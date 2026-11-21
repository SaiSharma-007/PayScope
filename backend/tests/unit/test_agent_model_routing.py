import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from payscope.agents.language import RunLimits, WorkflowFailure
from payscope.agents.workflow import Outcome, PayWorkflow, TurnInput


def test_invalid_bolt_output_escalates_once_with_the_same_run_budget():
    bolt, super_model, writer = object(), object(), object()
    provider = SimpleNamespace(
        model="bolt",
        strong_model="super",
        chat_completions=True,
        agents=Mock(side_effect=[(bolt, writer), (super_model, writer)]),
    )
    flow = PayWorkflow(None, provider, uuid4(), uuid4(), {}, RunLimits())
    flow.run_tool = AsyncMock(
        return_value={"countries": [{"code": "IN", "name": "India"}]}
    )
    answer = Outcome("completed", "Verified")
    flow.select_with = AsyncMock(
        side_effect=[WorkflowFailure("ANALYST_INVALID_OUTPUT"), answer]
    )
    flow.event = AsyncMock()
    turn = TurnInput("Compare fictional pay")

    assert asyncio.run(flow.select_report(turn)) == answer
    assert flow.select_with.await_count == 2
    fast_turn = flow.select_with.await_args_list[0].args[0]
    assert '"code": "IN"' in fast_turn.question
    assert turn.question in fast_turn.question
    flow.select_with.assert_awaited_with(fast_turn, super_model, thinking=True)
    flow.run_tool.assert_awaited_once()
    flow.event.assert_awaited_once_with(
        "model_escalated",
        {
            "from_model": "bolt",
            "to_model": "super",
            "reason": "ANALYST_INVALID_OUTPUT",
        },
        "pay_analyst",
    )
