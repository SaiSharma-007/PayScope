import asyncio
import json
import os
import socket
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
import uvicorn
from fastapi import FastAPI
from openai import AsyncOpenAI
from redis.asyncio import Redis

from payscope.agents import api, leases, workflow
from payscope.agents.api import router
from payscope.agents.language import OpenAIProvider
from payscope.agents.leases import Lease, LeaseStore
from payscope.agents.runtime import DEFAULT_LIMITS, AgentRuntime
from payscope.auth.router import SESSION_COOKIE
from payscope.auth.service import PASSWORD_HASHER
from payscope.main import app
from payscope.models import (
    countries,
    currencies,
    departments,
    employee_salaries,
    employees,
    hr_users,
    job_titles,
)

PASSWORD = "test-agent-stream-password"
RUNS = "/api/agent/runs"


@pytest.fixture
def redis_url():
    if not (url := os.environ.get("TEST_REDIS_URL")):
        pytest.skip("TEST_REDIS_URL is unset")
    return url


class ScriptStream(httpx2.AsyncByteStream):
    def __init__(self, frames, gate=None, gate_at=None):
        self.frames = frames
        self.gate = gate
        self.gate_at = gate_at
        self.reached_gate = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aiter__(self):
        for index, frame in enumerate(self.frames):
            if self.gate is not None and index == self.gate_at:
                self.reached_gate.set()
                await self.gate.wait()
            wire = f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n".encode()
            yield wire[:17]
            yield wire[17:]

    async def aclose(self):
        self.closed.set()


def response_frame(event_type, **fields):
    return {"type": event_type, "sequence_number": 1, **fields}


def completion(output):
    usage = {
        "input_tokens": 20,
        "output_tokens": 30,
        "total_tokens": 50,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    response = {
        "id": f"resp_{uuid4().hex}",
        "object": "response",
        "created_at": 1760000000,
        "model": "test-model",
        "status": "completed",
        "output": output,
        "usage": usage,
        "service_tier": "default",
        "conversation": None,
        "error": None,
        "incomplete_details": None,
    }
    return response_frame("response.completed", response=response)


def created(final):
    return response_frame(
        "response.created",
        response=final["response"]
        | {
            "status": "in_progress",
            "output": [],
            "usage": None,
        },
    )


def function_call(name, arguments, gate=None):
    item_id, call_id = f"fc_{uuid4().hex}", f"call_{uuid4().hex}"
    arguments = json.dumps(arguments)
    item = {
        "type": "function_call",
        "id": item_id,
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
    }
    common = {"output_index": 0, "item_id": item_id}
    final = completion([item])
    frames = [
        created(final),
        response_frame(
            "response.output_item.added", output_index=0, item=item | {"arguments": ""}
        ),
        response_frame(
            "response.function_call_arguments.delta", delta=arguments[:5], **common
        ),
        response_frame(
            "response.function_call_arguments.delta", delta=arguments[5:], **common
        ),
        response_frame(
            "response.function_call_arguments.done",
            arguments=arguments,
            name=name,
            **common,
        ),
        response_frame("response.output_item.done", output_index=0, item=item),
        final,
    ]
    return ScriptStream(frames, gate, gate_at=3)


def text_response(text, gate=None):
    item = {
        "type": "message",
        "id": f"msg_{uuid4().hex}",
        "role": "assistant",
        "status": "completed",
        "phase": None,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    common = {
        "item_id": item["id"],
        "output_index": 0,
        "content_index": 0,
        "logprobs": [],
    }
    split = text.find("},") + 1 if "}," in text else len(text) // 2
    final = completion([item])
    frames = [
        created(final),
        response_frame(
            "response.output_item.added", output_index=0, item=item | {"content": []}
        ),
        response_frame(
            "response.content_part.added",
            part={"type": "output_text", "text": "", "annotations": []},
            **common,
        ),
        response_frame("response.output_text.delta", delta=text[:split], **common),
        response_frame("response.output_text.delta", delta=text[split:], **common),
        response_frame("response.output_text.done", text=text, **common),
        response_frame("response.output_item.done", output_index=0, item=item),
        final,
    ]
    return ScriptStream(frames, gate, gate_at=4)


class ModelScript:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.requests = []
        self.streams = []

    async def __call__(self, request):
        data = json.loads(request.content)
        self.requests.append(data)
        step = next(self.steps)
        result = step(data) if callable(step) else step
        if isinstance(result, int):
            return httpx2.Response(
                result,
                json={
                    "error": {
                        "message": "Private provider error",
                        "type": "server_error",
                    }
                },
            )
        self.streams.append(result)
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, stream=result
        )

    def provider(self):
        return OpenAIProvider(
            "test-model",
            AsyncOpenAI(
                api_key="fake-key",
                base_url="https://mock-provider.test/v1",
                max_retries=0,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self)),
            ),
        )


