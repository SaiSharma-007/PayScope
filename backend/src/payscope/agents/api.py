import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from payscope.agents import runs
from payscope.agents.leases import AdmissionUnavailable
from payscope.agents.runtime import AgentRuntime, live_session_predicate
from payscope.agents.schemas import RunRequest, RunStatus
from payscope.auth.router import Session, VerifiedSession
from payscope.auth.service import ActiveSession
from payscope.database import DatabaseSession
from payscope.models import agent_events, agent_runs

HEARTBEAT_SECONDS = 5
MAX_BODY_BYTES = 32 * 1024
RETRY_AFTER = "2"
router = APIRouter(prefix="/agent/runs", tags=["Agent runs"])

PROBLEMS = {
    "CONVERSATION_BUSY": (409, "This chat already has a running request."),
    "CONVERSATION_NOT_FOUND": (404, "Conversation not found."),
    "RUN_NOT_FOUND": (404, "Run not found."),
    "IDEMPOTENCY_CONFLICT": (409, "That request key belongs to a different question."),
    "ADMISSION_PENDING": (
        409,
        "The original request is still being admitted. Retry with the same key.",
    ),
    "INVALID_RUN_SOURCE": (422, "Choose a valid run from this conversation."),
    "INVALID_CLARIFICATION_CHOICE": (422, "Choose one of the available currencies."),
    "INVALID_EVENT_CURSOR": (422, "The requested cursor is past the last saved event."),
    "USER_CONCURRENCY_LIMIT": (429, "You have reached your concurrent request limit."),
    "AGENT_POOL_BUSY": (503, "Agent capacity is busy. Please try again shortly."),
    "AGENT_ADMISSION_UNAVAILABLE": (503, "Agent requests are temporarily unavailable."),
    "AGENT_NOT_CONFIGURED": (503, "Ask about pay is unavailable in this environment."),
}


class CancelResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    cancel_requested: bool


def problem(code: str, run_id: UUID | None = None) -> HTTPException:
    status, message = PROBLEMS[code]
    detail = {"code": code, "message": message}
    if run_id is not None:
        detail["run_id"] = str(run_id)
    headers = {"Cache-Control": "no-store"}
    if status in (429, 503) or code == "ADMISSION_PENDING":
        headers["Retry-After"] = RETRY_AFTER
    return HTTPException(status, detail=detail, headers=headers)


async def parse_turn(request: Request) -> RunRequest:
    if (
        request.headers.get("content-type", "").partition(";")[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(415, detail="Agent requests require application/json.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, detail="Agent request is too large.")
        body.extend(chunk)
    try:
        return RunRequest.model_validate_json(body)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None


def encode_event(row: sa.RowMapping) -> bytes:
    event = {
        "schema_version": row.schema_version,
        "event_id": str(row.event_id),
        "run_id": str(row.run_id),
        "sequence": row.sequence,
        "timestamp": row.created_at.isoformat(),
        "type": row.event_type,
        "payload": row.payload,
    }
    if row.agent_name is not None:
        event["agent_name"] = row.agent_name
    if row.call_id is not None:
        event["call_id"] = str(row.call_id)
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {row.sequence}\nevent: {row.event_type}\ndata: {data}\n\n".encode()


async def follow_events(
    runtime: AgentRuntime,
    run_id: UUID,
    session: ActiveSession,
    after: int,
) -> AsyncIterator[bytes]:
    clock = asyncio.get_running_loop()
    heartbeat_at = clock.time() + HEARTBEAT_SECONDS
    while True:
        updated = runtime.updates
        # One authorized snapshot avoids opening a connection for each stream check.
        async with runtime.database() as database:
            result = await database.execute(
                sa.select(
                    agent_runs.c.finished_at,
                    agent_runs.c.last_event_sequence,
                    (agent_runs.c.execution_lease_expires_at <= sa.func.clock_timestamp()).label("lease_expired"),
                    *agent_events.c,
                )
                .select_from(agent_runs)
                .outerjoin(agent_events, sa.and_(
                    agent_events.c.run_id == agent_runs.c.id,
                    agent_events.c.sequence > after,
                ))
                .where(
                    agent_runs.c.id == run_id,
                    agent_runs.c.user_id == session.user_id,
                    live_session_predicate(session.id, session.user_id),
                )
                .order_by(agent_events.c.sequence)
                .limit(200)
            )
            snapshot = result.mappings().all()
        if not snapshot:
            return
        batch = [row for row in snapshot if row.event_id is not None]
        if batch:
            for row in batch:
                yield encode_event(row)
                after = row.sequence
                if row.event_type == "final":
                    return
            heartbeat_at = clock.time() + HEARTBEAT_SECONDS
            continue

        run = snapshot[0]
        if run.finished_at is not None and after >= run.last_event_sequence:
            return
        if run.finished_at is None and run.lease_expired:
            await runtime.stored(runs.interrupt_expired_run, run_id)
            runtime.notify()
            continue
        if clock.time() >= heartbeat_at:
            yield b": keep-alive\n\n"
            heartbeat_at = clock.time() + HEARTBEAT_SECONDS
        try:
            async with asyncio.timeout(1):
                await updated.wait()
        except TimeoutError:
            pass


def stream_response(
    runtime: AgentRuntime, run_id: UUID, session: ActiveSession, after: int = 0
):
    return StreamingResponse(
        follow_events(runtime, run_id, session, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post(
    "",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": RunRequest.model_json_schema()},
            },
        }
    },
)
async def start_run(
    request: Request,
    session: VerifiedSession,
    database: DatabaseSession,
    key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> StreamingResponse:
    await database.rollback()
    body = await parse_turn(request)
    runtime = request.app.state.agent_runtime
    try:
        run = await runtime.submit(body, session, key)
    except AdmissionUnavailable:
        raise problem("AGENT_ADMISSION_UNAVAILABLE") from None
    except runs.RunConflict as exc:
        raise problem(exc.code, exc.run_id) from None
    return stream_response(runtime, run.id, session)


@router.get(
    "/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def run_events(
    run_id: UUID,
    request: Request,
    session: Session,
    database: DatabaseSession,
    after: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
) -> StreamingResponse:
    try:
        run = await runs.owned_run(database, run_id, session.user_id)
    except runs.RunConflict as exc:
        raise problem(exc.code) from None
    if after > run.last_event_sequence:
        raise problem("INVALID_EVENT_CURSOR")
    await database.rollback()
    return stream_response(request.app.state.agent_runtime, run_id, session, after)


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    request: Request,
    session: VerifiedSession,
    database: DatabaseSession,
) -> CancelResponse:
    await database.rollback()
    runtime = request.app.state.agent_runtime
    try:
        run = await runtime.stored(runs.request_cancel, run_id, session.user_id)
    except runs.RunConflict as exc:
        raise problem(exc.code) from None
    return CancelResponse(
        run_id=run.id,
        status=run.status,
        cancel_requested=run.cancel_requested_at is not None,
    )
