import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from payscope.agents import runs
from payscope.agents.leases import Lease
from payscope.agents.runtime import AgentRuntime, session_is_live
from payscope.agents.workflow import Outcome, TurnInput


def test_ownership_monitor_runs_while_workflow_startup_is_blocked():
    async def check():
        runtime = AgentRuntime(None, None, None)
        startup = asyncio.Event()
        monitored = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_start(*_):
            startup.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def monitor(*_):
            await startup.wait()
            monitored.set()
            return Outcome("interrupted")

        runtime.run_workflow = slow_start
        runtime.watch = monitor
        async with asyncio.timeout(1):
            outcome = await runtime.execute_claimed(None, None, TurnInput("Pay?"))
        assert monitored.is_set() and cancelled.is_set()
        assert outcome.status == "interrupted"

    asyncio.run(check())


def test_monitor_renews_before_checking_authentication_and_cancellation():
    async def check():
        lease = Lease(uuid4(), uuid4(), uuid4())
        runtime = AgentRuntime(None, None, SimpleNamespace(renew=AsyncMock(return_value=True)))
        run = SimpleNamespace(id=uuid4(), user_id=lease.user_id, auth_session_id=uuid4())
        operations = []

        async def stored(operation, *_):
            operations.append(operation)
            if operation is runs.renew_run:
                return SimpleNamespace(cancel_requested_at=None)
            return False

        runtime.stored = stored
        outcome = await runtime.watch(run, lease)
        assert outcome.status == "cancelled"
        assert operations == [runs.renew_run, session_is_live, runs.request_cancel]
        runtime.leases.renew.assert_awaited_once_with(lease)

    asyncio.run(check())


def test_monitor_stops_when_database_ownership_cannot_be_renewed():
    async def check():
        lease = Lease(uuid4(), uuid4(), uuid4())
        runtime = AgentRuntime(None, None, SimpleNamespace(renew=AsyncMock(return_value=True)))
        runtime.stored = AsyncMock(return_value=None)
        outcome = await runtime.watch(SimpleNamespace(id=uuid4()), lease)
        assert outcome.status == "interrupted"
        runtime.stored.assert_awaited_once()

    asyncio.run(check())


def test_lease_client_has_its_own_timeout_and_is_closed(monkeypatch):
    from unittest.mock import Mock

    from payscope.agents import runtime as module

    client = SimpleNamespace(aclose=AsyncMock())
    create_client = Mock(return_value=client)
    monkeypatch.setattr(module.Redis, "from_url", create_client)
    cache = SimpleNamespace(redis=object(), prefix="test")
    settings = SimpleNamespace(
        redis_url=SimpleNamespace(get_secret_value=lambda: "redis://localhost"),
        agent_user_quota=2,
        agent_global_quota=5,
        agent_openai_api_key=None,
    )
    runtime = AgentRuntime.from_settings(None, cache, settings)
    assert runtime.leases.redis is client
    assert runtime.leases.redis is not cache.redis
    assert create_client.call_args.kwargs["socket_timeout"] == 3
    asyncio.run(runtime.close())
    client.aclose.assert_awaited_once()