async def seed_fixture():
    async with app.state.engine.begin() as database:
        password_hash = PASSWORD_HASHER.hash(PASSWORD)
        for index, email in enumerate(
            ("owner@example.test", "other@example.test"), start=1
        ):
            await database.execute(
                hr_users.insert().values(
                    id=uuid4(),
                    email=email,
                    display_name=f"HR {index}",
                    password_hash=password_hash,
                )
            )
        await database.execute(
            countries.insert(),
            [
                {"code": "IN", "name": "India"},
                {"code": "US", "name": "United States"},
                {"code": "FR", "name": "France"},
            ],
        )
        await database.execute(
            currencies.insert(),
            [
                {"code": code, "name": name, "minor_units": 2}
                for code, name in (
                    ("INR", "Indian Rupee"),
                    ("USD", "US Dollar"),
                    ("EUR", "Euro"),
                )
            ],
        )
        await database.execute(departments.insert().values(id=1, name="Engineering"))
        await database.execute(
            job_titles.insert(),
            [
                {"id": 1, "name": "Engineer"},
                {"id": 2, "name": "Designer"},
                {"id": 3, "name": "Intern"},
            ],
        )
        for employee_id, (country, job_title, amount, code) in enumerate(
            (
                ("IN", 1, 100, "INR"),
                ("IN", 1, 100, "INR"),
                ("IN", 2, 80, "INR"),
                ("IN", 2, 120, "INR"),
                ("IN", 3, 40, "INR"),
                ("US", 1, 60, "USD"),
            ),
            start=1,
        ):
            await database.execute(
                employees.insert().values(
                    id=employee_id,
                    employee_code=f"EMP-{employee_id}",
                    full_name=f"Dummy Worker {employee_id}",
                    country_code=country,
                    department_id=1,
                    job_title_id=job_title,
                )
            )
            await database.execute(
                employee_salaries.insert().values(
                    employee_id=employee_id,
                    annual_gross_base=amount,
                    currency_code=code,
                    updated_by=await database.scalar(
                        hr_users.select().with_only_columns(hr_users.c.id).limit(1)
                    ),
                )
            )


def writer_answer(body, *, wrong_group=False, gate=None):
    assert not body.get("tools")
    report = next(
        json.loads(content["text"])
        for item in body["input"]
        if item.get("role") == "user"
        for content in item["content"]
        if content.get("type") == "input_text"
    )
    claims = [
        {
            "claim_id": f"c{index}",
            "evidence_id": row["evidence_id"],
            "group": "wrong" if wrong_group else row["group"],
            "currency": report["currency_code"],
            "metric": report["metric"],
            "statement": "tied highest" if report["ranking_evidence_ids"] else "value",
        }
        for index, row in enumerate(report["rows"], start=1)
        if not report["ranking_evidence_ids"]
        or row["evidence_id"] in report["ranking_evidence_ids"]
    ]
    return text_response(json.dumps({"claims": claims}), gate)


