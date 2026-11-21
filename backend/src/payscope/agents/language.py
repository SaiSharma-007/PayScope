import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from agent_framework import (
    Agent,
    AgentResponse,
    AgentResponseUpdate,
    AgentSession,
    FunctionTool,
    Message,
)
from agent_framework.exceptions import ChatClientException
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from payscope.agents.evidence import OptionsRequest, SummaryRequest


@dataclass(frozen=True)
class RunLimits:
    run_seconds: float = 60
    first_update_seconds: float = 15
    tool_seconds: float = 10
    model_calls: int = 4
    tool_attempts: int = 3
    output_tokens: int = 2000


class WorkflowFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OpenAIProvider:
    def __init__(
        self,
        model: str,
        client: AsyncOpenAI,
        *,
        chat_completions: bool = False,
        strong_model: str | None = None,
    ) -> None:
        self.model = model
        self.strong_model = strong_model
        self.chat_completions = chat_completions
        self.client = client
        connector = OpenAIChatCompletionClient if chat_completions else OpenAIChatClient
        self.chat = connector(model=model, async_client=client)
        self.strong_chat = (
            connector(model=strong_model, async_client=client) if strong_model else None
        )
        for chat in (self.chat, self.strong_chat):
            if chat is None:
                continue
            chat.function_invocation_configuration.update(
                {
                    "max_iterations": 1,
                    "terminate_on_unknown_calls": True,
                }
            )

    def agents(
        self, prompts: dict[str, str], *, strong: bool = False
    ) -> tuple[Agent, Agent]:
        analyst = Agent(
            client=self.strong_chat if strong else self.chat,
            name="pay_analyst",
            instructions=prompts["pay_analyst"]
            + "\nWorkforce headcount is also supported by get_salary_summary with metric=headcount. It counts ALL employees, including those without salaries. Never ask for or filter currency for headcount. For least/fewest use operation=lowest; most use highest. Preserve the requested grouping and global scope."
            + (
                "\nThe application already looked up reference values for this question. "
                "Use the supplied codes and IDs and call get_salary_summary directly. If a report tool does not apply, "
                'return only JSON with outcome ("clarify" or "unsupported") and field (null, '
                '"currency", "country", "department", "job_title", "grouping", "metric", or "scope").'
                if self.chat_completions
                else ""
            ),
            tools=[
                *(
                    []
                    if self.chat_completions
                    else [
                        FunctionTool(
                            name="get_report_options",
                            input_model=OptionsRequest,
                            description="Resolve allowed country and currency codes and department and job title IDs.",
                        )
                    ]
                ),
                FunctionTool(
                    name="get_salary_summary",
                    input_model=SummaryRequest,
                    description=(
                        "Query current annual gross base pay. Set metric to median or average when requested. "
                        "Omit group_by for a single aggregate. For comparisons, group_by is country, "
                        "department, or job_title. Set operation to summary, highest, or lowest."
                        " For workforce counts set metric=headcount, omit currency_code, and use lowest/highest for fewest/most employees."
                    ),
                ),
            ],
        )
        writer = Agent(
            client=self.chat,
            name="answer_writer",
            instructions=prompts["answer_writer"] + "\nFor report_type workforce_headcount, count all employees, use only metric=headcount, and set claim currency to the empty string. Never mention currency or recorded salaries. Preserve lowest/highest and all ties.",
        )
        return analyst, writer

    async def close(self) -> None:
        await self.client.close()


class ModelBudget:
    def __init__(self, limits: RunLimits, on_event=None) -> None:
        self.limits = limits
        self.calls = 0
        self.remaining = limits.output_tokens
        self.on_event = on_event

    async def invoke(
        self,
        agent: Agent,
        session: AgentSession,
        messages: str | list[Message],
        response_format: type[BaseModel],
        on_text: Callable[[str], Awaitable[None]] | None = None,
        *,
        thinking: bool = False,
        model_name: str | None = None,
    ) -> AgentResponse:
        if self.calls >= self.limits.model_calls:
            raise WorkflowFailure("MODEL_CALL_LIMIT")
        # The Responses API requires a minimum max_output_tokens of 16.
        if self.remaining < 16:
            raise WorkflowFailure("MODEL_OUTPUT_LIMIT")
        self.calls += 1
        options = {
            "max_tokens": self.remaining,
            "allow_multiple_tool_calls": False,
            "store": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.__name__,
                    "strict": True,
                    "schema": response_format.model_json_schema(),
                },
            },
        }
        if isinstance(agent.client, OpenAIChatCompletionClient):
            options.pop("store")
            if agent.name == "pay_analyst":
                options.pop("response_format")
            options["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": thinking}
            }
        streamed_ids = set()

        async def forward_text(update: AgentResponseUpdate) -> None:
            if on_text is None:
                return
            for index, content in enumerate(update.contents):
                if content.type != "text" or not content.text:
                    continue
                if (content.additional_properties or {}).get("core", {}).get(
                    "model_output_kind"
                ) == "refusal":
                    continue
                identity = (update.message_id, index)
                if content.merge_mode == "replace" and identity in streamed_ids:
                    continue
                await on_text(content.text)
                streamed_ids.add(identity)

        started = perf_counter()
        first_update_ms = None
        try:
            async with agent.run(
                messages, session=session, options=options, stream=True
            ) as stream:
                try:
                    async with asyncio.timeout(self.limits.first_update_seconds):
                        first = await anext(aiter(stream), None)
                        while first is not None and not any(
                            item.type in ("function_call", "error")
                            or (item.type == "text" and item.text)
                            for item in first.contents
                        ):
                            first = await anext(stream, None)
                except TimeoutError:
                    raise WorkflowFailure("MODEL_FIRST_UPDATE_TIMEOUT") from None
                if first is not None:
                    first_update_ms = round((perf_counter() - started) * 1000)
                    await forward_text(first)
                async for update in stream:
                    await forward_text(update)
                response = await stream.get_final_response()
        except OpenAIError, ChatClientException:
            raise WorkflowFailure("MODEL_PROVIDER_FAILED") from None

        usage = response.usage_details or {}
        tokens = usage.get("output_token_count")
        if self.on_event is not None:
            await self.on_event(
                "model_completed",
                {
                    "model": model_name,
                    "call_number": self.calls,
                    "duration_ms": round((perf_counter() - started) * 1000),
                    "first_update_ms": first_update_ms,
                    "input_tokens": usage.get("input_token_count"),
                    "output_tokens": tokens,
                },
                agent.name,
            )
        self.remaining -= (
            tokens if tokens is not None and tokens > 0 else self.remaining
        )
        if self.remaining < 0:
            raise WorkflowFailure("MODEL_OUTPUT_LIMIT")
        return response
