from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.agents.schemas import RunRequest, TerminalStatus
from payscope.models import AGENT_ACTIVE_STATUSES, AGENT_TERMINAL_STATUSES
from payscope.models import agent_conversations as conversations
from payscope.models import agent_events as events
from payscope.models import agent_messages as messages
from payscope.models import agent_prompt_catalog as catalog
from payscope.models import agent_prompt_versions as versions
from payscope.models import agent_runs as runs
from payscope.models import agent_tool_calls as tools

ACTIVE = runs.c.status.in_(AGENT_ACTIVE_STATUSES)
LEASE_VALID = runs.c.execution_lease_expires_at > sa.func.clock_timestamp()


class RunConflict(Exception):
    def __init__(self, code: str, run_id: UUID | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.run_id = run_id


async def find_admitted_run(
    database: AsyncSession,
    request: RunRequest,
    user_id: UUID,
    idempotency_key: UUID,
) -> sa.RowMapping | None:
    result = await database.execute(
        sa.select(runs, conversations.c.deleted_at).join(conversations).where(
            runs.c.user_id == user_id,
            runs.c.idempotency_key == idempotency_key,
        )
    )
    run = result.mappings().one_or_none()
    if run is not None and run.deleted_at is not None:
        raise RunConflict("CONVERSATION_NOT_FOUND")
    if (
        run is not None
        and run.request_hash != sha256(request.model_dump_json().encode()).digest()
    ):
        raise RunConflict("IDEMPOTENCY_CONFLICT")
    return run


async def admit_run(
    database: AsyncSession,
    request: RunRequest,
    *,
    user_id: UUID,
    auth_session_id: UUID | None,
    idempotency_key: UUID,
    runtime_fingerprint: str,
    runtime_limits: dict,
    start_timeout: timedelta,
) -> tuple[sa.RowMapping, bool]:
    """Return the admitted run and whether it was newly created."""
    request_hash = sha256(request.model_dump_json().encode()).digest()
    lock_key = int.from_bytes(
        sha256(user_id.bytes + idempotency_key.bytes).digest()[:8], "big", signed=True
    )
    async with database.begin():
        # The key lock also covers simultaneous requests that have no conversation ID yet.
        await database.execute(sa.select(sa.func.pg_advisory_xact_lock(lock_key)))
        prior = await find_admitted_run(database, request, user_id, idempotency_key)
        if prior is not None:
            return prior, False

        conversation_id = request.conversation_id
        if conversation_id is None:
            if request.kind != "question" or request.parent_run_id is not None:
                raise RunConflict("INVALID_RUN_SOURCE")
            conversation_id = uuid4()
            await database.execute(
                conversations.insert().values(
                    id=conversation_id,
                    user_id=user_id,
                    title=request.question[:120],
                )
            )

        conversation = (
            (
                await database.execute(
                    conversations.select()
                    .where(
                        conversations.c.id == conversation_id,
                        conversations.c.user_id == user_id,
                        conversations.c.deleted_at.is_(None),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if conversation is None:
            raise RunConflict("CONVERSATION_NOT_FOUND")
        active_run_id = await database.scalar(
            sa.select(runs.c.id).where(
                runs.c.conversation_id == conversation_id,
                ACTIVE,
            )
        )
        if active_run_id is not None:
            raise RunConflict("CONVERSATION_BUSY", active_run_id)

        if request.kind == "question":
            if request.parent_run_id is not None:
                raise RunConflict("INVALID_RUN_SOURCE")
        else:
            parent_status = await database.scalar(
                sa.select(runs.c.status).where(
                    runs.c.id == request.parent_run_id,
                    runs.c.conversation_id == conversation_id,
                )
            )
            source_statuses = (
                ("awaiting_clarification",)
                if request.kind == "clarification"
                else ("failed", "interrupted", "cancelled")
            )
            if parent_status not in source_statuses:
                raise RunConflict("INVALID_RUN_SOURCE")

        pinned = dict(
            (
                await database.execute(
                    sa.select(catalog.c.agent_key, catalog.c.active_version)
                )
            )
            .tuples()
            .all()
        )
        run = (
            (
                await database.execute(
                    runs.insert()
                    .values(
                        id=uuid4(),
                        conversation_id=conversation_id,
                        user_id=user_id,
                        auth_session_id=auth_session_id,
                        turn_number=conversation.next_turn_number,
                        kind=request.kind,
                        parent_run_id=request.parent_run_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                        status="queued",
                        pay_analyst_version=pinned["pay_analyst"],
                        answer_writer_version=pinned["answer_writer"],
                        runtime_fingerprint=runtime_fingerprint,
                        runtime_limits=runtime_limits,
                        execution_lease_expires_at=sa.func.clock_timestamp()
                        + start_timeout,
                    )
                    .returning(runs)
                )
            )
            .mappings()
            .one()
        )
        await database.execute(
            messages.insert().values(
                run_id=run.id,
                role="user",
                text=request.question,
            )
        )
        await database.execute(
            conversations.update()
            .where(conversations.c.id == conversation_id)
            .values(
                next_turn_number=conversations.c.next_turn_number + 1,
                updated_at=sa.func.clock_timestamp(),
            )
        )
        await _write_event(
            database, run, "accepted", {"conversation_id": str(conversation_id)}
        )
        return await owned_run(database, run.id, user_id), True


async def pinned_prompts(database: AsyncSession, run: sa.RowMapping) -> dict[str, str]:
    async with database.begin():
        result = await database.execute(
            sa.select(versions.c.agent_key, versions.c.body).where(
                sa.tuple_(versions.c.agent_key, versions.c.version).in_(
                    [
                        ("pay_analyst", run.pay_analyst_version),
                        ("answer_writer", run.answer_writer_version),
                    ]
                )
            )
        )
        return dict(result.tuples().all())


async def claim_run(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    lease: timedelta,
) -> sa.RowMapping | None:
    async with database.begin():
        result = await database.execute(
            runs.update()
            .where(
                runs.c.id == run_id,
                runs.c.status == "queued",
                LEASE_VALID,
            )
            .values(
                status="running",
                execution_owner_token=owner_token,
                started_at=sa.func.clock_timestamp(),
                execution_lease_expires_at=sa.func.clock_timestamp() + lease,
            )
            .returning(runs)
        )
        return result.mappings().one_or_none()


async def renew_run(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    lease: timedelta,
) -> sa.RowMapping | None:
    async with database.begin():
        result = await database.execute(
            runs.update()
            .where(
                runs.c.id == run_id,
                runs.c.status == "running",
                runs.c.execution_owner_token == owner_token,
                LEASE_VALID,
            )
            .values(execution_lease_expires_at=sa.func.clock_timestamp() + lease)
            .returning(runs)
        )
        return result.mappings().one_or_none()


async def request_cancel(
    database: AsyncSession, run_id: UUID, user_id: UUID
) -> sa.RowMapping:
    async with database.begin():
        result = await database.execute(
            runs.update()
            .where(
                runs.c.id == run_id,
                runs.c.user_id == user_id,
                ACTIVE,
                runs.c.cancel_requested_at.is_(None),
            )
            .values(cancel_requested_at=sa.func.clock_timestamp())
            .returning(runs)
        )
        run = result.mappings().one_or_none()
        if run is not None:
            return run
        return await owned_run(database, run_id, user_id)


async def owned_run(
    database: AsyncSession, run_id: UUID, user_id: UUID
) -> sa.RowMapping:
    result = await database.execute(
        sa.select(runs).join(conversations).where(
            runs.c.id == run_id, runs.c.user_id == user_id,
            conversations.c.deleted_at.is_(None),
        )
    )
    run = result.mappings().one_or_none()
    if run is None:
        raise RunConflict("RUN_NOT_FOUND")
    return run


async def _execution_run(database: AsyncSession, run_id: UUID) -> sa.RowMapping:
    result = await database.execute(
        runs.select().where(runs.c.id == run_id).with_for_update()
    )
    run = result.mappings().one_or_none()
    if run is None:
        raise RunConflict("RUN_NOT_FOUND")
    return run


async def _require_execution(
    database: AsyncSession, run: sa.RowMapping, owner_token: UUID
) -> None:
    now = await database.scalar(sa.select(sa.func.clock_timestamp()))
    if (
        run.status != "running"
        or run.execution_owner_token != owner_token
        or run.execution_lease_expires_at <= now
    ):
        raise RunConflict("EXECUTION_LEASE_LOST")


async def _write_event(
    database: AsyncSession,
    run: sa.RowMapping,
    event_type: str,
    payload: dict,
    agent_name: str | None = None,
    call_id: UUID | None = None,
) -> sa.RowMapping:
    sequence = run.last_event_sequence + 1
    result = await database.execute(
        events.insert()
        .values(
            run_id=run.id,
            sequence=sequence,
            event_id=uuid4(),
            event_type=event_type,
            payload=payload,
            agent_name=agent_name,
            call_id=call_id,
            created_at=sa.func.clock_timestamp(),
        )
        .returning(events)
    )
    await database.execute(
        runs.update().where(runs.c.id == run.id).values(last_event_sequence=sequence)
    )
    return result.mappings().one()


async def append_event(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    event_type: str,
    payload: dict,
    *,
    agent_name: str | None = None,
    call_id: UUID | None = None,
) -> sa.RowMapping:
    if event_type == "final":
        raise ValueError("Use finalize_run to append a terminal event.")
    if event_type == "token" and not isinstance(payload.get("text"), str):
        raise ValueError("A token event requires a text segment.")
    async with database.begin():
        # Fence ownership and allocate the sequence in the same database round trip.
        owned = (
            runs.update()
            .where(
                runs.c.id == run_id,
                runs.c.status == "running",
                runs.c.execution_owner_token == owner_token,
                LEASE_VALID,
            )
            .values(last_event_sequence=runs.c.last_event_sequence + 1)
            .returning(runs.c.id, runs.c.last_event_sequence)
            .cte("owned_event_run")
        )
        result = await database.execute(
            events.insert()
            .from_select(
                ["run_id", "sequence", "event_id", "schema_version", "event_type", "payload", "agent_name", "call_id", "created_at"],
                sa.select(
                    owned.c.id,
                    owned.c.last_event_sequence,
                    sa.literal(uuid4(), type_=events.c.event_id.type),
                    sa.literal(1),
                    sa.literal(event_type),
                    sa.literal(payload, type_=events.c.payload.type),
                    sa.literal(agent_name, type_=events.c.agent_name.type),
                    sa.literal(call_id, type_=events.c.call_id.type),
                    sa.func.clock_timestamp(),
                ),
            )
            .returning(events)
        )
        event = result.mappings().one_or_none()
        if event is None:
            raise RunConflict("EXECUTION_LEASE_LOST")
        return event


async def replay_events(
    database: AsyncSession,
    run_id: UUID,
    user_id: UUID,
    after: int = 0,
    limit: int = 200,
) -> list[sa.RowMapping]:
    async with database.begin():
        await owned_run(database, run_id, user_id)
        result = await database.execute(
            events.select()
            .where(
                events.c.run_id == run_id,
                events.c.sequence > after,
            )
            .order_by(events.c.sequence)
            .limit(limit)
        )
        return list(result.mappings().all())


async def start_tool(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    *,
    attempt_number: int,
    tool_name: str,
    arguments: dict,
) -> sa.RowMapping:
    async with database.begin():
        run = await _execution_run(database, run_id)
        await _require_execution(database, run, owner_token)
        call_id = uuid4()
        await database.execute(
            tools.insert().values(
                id=call_id,
                run_id=run_id,
                attempt_number=attempt_number,
                tool_name=tool_name,
                arguments=arguments,
                started_at=sa.func.clock_timestamp(),
            )
        )
        return await _write_event(
            database,
            run,
            "tool_started",
            {"tool_name": tool_name, "arguments": arguments},
            "pay_analyst",
            call_id,
        )


async def finish_tool(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    call_id: UUID,
    *,
    status: str,
    summary: dict,
    result: dict | None = None,
    report_revision: int | None = None,
    error_code: str | None = None,
) -> sa.RowMapping:
    async with database.begin():
        run = await _execution_run(database, run_id)
        await _require_execution(database, run, owner_token)
        call = (
            (
                await database.execute(
                    tools.update()
                    .where(
                        tools.c.id == call_id,
                        tools.c.run_id == run_id,
                        tools.c.status == "running",
                    )
                    .values(
                        status=status,
                        result=result,
                        report_revision=report_revision,
                        error_code=error_code,
                        finished_at=sa.func.clock_timestamp(),
                    )
                    .returning(tools)
                )
            )
            .mappings()
            .one_or_none()
        )
        if call is None:
            raise RunConflict("TOOL_NOT_RUNNING")
        return await _tool_completed_event(database, run, call, summary)


async def _tool_completed_event(
    database: AsyncSession,
    run: sa.RowMapping,
    call: sa.RowMapping,
    summary: dict,
) -> sa.RowMapping:
    return await _write_event(
        database,
        run,
        "tool_completed",
        {
            "tool_name": call.tool_name,
            "status": call.status,
            "summary": summary,
            "duration_ms": round(
                (call.finished_at - call.started_at).total_seconds() * 1000
            ),
            "error_code": call.error_code,
        },
        "pay_analyst",
        call.id,
    )


async def _persist_final(
    database: AsyncSession,
    run: sa.RowMapping,
    status: TerminalStatus,
    answer: str | None,
    payload: dict,
) -> sa.RowMapping:
    if run.cancel_requested_at is not None:
        status = "cancelled"
    is_partial = status in ("cancelled", "interrupted")
    if is_partial:
        result = await database.execute(
            sa.select(events.c.event_type, events.c.payload)
            .where(
                events.c.run_id == run.id,
                events.c.event_type.in_(("token", "report_ready")),
            )
            .order_by(events.c.sequence)
        )
        chunks = []
        payload = {}
        for event_type, event_payload in result:
            if event_type == "token":
                chunks.append(event_payload["text"])
            else:
                payload["report"] = event_payload
        if "report" not in payload:
            report = await database.scalar(
                sa.select(tools.c.result)
                .where(
                    tools.c.run_id == run.id,
                    tools.c.tool_name == "get_salary_summary",
                    tools.c.status == "completed",
                    tools.c.result["report_type"].astext.in_(("annual_gross_base", "workforce_headcount")),
                )
                .limit(1)
            )
            if report is not None:
                payload["report"] = report
        answer = "".join(chunks) or None

    final_payload = {
        **payload,
        "status": status,
        "answer": answer,
        "is_partial": is_partial,
    }
    if answer is not None or payload:
        await database.execute(
            messages.insert().values(
                run_id=run.id,
                role="assistant",
                text=answer or "",
                is_partial=is_partial,
                structured_content=final_payload,
                created_at=sa.func.clock_timestamp(),
            )
        )
    unfinished = await database.execute(
        tools.update()
        .where(
            tools.c.run_id == run.id,
            tools.c.status == "running",
        )
        .values(
            status="cancelled" if is_partial else "failed",
            error_code="RUN_ENDED",
            finished_at=sa.func.clock_timestamp(),
        )
        .returning(tools)
    )
    for call in unfinished.mappings():
        await _tool_completed_event(database, run, call, {})
        run = await _execution_run(database, run.id)
    await database.execute(
        runs.update()
        .where(runs.c.id == run.id)
        .values(
            status=status,
            finished_at=sa.func.clock_timestamp(),
            execution_owner_token=None,
            execution_lease_expires_at=None,
        )
    )
    await database.execute(
        conversations.update()
        .where(conversations.c.id == run.conversation_id)
        .values(
            updated_at=sa.func.clock_timestamp(),
        )
    )
    if status == "failed" and "error" in payload:
        await _write_event(database, run, "error", payload["error"])
        run = await _execution_run(database, run.id)
    return await _write_event(database, run, "final", final_payload)


async def finalize_run(
    database: AsyncSession,
    run_id: UUID,
    owner_token: UUID,
    *,
    status: TerminalStatus,
    answer: str | None,
    payload: dict,
) -> sa.RowMapping:
    async with database.begin():
        run = await _execution_run(database, run_id)
        if run.status in AGENT_TERMINAL_STATUSES:
            result = await database.execute(
                events.select().where(
                    events.c.run_id == run_id,
                    events.c.event_type == "final",
                )
            )
            return result.mappings().one()
        await _require_execution(database, run, owner_token)
        return await _persist_final(database, run, status, answer, payload)


async def interrupt_expired_run(
    database: AsyncSession, run_id: UUID
) -> sa.RowMapping | None:
    async with database.begin():
        run = await _execution_run(database, run_id)
        now = await database.scalar(sa.select(sa.func.clock_timestamp()))
        if (
            run.status not in AGENT_ACTIVE_STATUSES
            or run.execution_lease_expires_at > now
        ):
            return None
        return await _persist_final(database, run, "interrupted", None, {})