def ranking(body):
    assert any(item.get("type") == "function_call_output" for item in body["input"])
    assert (
        body["stream"] and body["store"] is False and body["max_output_tokens"] < 2000
    )
    return function_call(
        "get_salary_summary",
        {
            "country_code": "IN",
            "department_id": 1,
            "currency_code": "INR",
            "group_by": "job_title",
            "metric": "median",
            "operation": "highest",
        },
    )


def sse(body):
    return [
        json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")
    ]


async def log_in(browser, email="owner@example.test"):
    reply = await browser.post(
        "/api/auth/sign-in", json={"email": email, "password": PASSWORD}
    )
    assert reply.status_code == 200
    return {"X-CSRF-Token": reply.json()["csrf_token"]}


async def start(
    browser, csrf, question="How much is median base pay?", *, key=None, **body
):
    return await browser.post(
        RUNS,
        json={"question": question, **body},
        headers=csrf | {"Idempotency-Key": str(key or uuid4())},
    )


def browser(app_instance=app, **options):
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app_instance),
        base_url="https://testserver",
        **options,
    )


def runtime(
    provider, connection, namespace, global_quota=5, user_quota=2, limits=DEFAULT_LIMITS
):
    return AgentRuntime(
        app.state.session_factory,
        provider,
        LeaseStore(connection, namespace, global_quota, user_quota),
        limits,
    )


def independent_app(agent_runtime):
    instance = FastAPI()
    instance.state.agent_runtime = agent_runtime
    instance.state.session_factory = app.state.session_factory
    instance.include_router(router, prefix="/api")
    return instance


