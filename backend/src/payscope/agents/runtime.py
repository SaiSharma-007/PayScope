import asyncio
import json
from dataclasses import asdict, replace
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import sqlalchemy as sa
from agent_framework import Message
from openai import AsyncOpenAI
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payscope.agents import runs
from payscope.agents.evidence import SummaryRequest
from payscope.agents.language import OpenAIProvider, RunLimits, WorkflowFailure
from payscope.agents.leases import AdmissionUnavailable, Lease, LeaseStore
from payscope.agents.schemas import RunRequest
from payscope.agents.workflow import Outcome, PayWorkflow, TurnInput
from payscope.analytics.cache import ReportCache
from payscope.auth.service import ActiveSession
from payscope.config import Settings
from payscope.logging import log_failure, logger
from payscope.models import (
    AGENT_ACTIVE_STATUSES,
    agent_conversations,
    agent_messages,
    agent_runs,
    auth_sessions,
    hr_users,
)

DATABASE_LEASE = timedelta(seconds=30)
RENEW_EVERY = 3
DEFAULT_LIMITS = RunLimits()
FAILED_MESSAGES = {
    "MODEL_FIRST_UPDATE_TIMEOUT": "The model took too long to start. Try again.",
    "MODEL_PROVIDER_FAILED": "The model could not complete the request. Try again.",
    "MODEL_CALL_LIMIT": "The agent reached its model request limit. Try a more specific question.",
    "MODEL_OUTPUT_LIMIT": "The agent reached its response limit. Try a more specific question.",
    "TOOL_ATTEMPT_LIMIT": "The agent reached its report request limit. Try a more specific question.",
    "TOOL_TIMEOUT": "The salary report took too long. Try again with a narrower filter.",
    "RUN_TIMEOUT": "The request ran out of time. Try again with a narrower question.",
    "ANALYST_INVALID_OUTPUT": "The agent could not select a report. Try rephrasing the question.",
    "WORKFLOW_FAILED": "The agent run ended before it could answer. Try again.",
}


def live_session_predicate(session_id: UUID, user_id: UUID):
    matching = (
        sa.select(auth_sessions.c.id)
        .join(hr_users)
        .where(
            auth_sessions.c.id == session_id,
            auth_sessions.c.user_id == user_id,
            auth_sessions.c.revoked_at.is_(None),
            auth_sessions.c.expires_at > sa.func.clock_timestamp(),
            hr_users.c.is_active.is_(True),
        )
    )
    return matching.exists()


async def session_is_live(
    database: AsyncSession, session_id: UUID, user_id: UUID
) -> bool:
    return bool(await database.scalar(sa.select(live_session_predicate(session_id, user_id))))


