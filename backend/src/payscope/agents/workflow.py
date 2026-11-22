import asyncio
import json
import re
from dataclasses import dataclass, field, replace
from typing import Literal
from uuid import UUID

from agent_framework import Content, Message, WorkflowBuilder, WorkflowContext, executor
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from payscope.agents import runs
from payscope.agents.evidence import (
    MAX_GROUPS,
    Claim,
    ClaimVerifier,
    Evidence,
    InvalidToolRequest,
    OptionsRequest,
    SummaryRequest,
    WriterAnswer,
    computed_summary,
    currencies_in,
    make_evidence,
    report_options,
    validate_report_filters,
)
from payscope.agents.language import (
    ModelBudget,
    OpenAIProvider,
    RunLimits,
    WorkflowFailure,
)
from payscope.agents.schemas import TerminalStatus
from payscope.analytics.cache import ReportCache
from payscope.analytics.service import get_salary_report, get_headcount_report

UNSUPPORTED = (
    "I can only help with PayScope reports. Ask about workforce headcount or current annual gross base pay "
    "by country, department, or job title. Base pay reports use one currency at a time."
)
CLARIFICATION_QUESTIONS = {
    "currency": "Which currency should I use?",
    "country": "Which country should I use?",
    "department": "Which department should I use?",
    "job_title": "Which job title should I use?",
    "grouping": "Should I group by country, department, or job title?",
    "metric": "Which salary measure should I use?",
    "scope": "Which group or part of the workforce should I include?",
}
CLAIMS_PREFIX = re.compile(r'\s*\{\s*"claims"\s*:\s*\[')


class AnalystDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["clarify", "unsupported"]
    field: (
        Literal[
            "currency",
            "country",
            "department",
            "job_title",
            "grouping",
            "metric",
            "scope",
        ]
        | None
    )


@dataclass(frozen=True)
class TurnInput:
    question: str
    history: tuple[Message, ...] = ()
    continuation: SummaryRequest | None = None


@dataclass(frozen=True)
class Outcome:
    status: TerminalStatus
    answer: str | None = None
    payload: dict = field(default_factory=dict)
    error_code: str | None = None


class ClaimsStream:
    def __init__(self) -> None:
        self.raw = ""
        self.position: int | None = None
        self.needs_comma = False
        self.decoder = json.JSONDecoder()

    def feed(self, delta: str):
        self.raw += delta
        if self.position is None:
            start = CLAIMS_PREFIX.match(self.raw)
            if start is None:
                return
            self.position = start.end()
        while True:
            while self.position < len(self.raw) and self.raw[self.position].isspace():
                self.position += 1
            if self.position == len(self.raw) or self.raw[self.position] == "]":
                return
            if self.needs_comma:
                if self.raw[self.position] != ",":
                    return
                self.position += 1
                self.needs_comma = False
                continue
            try:
                item, end = self.decoder.raw_decode(self.raw, self.position)
            except json.JSONDecodeError:
                return
            self.position = end
            self.needs_comma = True
            yield Claim.model_validate(item)