async def report_scenarios(redis_url):
    steps = [
        function_call("get_report_options", {}),
        ranking,
        writer_answer,
        function_call(
            "get_salary_summary", {"group_by": "department", "metric": "median"}
        ),
        500,
        500,
        lambda data: writer_answer(data, wrong_group=True),
        function_call(
            "get_salary_summary",
            {"country_code": "FR", "currency_code": "EUR", "metric": "median"},
        ),
        text_response('{"outcome":"unsupported","field":null}'),
        500,
    ]
    script = ModelScript(steps)
    async with (
        app.router.lifespan_context(app),
        Redis.from_url(redis_url) as connection,
        browser() as http,
        browser() as stranger,
    ):
        await seed_fixture()
        active = app.state.agent_runtime = runtime(
            script.provider(), connection, uuid4().hex
        )
        try:
            csrf = await log_in(http)
            other = await log_in(stranger, "other@example.test")
            assert (await start(http, {})).status_code == 403
            key = uuid4()
            reply = await start(
                http,
                csrf,
                "Which Engineering roles in India have the highest median INR base pay?",
                key=key,
            )
            assert reply.status_code == 200, reply.text
            assert reply.headers["x-accel-buffering"] == "no"
            events = sse(reply.text)
            assert events[0]["type"] == "accepted"
            assert events[-1]["payload"]["status"] == "completed", events
            kind = [event["type"] for event in events]
            assert kind.count("tool_started") == kind.count("tool_completed") == 2
            assert kind.count("token") == 2 and kind.index("report_ready") < kind.index(
                "token"
            )
            final = events[-1]["payload"]
            assert final["answer_source"] == "verified_writer"
            assert (
                "Designer" in final["answer"]
                and "Engineer" in final["answer"]
                and "Intern" not in final["answer"]
            )
            card = final["report"]
            assert card["filters"] == {
                "country_code": "IN",
                "department_id": 1,
                "group_by": "job_title",
                "currency_code": "INR",
            }
            live = (
                await http.get("/api/analytics/salary-summary", params=card["filters"])
            ).json()
            assert card["revision"] == live["revision"]
            assert [row["median"] for row in card["rows"]] == [
                row["median"] for row in live["rows"]
            ]
            run = events[0]["run_id"]
            replay = await http.get(
                f"{RUNS}/{run}/events", params={"after": events[3]["sequence"]}
            )
            assert sse(replay.text) == events[4:]
            assert (
                await http.get(f"{RUNS}/{run}/events", params={"after": 10000})
            ).status_code == 422
            repeat = await start(
                http,
                csrf,
                "Which Engineering roles in India have the highest median INR base pay?",
                key=key,
            )
            assert sse(repeat.text) == events and len(script.requests) == 3
            assert (
                await start(http, csrf, "Changed question", key=key)
            ).status_code == 409
            assert (await stranger.get(f"{RUNS}/{run}/events")).status_code == 404
            assert (
                await stranger.post(f"{RUNS}/{run}/cancel", headers=other)
            ).status_code == 404

            clarify = sse(
                (await start(http, csrf, "Compare median pay by department")).text
            )
            assert clarify[-1]["payload"]["status"] == "awaiting_clarification"
            assert clarify[-1]["payload"]["clarification"]["choices"] == ["INR", "USD"]
            linked = {
                "conversation_id": clarify[0]["payload"]["conversation_id"],
                "kind": "clarification",
                "parent_run_id": clarify[0]["run_id"],
            }
            assert (await start(http, csrf, "EUR", **linked)).status_code == 422
            latest = sse((await start(http, csrf, "INR", **linked)).text)
            assert latest[-1]["payload"]["status"] == "failed"
            for expected in ("failed", "completed"):
                retry = {
                    "conversation_id": linked["conversation_id"],
                    "kind": "retry",
                    "parent_run_id": latest[0]["run_id"],
                }
                latest = sse((await start(http, csrf, "INR", **retry)).text)
                assert latest[-1]["payload"]["status"] == expected
                assert (
                    latest[-1]["payload"]["report"]["filters"]["currency_code"] == "INR"
                )
            fallback = latest
            assert fallback[-1]["payload"]["answer_source"] == "computed"
            assert "Engineering" in fallback[-1]["payload"]["answer"]
            assert not any(event["type"] == "token" for event in fallback)

            empty = sse((await start(http, csrf, "Median in France")).text)[-1][
                "payload"
            ]
            assert empty["status"] == "completed" and not empty["report"]["rows"]
            unsupported = sse(
                (await start(http, csrf, "Increase everyone's salary")).text
            )
            assert unsupported[-1]["payload"]["status"] == "unsupported"
            assert not any(event["type"] == "tool_started" for event in unsupported)
            failed = sse((await start(http, csrf, "Median for Engineering")).text)
            assert (
                failed[-2]["type"] == "error"
                and failed[-2]["payload"]["code"] == "MODEL_PROVIDER_FAILED"
            )
            assert failed[-1]["payload"]["status"] == "failed"
            assert "Private provider error" not in json.dumps(failed)
        finally:
            await active.close()


def test_agent_reports_with_fragmented_provider_stream(migrated_database, redis_url):
    asyncio.run(report_scenarios(redis_url))


async def controlled_stream(redis_url):
    gate = asyncio.Event()
    function = function_call("get_salary_summary", {"metric": "median"}, gate)
    script = ModelScript([function])
    async with (
        app.router.lifespan_context(app),
        Redis.from_url(redis_url) as primary,
        Redis.from_url(redis_url) as secondary,
    ):
        await seed_fixture()
        namespace = uuid4().hex
        active = app.state.agent_runtime = runtime(
            script.provider(), primary, namespace, 1, 1
        )
        remote = runtime(script.provider(), secondary, namespace, 1, 1)
        async with (
            browser() as local,
            browser(independent_app(remote)) as second,
            browser() as another,
        ):
            try:
                csrf = await log_in(local)
                other = await log_in(another, "other@example.test")
                second.cookies.update(local.cookies)
                key = uuid4()
                run_request = asyncio.create_task(start(local, csrf, key=key))
                await asyncio.wait_for(function.reached_gate.wait(), timeout=8)
                chat = (await local.get("/api/agent/conversations")).json()["items"][0]
                run_id = chat["active_run_id"]
                assert (
                    await start(local, csrf, conversation_id=chat["id"])
                ).status_code == 409
                assert (await start(local, csrf)).status_code == 429
                assert (await start(another, other)).json()["detail"][
                    "code"
                ] == "AGENT_POOL_BUSY"
                repeat = asyncio.create_task(start(second, csrf, key=key))
                cancelled = await second.post(f"{RUNS}/{run_id}/cancel", headers=csrf)
                assert cancelled.json()["cancel_requested"]
                response, replay = await asyncio.gather(run_request, repeat)
                assert sse(response.text) == sse(replay.text)
                events = sse(response.text)
                assert events[-1]["payload"]["status"] == "cancelled"
                assert not any(event["type"] == "tool_started" for event in events)
                assert function.closed.is_set() and len(script.requests) == 1
            finally:
                await remote.close()
                await active.close()