class AgentRuntime:
    def __init__(
        self,
        database: async_sessionmaker,
        provider: OpenAIProvider | None,
        leases: LeaseStore | None,
        limits: RunLimits = DEFAULT_LIMITS,
        report_cache: ReportCache | None = None,
        owns_lease_client: bool = False,
    ) -> None:
        self.database = database
        self.provider = provider
        self.leases = leases
        self.limits = limits
        self.report_cache = report_cache
        self.owns_lease_client = owns_lease_client
        self.tasks: dict[UUID, asyncio.Task] = {}
        self.maintenance: asyncio.Task | None = None
        self.closing = False
        self.updates = asyncio.Event()

    def notify(self) -> None:
        self.updates.set()
        self.updates = asyncio.Event()

    @classmethod
    def from_settings(
        cls,
        database: async_sessionmaker,
        cache: ReportCache | None,
        settings: Settings,
    ) -> AgentRuntime:
        leases = None
        provider = None
        if cache is not None and settings.agent_user_quota is not None:
            leases = LeaseStore(
                Redis.from_url(
                    settings.redis_url.get_secret_value(),
                    max_connections=10,
                    socket_timeout=3,
                    socket_connect_timeout=3,
                    retry=Retry(NoBackoff(), 0),
                    protocol=2,
                    driver_info=None,
                ),
                cache.prefix,
                settings.agent_global_quota,
                settings.agent_user_quota,
            )
        if settings.agent_openai_api_key and settings.agent_openai_model:
            provider = OpenAIProvider(
                settings.agent_openai_model,
                AsyncOpenAI(
                    api_key=settings.agent_openai_api_key.get_secret_value(),
                    base_url=settings.agent_openai_base_url,
                    max_retries=0,
                ),
                chat_completions=settings.agent_openai_base_url is not None,
                strong_model=settings.agent_openai_strong_model,
            )
        return cls(database, provider, leases, report_cache=cache, owns_lease_client=leases is not None)

    async def close(self) -> None:
        self.closing = True
        tasks = list(self.tasks.values())
        if self.maintenance is not None:
            tasks.append(self.maintenance)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.provider is not None:
            await self.provider.close()
        if self.owns_lease_client:
            await self.leases.redis.aclose()

    async def stored(self, operation, *args, **kwargs):
        async with self.database() as database:
            return await operation(database, *args, **kwargs)

    async def submit(
        self, request: RunRequest, session: ActiveSession, key: UUID
    ) -> sa.RowMapping:
        user_id = session.user_id
        prior = await self.stored(runs.find_admitted_run, request, user_id, key)
        if prior is not None:
            return prior
        turn = await self.prepare_turn(request, user_id)
        if self.provider is None or self.closing:
            raise runs.RunConflict("AGENT_NOT_CONFIGURED")
        if self.leases is None:
            raise runs.RunConflict("AGENT_ADMISSION_UNAVAILABLE")
        if self.maintenance is None:
            self.maintenance = asyncio.create_task(self.reconcile_periodically())

        lease = Lease(user_id, key, uuid4())
        wait_until = asyncio.get_running_loop().time() + 2
        while True:
            rejection = await self.leases.reserve(lease)
            if rejection is None:
                break
            prior = await self.stored(runs.find_admitted_run, request, user_id, key)
            if prior is not None:
                return prior
            if (
                rejection != "ADMISSION_PENDING"
                or asyncio.get_running_loop().time() >= wait_until
            ):
                raise runs.RunConflict(rejection)
            await asyncio.sleep(0.05)

        handed_off = False
        try:
            fingerprint = sha256(
                f"ask-about-pay:v2:{self.provider.model}:{self.provider.strong_model}".encode()
            ).hexdigest()
            run, created = await self.stored(
                runs.admit_run,
                request,
                user_id=user_id,
                auth_session_id=session.id,
                idempotency_key=key,
                runtime_fingerprint=fingerprint,
                runtime_limits=asdict(self.limits),
                start_timeout=DATABASE_LEASE,
            )
            if created:
                task = asyncio.create_task(
                    self.execute(run, lease, turn), name=f"agent-run-{run.id}"
                )
                self.tasks[run.id] = task
                task.add_done_callback(lambda _: self.tasks.pop(run.id, None))
                handed_off = True
            return run
        finally:
            if not handed_off:
                await self.release(lease)

    async def prepare_turn(self, request: RunRequest, user_id: UUID) -> TurnInput:
        if request.conversation_id is None:
            if request.kind != "question" or request.parent_run_id is not None:
                raise runs.RunConflict("INVALID_RUN_SOURCE")
            return TurnInput(request.question)

        async with self.database() as database:
            exists = await database.scalar(
                sa.select(agent_conversations.c.id).where(
                    agent_conversations.c.id == request.conversation_id,
                    agent_conversations.c.user_id == user_id,
                    agent_conversations.c.deleted_at.is_(None),
                )
            )
            active_run_id = await database.scalar(
                sa.select(agent_runs.c.id).where(
                    agent_runs.c.conversation_id == request.conversation_id,
                    runs.ACTIVE,
                )
            )
        if exists is None:
            raise runs.RunConflict("CONVERSATION_NOT_FOUND")
        if active_run_id is not None:
            expired = await self.stored(runs.interrupt_expired_run, active_run_id)
            if expired is None:
                active = await self.stored(runs.owned_run, active_run_id, user_id)
                if active.status in AGENT_ACTIVE_STATUSES:
                    raise runs.RunConflict("CONVERSATION_BUSY", active_run_id)

        if request.kind == "question" and request.parent_run_id is None:
            return TurnInput(request.question)
        return await self.linked_turn(request, user_id)

    async def recent_history(self, conversation_id: UUID) -> tuple[Message, ...]:
        async with self.database() as database:
            found = await database.execute(
                sa.select(
                    agent_messages.c.role,
                    agent_messages.c.text,
                    agent_messages.c.structured_content,
                )
                .select_from(agent_runs.join(agent_messages))
                .where(
                    agent_runs.c.conversation_id == conversation_id,
                    agent_runs.c.status == "completed",
                    agent_messages.c.is_partial.is_(False),
                )
                .order_by(agent_runs.c.turn_number.desc(), agent_messages.c.role)
                .limit(6)
            )
            return tuple(
                Message(
                    role,
                    [
                        body[:2000]
                        + (
                            "\nSaved report settings: "
                            + json.dumps(
                                {
                                    key: report[key]
                                    for key in ("filters", "operation", "metric")
                                    if key in report
                                }
                            )
                            if (report := (structured or {}).get("report"))
                            else ""
                        )
                    ],
                )
                for role, body, structured in reversed(found.all())
                if body
            )

    async def linked_turn(self, request: RunRequest, user_id: UUID) -> TurnInput:
        if request.kind == "question" or request.parent_run_id is None:
            raise runs.RunConflict("INVALID_RUN_SOURCE")
        async with self.database() as database:
            try:
                source = await runs.owned_run(database, request.parent_run_id, user_id)
            except runs.RunConflict:
                raise runs.RunConflict("INVALID_RUN_SOURCE") from None
            if source.conversation_id != request.conversation_id:
                raise runs.RunConflict("INVALID_RUN_SOURCE")
            records = (
                (
                    await database.execute(
                        agent_messages.select().where(
                            agent_messages.c.run_id == source.id,
                        )
                    )
                )
                .mappings()
                .all()
            )
        messages = {record.role: record for record in records}
        if request.kind == "retry":
            if source.status not in ("failed", "interrupted", "cancelled"):
                raise runs.RunConflict("INVALID_RUN_SOURCE")
            if request.question != messages["user"].text:
                raise runs.RunConflict("INVALID_RUN_SOURCE")
            origin = (
                await self.retry_origin(source) if source.kind == "retry" else source
            )
            if origin.kind == "clarification":
                response = request.model_copy(
                    update={
                        "kind": "clarification",
                        "parent_run_id": origin.parent_run_id,
                    }
                )
                return await self.linked_turn(response, user_id)
            return TurnInput(request.question)
        if source.status != "awaiting_clarification" or "assistant" not in messages:
            raise runs.RunConflict("INVALID_RUN_SOURCE")
        clarification = messages["assistant"].structured_content["clarification"]
        report = clarification.get("report_request")
        if report is not None:
            selected = request.question.upper()
            if selected not in clarification["choices"]:
                raise runs.RunConflict("INVALID_CLARIFICATION_CHOICE")
            continuation = SummaryRequest.model_validate(
                report | {"currency_code": selected}
            )
            return TurnInput(request.question, continuation=continuation)
        return TurnInput(
            request.question,
            (
                Message("user", [messages["user"].text]),
                Message("assistant", [clarification["question"]]),
            ),
        )

    async def retry_origin(self, source: sa.RowMapping) -> sa.RowMapping:
        chain = (
            sa.select(
                agent_runs.c.kind,
                agent_runs.c.parent_run_id,
                agent_runs.c.turn_number,
            )
            .where(agent_runs.c.id == source.id)
            .cte(recursive=True)
        )
        older = agent_runs.alias()
        chain = chain.union_all(
            sa.select(
                older.c.kind,
                older.c.parent_run_id,
                older.c.turn_number,
            )
            .join(chain, older.c.id == chain.c.parent_run_id)
            .where(
                chain.c.kind == "retry",
                older.c.conversation_id == source.conversation_id,
                older.c.turn_number < chain.c.turn_number,
            )
        )
        async with self.database() as database:
            result = await database.execute(
                sa.select(chain).where(chain.c.kind != "retry")
            )
            origin = result.mappings().one_or_none()
        if origin is None:
            raise runs.RunConflict("INVALID_RUN_SOURCE")
        return origin

    async def release(self, lease: Lease) -> None:
        try:
            await self.leases.release(lease)
        except AdmissionUnavailable:
            logger.warning("agent.lease_release_unavailable")

    async def execute(self, run: sa.RowMapping, lease: Lease, turn: TurnInput) -> None:
        try:
            if not await self.leases.renew(lease):
                return
            claimed = await self.stored(
                runs.claim_run, run.id, lease.owner, DATABASE_LEASE
            )
            if claimed is None:
                return
            try:
                async with asyncio.timeout(self.limits.run_seconds):
                    outcome = await self.execute_claimed(claimed, lease, turn)
            except asyncio.CancelledError:
                outcome = Outcome("interrupted")
            except TimeoutError:
                outcome = Outcome("failed", error_code="RUN_TIMEOUT")
            except WorkflowFailure as exc:
                outcome = Outcome("failed", error_code=exc.code)
            except Exception as exc:  # noqa: BLE001
                log_failure("agent.workflow_failed", exc, request_id=str(run.id))
                outcome = Outcome("failed", error_code="WORKFLOW_FAILED")
            await self.finish(run.id, lease.owner, outcome)
        except (AdmissionUnavailable, runs.RunConflict) as exc:
            log_failure("agent.ownership_lost", exc, request_id=str(run.id))
        except Exception as exc:  # noqa: BLE001
            log_failure("agent.execution_failed", exc, request_id=str(run.id))
        finally:
            await self.release(lease)

    async def execute_claimed(
        self, run: sa.RowMapping, lease: Lease, turn: TurnInput
    ) -> Outcome:
        # Renew ownership during startup too, before slow database reads or event writes.
        work = asyncio.create_task(self.run_workflow(run, lease, turn))
        control = asyncio.create_task(self.watch(run, lease))
        try:
            done, _ = await asyncio.wait(
                (work, control), return_when=asyncio.FIRST_COMPLETED
            )
            return control.result() if control in done else work.result()
        finally:
            work.cancel()
            control.cancel()
            await asyncio.gather(work, control, return_exceptions=True)

    async def run_workflow(
        self, run: sa.RowMapping, lease: Lease, turn: TurnInput
    ) -> Outcome:
        if run.cancel_requested_at or not await self.stored(
            session_is_live, run.auth_session_id, run.user_id
        ):
            await self.stored(runs.request_cancel, run.id, run.user_id)
            return Outcome("cancelled")
        prompts = await self.stored(runs.pinned_prompts, run)
        if not turn.history and turn.continuation is None and run.turn_number > 1:
            turn = replace(turn, history=await self.recent_history(run.conversation_id))
        workflow = PayWorkflow(
            self.database, self.provider, run.id, lease.owner, prompts, self.limits,
            report_cache=self.report_cache,
            notify=self.notify,
        )
        await workflow.event("run_started", {})
        logger.info(
            "agent.started run=%s analyst_version=%d writer_version=%d",
            run.id,
            run.pay_analyst_version,
            run.answer_writer_version,
        )
        return await workflow.run(turn)

    async def watch(self, run: sa.RowMapping, lease: Lease) -> Outcome:
        while True:
            try:
                if not await self.leases.renew(lease):
                    logger.warning("agent.redis_ownership_lost run=%s", run.id)
                    return Outcome("interrupted")
            except AdmissionUnavailable:
                logger.warning("agent.lease_renewal_unavailable run=%s", run.id)
                return Outcome("interrupted")
            state = await self.stored(
                runs.renew_run, run.id, lease.owner, DATABASE_LEASE
            )
            if state is None:
                logger.warning("agent.database_ownership_lost run=%s", run.id)
                return Outcome("interrupted")
            if state.cancel_requested_at or not await self.stored(
                session_is_live, run.auth_session_id, run.user_id
            ):
                await self.stored(runs.request_cancel, run.id, run.user_id)
                return Outcome("cancelled")
            await asyncio.sleep(RENEW_EVERY)

    async def finish(self, run_id: UUID, owner: UUID, outcome: Outcome) -> None:
        payload = outcome.payload.copy()
        answer = outcome.answer
        if outcome.error_code:
            answer = FAILED_MESSAGES[outcome.error_code]
            error = {"code": outcome.error_code, "message": answer, "retryable": True}
            payload["error"] = error
        final = await self.stored(
            runs.finalize_run,
            run_id,
            owner,
            status=outcome.status,
            answer=answer,
            payload=payload,
        )
        self.notify()
        logger.info("agent.finished run=%s status=%s", run_id, final.payload["status"])

    async def reconcile_periodically(self) -> None:
        while True:
            await asyncio.sleep(RENEW_EVERY)
            try:
                async with self.database() as database:
                    result = await database.scalars(
                        sa.select(agent_runs.c.id)
                        .where(
                            runs.ACTIVE,
                            agent_runs.c.execution_lease_expires_at
                            <= sa.func.clock_timestamp(),
                        )
                        .limit(100)
                    )
                    expired = result.all()
                for run_id in expired:
                    await self.stored(runs.interrupt_expired_run, run_id)
            except Exception as exc:  # noqa: BLE001
                log_failure("agent.reconciliation_failed", exc)