class PayWorkflow:
    def __init__(
        self,
        database: async_sessionmaker,
        provider: OpenAIProvider,
        run_id: UUID,
        owner: UUID,
        prompts: dict[str, str],
        limits: RunLimits,
        report_cache: ReportCache | None = None,
        notify=None,
    ) -> None:
        self.database = database
        self.run_id = run_id
        self.owner = owner
        self.limits = limits
        self.report_cache = report_cache
        self.notify = notify
        self.budget = ModelBudget(limits, self.event)
        self.analyst, self.writer = provider.agents(prompts)
        self.provider = provider
        self.prompts = prompts
        self.tool_attempts = 0
        self.report: dict | None = None

    async def event(
        self, event_type: str, payload: dict, agent_name: str | None = None
    ) -> None:
        async with self.database() as session:
            await runs.append_event(
                session,
                self.run_id,
                self.owner,
                event_type,
                payload,
                agent_name=agent_name,
            )
        if self.notify is not None:
            self.notify()

    async def run(self, turn: TurnInput) -> Outcome:
        @executor(id="pay_analyst")
        async def analyze(
            value: TurnInput, ctx: WorkflowContext[Evidence, Outcome]
        ) -> None:
            try:
                result = await self.analyze(value)
            except WorkflowFailure as error:
                await ctx.yield_output(Outcome("failed", error_code=error.code))
                return
            if isinstance(result, Outcome):
                await ctx.yield_output(result)
            else:
                await ctx.send_message(result)

        @executor(id="answer_writer")
        async def write(value: Evidence, ctx: WorkflowContext[None, Outcome]) -> None:
            try:
                result = await self.write(value)
            except WorkflowFailure as error:
                result = Outcome(
                    "failed", payload={"report": self.report}, error_code=error.code
                )
            await ctx.yield_output(result)

        workflow = (
            WorkflowBuilder(
                name="ask_about_pay",
                start_executor=analyze,
                output_from=[analyze, write],
            )
            .add_edge(analyze, write)
            .build()
        )
        outcome = None
        async with workflow.run(turn, stream=True) as stream:
            async for event in stream:
                if event.type == "output":
                    outcome = event.data
        if not isinstance(outcome, Outcome):
            raise WorkflowFailure("WORKFLOW_FAILED")
        return outcome

    async def analyze(self, turn: TurnInput) -> Evidence | Outcome:
        await self.event("agent_started", {}, "pay_analyst")
        try:
            result = await self.select_report(turn)
        except WorkflowFailure:
            await self.event("agent_completed", {"outcome": "failed"}, "pay_analyst")
            raise
        await self.event(
            "agent_completed",
            {
                "outcome": result.status
                if isinstance(result, Outcome)
                else "report_ready"
            },
            "pay_analyst",
        )
        if isinstance(result, Evidence):
            await self.event(
                "handoff_started", {"source": "pay_analyst", "target": "answer_writer"}
            )
        return result

    async def select_report(self, turn: TurnInput) -> Evidence | Outcome:
        if turn.continuation is not None:
            self.tool_attempts = 1
            return await self.run_tool("get_salary_summary", turn.continuation)

        if self.provider.chat_completions:
            self.tool_attempts += 1
            options = await self.run_tool("get_report_options", OptionsRequest())
            turn = replace(
                turn,
                question=(
                    f"Report reference values supplied by PayScope: {json.dumps(options)}\n"
                    f"Question: {turn.question}"
                ),
            )

        try:
            return await self.select_with(turn, self.analyst)
        except WorkflowFailure as error:
            if (
                error.code not in ("ANALYST_INVALID_OUTPUT", "FOLLOWUP_UNRESOLVED")
                or not self.provider.strong_model
                or self.budget.calls >= self.limits.model_calls - 1
                or self.tool_attempts >= self.limits.tool_attempts
            ):
                if error.code == "FOLLOWUP_UNRESOLVED":
                    return await self.clarify("scope")
                raise
            await self.event(
                "model_escalated",
                {
                    "from_model": self.provider.model,
                    "to_model": self.provider.strong_model,
                    "reason": error.code,
                },
                "pay_analyst",
            )
            strong, _ = self.provider.agents(self.prompts, strong=True)
            return await self.select_with(turn, strong, thinking=True)

    async def select_with(
        self, turn: TurnInput, analyst, *, thinking: bool = False
    ) -> Evidence | Outcome:
        session = analyst.create_session()
        dialogue = [*turn.history, Message("user", [turn.question])]
        while True:
            response = await self.budget.invoke(
                analyst,
                session,
                dialogue,
                AnalystDecision,
                thinking=thinking,
                model_name=self.provider.strong_model if thinking else self.provider.model,
            )
            calls = [
                content
                for message in response.messages
                for content in message.contents
                if content.type == "function_call"
            ]
            if not calls:
                try:
                    decision = AnalystDecision.model_validate_json(response.text)
                except ValidationError:
                    raise WorkflowFailure("ANALYST_INVALID_OUTPUT") from None
                if decision.outcome == "unsupported":
                    return Outcome("unsupported", UNSUPPORTED)
                if (
                    turn.history
                    and decision.field in (None, "scope")
                    and self.provider.strong_model
                    and not thinking
                ):
                    raise WorkflowFailure("FOLLOWUP_UNRESOLVED")
                return await self.clarify(decision.field or "scope")

            dialogue = []
            for call in calls:
                self.tool_attempts += 1
                if self.tool_attempts > self.limits.tool_attempts:
                    raise WorkflowFailure("TOOL_ATTEMPT_LIMIT")
                if not call.call_id:
                    raise WorkflowFailure("ANALYST_INVALID_OUTPUT")
                try:
                    tool_input = self.validate_call(call)
                    result = await self.run_tool(call.name, tool_input)
                except ValidationError, InvalidToolRequest:
                    await self.event(
                        "tool_rejected", {"code": "INVALID_TOOL_REQUEST"}, "pay_analyst"
                    )
                    if self.provider.strong_model and not thinking:
                        raise WorkflowFailure("ANALYST_INVALID_OUTPUT") from None
                    result = {
                        "error": "Unsupported tool or invalid arguments. Use the provided schema and report options."
                    }
                if isinstance(result, (Evidence, Outcome)):
                    return result
                dialogue.append(
                    Message(
                        "tool",
                        [Content.from_function_result(call.call_id, result=result)],
                    )
                )

    @staticmethod
    def validate_call(call: Content) -> OptionsRequest | SummaryRequest:
        schemas = {
            "get_report_options": OptionsRequest,
            "get_salary_summary": SummaryRequest,
        }
        schema = schemas.get(call.name)
        if schema is None:
            raise InvalidToolRequest("Unknown report tool.")
        if isinstance(call.arguments, str):
            return schema.model_validate_json(call.arguments)
        return schema.model_validate(call.arguments or {})

    async def run_tool(
        self,
        tool_name: str,
        request: OptionsRequest | SummaryRequest,
    ) -> dict | Evidence | Outcome:
        call_id = None
        try:
            async with asyncio.timeout(self.limits.tool_seconds):
                if isinstance(request, SummaryRequest):
                    async with self.database() as database:
                        await validate_report_filters(database, request)
                async with self.database() as database:
                    started = await runs.start_tool(
                        database,
                        self.run_id,
                        self.owner,
                        attempt_number=self.tool_attempts,
                        tool_name=tool_name,
                        arguments=request.model_dump(exclude_none=True),
                    )
                    call_id = started.call_id
                if self.notify is not None:
                    self.notify()
                async with self.database() as database:
                    if isinstance(request, OptionsRequest):
                        options = await report_options(database, request)
                    else:
                        if request.metric == "headcount":
                            report = await get_headcount_report(database, request)
                            cache_status = "bypass"
                        else:
                            report, cache_status = await get_salary_report(database, request, self.report_cache)
        except TimeoutError:
            if call_id is not None:
                async with self.database() as database:
                    await runs.finish_tool(
                        database,
                        self.run_id,
                        self.owner,
                        call_id,
                        status="failed",
                        summary={},
                        error_code="TOOL_TIMEOUT",
                    )
            raise WorkflowFailure("TOOL_TIMEOUT") from None
        if isinstance(request, OptionsRequest):
            counts = {
                key: len(value) for key, value in options.items() if key != "truncated"
            }
            async with self.database() as database:
                await runs.finish_tool(
                    database,
                    self.run_id,
                    self.owner,
                    call_id,
                    status="completed",
                    summary={"counts": counts},
                    result=options,
                )
            return options

        currencies = currencies_in(report)
        summary = {
            "row_count": len(report.rows),
            "currencies": currencies,
            "revision": report.revision,
            "cache_status": cache_status,
        }
        evidence = (
            make_evidence(request, report)
            if len(currencies) <= 1 and len(report.rows) <= MAX_GROUPS
            else None
        )
        if evidence is not None:
            self.report = evidence.card()
        async with self.database() as database:
            await runs.finish_tool(
                database,
                self.run_id,
                self.owner,
                call_id,
                status="completed",
                summary=summary,
                result=self.report or summary,
                report_revision=report.revision,
            )
        if len(currencies) > 1:
            return await self.clarify("currency", currencies, request)
        if evidence is None:
            return await self.clarify("scope")
        await self.event("report_ready", self.report)
        if not evidence.rows:
            return Outcome(
                "completed",
                "No recorded salaries match these filters.",
                {"report": self.report},
            )
        return evidence

    async def clarify(
        self,
        field: str,
        choices: list[str] | None = None,
        report_request: SummaryRequest | None = None,
    ) -> Outcome:
        question = CLARIFICATION_QUESTIONS[field]
        detail = {"field": field, "question": question, "choices": choices or []}
        if report_request is not None:
            detail["report_request"] = report_request.model_dump(exclude_none=True)
        await self.event("clarification", detail, "pay_analyst")
        return Outcome("awaiting_clarification", question, {"clarification": detail})

    async def write(self, evidence: Evidence) -> Outcome:
        await self.event("agent_started", {}, "answer_writer")
        verifier = ClaimVerifier(evidence)
        stream = ClaimsStream()
        lines = []
        invalid = False

        async def verified_delta(delta: str) -> None:
            nonlocal invalid
            if invalid:
                return
            try:
                for claim in stream.feed(delta):
                    line = verifier.check(claim)
                    segment = ("\n" if lines else "") + line
                    await self.event("token", {"text": segment}, "answer_writer")
                    lines.append(line)
            except ValidationError, ValueError:
                invalid = True

        try:
            response = await self.budget.invoke(
                self.writer,
                self.writer.create_session(),
                json.dumps(evidence.card()),
                WriterAnswer,
                verified_delta,
                model_name=self.provider.model,
            )
        except WorkflowFailure:
            await self.event("agent_completed", {"outcome": "failed"}, "answer_writer")
            raise
        try:
            final = WriterAnswer.model_validate_json(response.text)
            valid = (
                not invalid and len(lines) == len(final.claims) and verifier.complete()
            )
            if valid:
                final_verifier = ClaimVerifier(evidence)
                valid = lines == [final_verifier.check(claim) for claim in final.claims]
        except ValidationError, ValueError:
            valid = False
        source = "verified_writer" if valid else "computed"
        await self.event("verification_completed", {"outcome": source})
        await self.event("agent_completed", {"outcome": source}, "answer_writer")
        answer = "\n".join(lines if valid else computed_summary(evidence))
        return Outcome(
            "completed", answer, {"report": self.report, "answer_source": source}
        )