def test_agent_cross_instance_limits_and_stop(migrated_database, redis_url):
    asyncio.run(controlled_stream(redis_url))


async def wire_stream(redis_url):
    gate = asyncio.Event()
    script = ModelScript(
        [
            function_call(
                "get_salary_summary",
                {
                    "country_code": "IN",
                    "currency_code": "INR",
                    "group_by": "job_title",
                    "operation": "highest",
                    "metric": "median",
                },
            ),
            lambda body: writer_answer(body, gate=gate),
            function_call(
                "get_salary_summary",
                {"country_code": "FR", "currency_code": "EUR", "metric": "median"},
            ),
        ]
    )
    async with (
        app.router.lifespan_context(app),
        Redis.from_url(redis_url) as connection,
        browser() as auth,
        httpx2.AsyncClient(timeout=8) as network,
    ):
        await seed_fixture()
        active = app.state.agent_runtime = runtime(
            script.provider(), connection, uuid4().hex
        )
        csrf = await log_in(auth)
        csrf["Cookie"] = f"{SESSION_COOKIE}={auth.cookies.get(SESSION_COOKIE)}"
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(app, lifespan="off", log_level="warning")
        )
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(15):
                while not server.started:
                    await asyncio.sleep(0.01)
                seen = []
                async with network.stream(
                    "POST",
                    address + RUNS,
                    json={"question": "Highest median salary in India in INR"},
                    headers=csrf | {"Idempotency-Key": str(uuid4())},
                ) as reply:
                    assert reply.status_code == 200
                    async for line in reply.aiter_lines():
                        if line.startswith("data: "):
                            seen.append(json.loads(line[6:]))
                            if seen[-1]["type"] == "token":
                                break
                assert seen[0]["type"] == "accepted" and seen[-1]["type"] == "token"
                assert script.streams[-1].reached_gate.is_set()
                assert not script.streams[-1].closed.is_set()
                run, cursor = seen[0]["run_id"], seen[-1]["sequence"]
                parallel = sse(
                    (await start(auth, csrf, "Median salary in France in EUR")).text
                )
                assert parallel[-1]["run_id"] != run
                assert parallel[-1]["payload"]["report"]["currency_code"] == "EUR"
                assert not gate.is_set()
                async with network.stream(
                    "GET",
                    f"{address}{RUNS}/{run}/events?after={cursor}",
                    headers=csrf,
                ) as resumed:
                    assert resumed.status_code == 200
                    replay = []
                    async for line in resumed.aiter_lines():
                        if line == ": keep-alive":
                            gate.set()
                        if line.startswith("data: "):
                            replay.append(json.loads(line[6:]))
                assert gate.is_set() and replay[0]["sequence"] == cursor + 1
                assert replay[0]["type"] == "token" and replay[-1]["type"] == "final"
                assert replay[-1]["payload"]["answer_source"] == "verified_writer"
                assert replay[-1]["payload"]["report"]["currency_code"] == "INR"
        finally:
            gate.set()
            server.should_exit = True
            await serving
            listener.close()
            await active.close()


def test_agent_stream_delivers_before_final_and_reconnects(
    migrated_database, redis_url, monkeypatch
):
    monkeypatch.setattr(api, "HEARTBEAT_SECONDS", 0.1)
    asyncio.run(wire_stream(redis_url))


async def deadlines(redis_url, monkeypatch):
    wait = asyncio.Event()
    slow = text_response('{"outcome":"unsupported","field":null}', wait)
    slow.gate_at = 3
    script = ModelScript(
        [
            slow,
            function_call("get_salary_summary", {"metric": "median"}),
            function_call("get_report_options", {}),
            function_call("get_salary_summary", {"currency_code": "XXX"}),
            function_call("get_salary_summary", {"currency_code": "XXX"}),
        ]
    )
    async with (
        app.router.lifespan_context(app),
        Redis.from_url(redis_url) as connection,
        browser() as http,
    ):
        await seed_fixture()
        active = app.state.agent_runtime = runtime(
            script.provider(), connection, uuid4().hex
        )
        try:
            csrf = await log_in(http)
            active.limits = replace(
                DEFAULT_LIMITS, first_update_seconds=0.7, run_seconds=4
            )
            events = sse((await start(http, csrf)).text)
            assert slow.closed.is_set() and not any(
                event["type"] == "tool_started" for event in events
            )
            assert (
                events[-1]["payload"]["error"]["code"] == "MODEL_FIRST_UPDATE_TIMEOUT"
            )

            async def slow_report(_database, _filters, _cache):
                await wait.wait()

            with monkeypatch.context() as override:
                override.setattr(workflow, "get_salary_report", slow_report)
                active.limits = replace(DEFAULT_LIMITS, tool_seconds=1)
                events = sse((await start(http, csrf)).text)
                completed = next(
                    event for event in events if event["type"] == "tool_completed"
                )
                assert completed["payload"]["status"] == "failed"
                assert events[-1]["payload"]["error"]["code"] == "TOOL_TIMEOUT"

            active.limits = replace(DEFAULT_LIMITS, model_calls=1)
            events = sse((await start(http, csrf)).text)
            assert events[-1]["payload"]["error"]["code"] == "MODEL_CALL_LIMIT"

            active.limits = replace(DEFAULT_LIMITS, tool_attempts=1)
            events = sse((await start(http, csrf)).text)
            assert any(event["type"] == "tool_rejected" for event in events)
            assert not any(event["type"] == "tool_started" for event in events)
            assert events[-1]["payload"]["error"]["code"] == "TOOL_ATTEMPT_LIMIT"
            assert len(script.requests) == 5
        finally:
            await active.close()


def test_agent_deadlines_and_attempt_limits(migrated_database, redis_url, monkeypatch):
    asyncio.run(deadlines(redis_url, monkeypatch))


async def capacity_lease_checks(redis_url):
    async with Redis.from_url(redis_url) as first, Redis.from_url(redis_url) as second:
        namespace = uuid4().hex
        store_a = LeaseStore(first, namespace, 1, 1)
        store_b = LeaseStore(second, namespace, 1, 1)
        lease = Lease(uuid4(), uuid4(), uuid4())
        another_owner = replace(lease, owner=uuid4())
        other_user = Lease(uuid4(), uuid4(), uuid4())
        assert await store_a.reserve(lease) is None
        assert await store_b.reserve(another_owner) == "ADMISSION_PENDING"
        assert await store_b.reserve(other_user) == "AGENT_POOL_BUSY"
        assert not await store_b.release(another_owner)
        assert await store_a.renew(lease)
        await asyncio.sleep(0.4)
        assert await store_b.reserve(another_owner) is None
        assert not await store_a.renew(lease)
        assert not await store_a.release(lease)
        assert await store_b.release(another_owner)
        assert await store_a.reserve(other_user) is None
        assert await store_a.release(other_user)


def test_capacity_lease_expiry_and_owner_checks(redis_url, monkeypatch):
    monkeypatch.setattr(leases, "LEASE_MS", 250)
    asyncio.run(capacity_lease_checks(redis_url))
