import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx2
import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DBAPIError

from payscope.agents import runs
from payscope.agents.schemas import RunRequest
from payscope.auth.service import PASSWORD_HASHER
from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.main import app
from payscope.models import (
    agent_conversations,
    agent_prompt_versions,
    agent_runs,
    agent_tool_calls,
    auth_sessions,
    hr_users,
)
from payscope.seed import DEMO_HR_EMAIL, seed_database, seed_hr_user

PROMPTS = "/api/admin/agent-prompts"
ANALYST = f"{PROMPTS}/pay_analyst"
CHATS = "/api/agent/conversations"
PASSWORD = "agents-integration-password"
REGULAR_EMAIL = "regular@example.test"
TIMEOUT = timedelta(seconds=30)


def client():
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://testserver"
    )


async def sign_in(http, email):
    login = await http.post(
        "/api/auth/sign-in", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return login.json()


async def seed_legacy_users():
    engine = create_database_engine(Settings())
    try:
        async with engine.begin() as database:
            await database.execute(
                sa.text(
                    "INSERT INTO app.hr_users (id, email, display_name, password_hash)"
                    " VALUES (:id, :email, 'HR', :password_hash)"
                ),
                [
                    {
                        "id": uuid4(),
                        "email": email,
                        "password_hash": PASSWORD_HASHER.hash(PASSWORD),
                    }
                    for email in (DEMO_HR_EMAIL, REGULAR_EMAIL)
                ],
            )
    finally:
        await engine.dispose()


async def prompt_admin_checks():
    async with app.router.lifespan_context(app), client() as admin, client() as regular:
        assert (await regular.get(PROMPTS)).status_code == 401
        regular_session = await sign_in(regular, REGULAR_EMAIL)
        assert not regular_session["user"]["manage_agent_prompts"]
        assert (await regular.get(PROMPTS)).json()["detail"][
            "code"
        ] == "PROMPT_CATALOG_FORBIDDEN"
        denied = await regular.put(
            f"{ANALYST}/draft",
            json={"body": "Restricted", "expected_revision": 0},
            headers={"X-CSRF-Token": regular_session["csrf_token"]},
        )
        assert denied.status_code == 403

        original_session = await sign_in(admin, DEMO_HR_EMAIL)
        assert not original_session["user"]["manage_agent_prompts"]
        await seed_database(app.state.engine, "a-different-password")
        assert (await admin.get("/api/auth/session")).json()["user"][
            "manage_agent_prompts"
        ]
        headers = {"X-CSRF-Token": original_session["csrf_token"]}
        catalog = (await admin.get(PROMPTS)).json()
        assert {
            entry["agent_key"]: entry["active"]["version"] for entry in catalog
        } == {
            "pay_analyst": 1,
            "answer_writer": 1,
        }
        assert all(
            entry["draft"] is None and "body" not in entry["active"]
            for entry in catalog
        )
        initial = (await admin.get(f"{ANALYST}/versions/1")).json()
        assert "get_salary_summary" in initial["body"]
        assert initial["author_id"] is None
        assert (await admin.get(f"{ANALYST}/versions/2")).status_code == 404
        assert (
            await admin.post(
                f"{ANALYST}/publish", headers=headers, json={"expected_revision": 0}
            )
        ).json()["detail"]["code"] == ("PROMPT_DRAFT_REQUIRED")

        edit = {
            "body": "First line\nSecond line",
            "change_note": "Clarified ranking",
            "expected_revision": 0,
        }
        no_csrf = await admin.put(f"{ANALYST}/draft", json=edit)
        assert no_csrf.status_code == 403
        assert no_csrf.json()["detail"]["code"] == "INVALID_CSRF_TOKEN"
        for invalid in ("\n\t ", "sensitive\x00prompt", "x" * 12001):
            rejected = await admin.put(
                f"{ANALYST}/draft", json=edit | {"body": invalid}, headers=headers
            )
            assert rejected.status_code == 422
            assert "input" not in rejected.json()["detail"][0]

        draft_results = await asyncio.gather(
            *(
                admin.put(f"{ANALYST}/draft", json=edit, headers=headers)
                for _ in range(2)
            )
        )
        assert sorted(response.status_code for response in draft_results) == [200, 409]
        draft = next(
            response.json() for response in draft_results if response.is_success
        )
        assert draft["edit_revision"] == 1 and draft["active"]["version"] == 1
        assert draft["draft"]["body"] == edit["body"]
        assert (
            "body"
            not in next(
                entry
                for entry in (await admin.get(PROMPTS)).json()
                if entry["agent_key"] == "pay_analyst"
            )["draft"]
        )

        publish_results = await asyncio.gather(
            *(
                admin.post(
                    f"{ANALYST}/publish", json={"expected_revision": 1}, headers=headers
                )
                for _ in range(2)
            )
        )
        assert sorted(response.status_code for response in publish_results) == [
            200,
            409,
        ]
        conflict = next(
            response.json()["detail"]
            for response in publish_results
            if not response.is_success
        )
        assert (
            conflict["code"] == "PROMPT_CHANGED" and conflict["current_revision"] == 2
        )
        published = (await admin.get(f"{ANALYST}/versions/2")).json()
        assert published["body"] == edit["body"]
        assert (
            published["author_id"]
            == published["published_by"]
            == original_session["user"]["id"]
        )
        assert (await admin.get(ANALYST)).json()["draft"] is None

        await seed_database(app.state.engine, "a-different-password")
        async with app.state.engine.begin() as database:
            version_one = agent_prompt_versions.c.version == 1
            for statement in (
                agent_prompt_versions.update()
                .where(version_one)
                .values(body="Changed directly"),
                agent_prompt_versions.delete().where(version_one),
            ):
                with pytest.raises(DBAPIError) as error:
                    async with database.begin_nested():
                        await database.execute(statement)
                assert error.value.orig.sqlstate == "23514"
        assert (await admin.get(ANALYST)).json()["active"]["version"] == 2
        assert (await sign_in(admin, DEMO_HR_EMAIL))["user"]["manage_agent_prompts"]

        restored = await admin.post(
            f"{ANALYST}/draft/restore",
            json={"version": 1, "expected_revision": 2},
            headers=headers,
        )
        # Signing in again replaces the session cookie and its CSRF token.
        assert restored.status_code == 403
        headers = {
            "X-CSRF-Token": (await admin.get("/api/auth/session")).json()["csrf_token"]
        }
        restored = await admin.post(
            f"{ANALYST}/draft/restore",
            json={"version": 1, "expected_revision": 2},
            headers=headers,
        )
        assert restored.json()["draft"]["body"] == initial["body"]
        assert restored.json()["active"]["version"] == 2
        assert (
            await admin.post(
                f"{ANALYST}/publish", json={"expected_revision": 3}, headers=headers
            )
        ).json()["active"]["version"] == 3
        assert (await admin.get(f"{ANALYST}/versions/3")).json()["body"] == initial[
            "body"
        ]
        page = (await admin.get(f"{ANALYST}/versions?limit=1")).json()
        assert page["next_before_version"] == 3 and page["items"][0]["version"] == 3
        assert "body" not in page["items"][0]
        second_page = (await admin.get(f"{ANALYST}/versions?before_version=3")).json()
        assert [item["version"] for item in second_page["items"]] == [2, 1]


def test_prompt_catalog_upgrade_and_permissions(migrated_database):
    command.downgrade(migrated_database, "0003")
    asyncio.run(seed_legacy_users())
    command.upgrade(migrated_database, "head")
    asyncio.run(prompt_admin_checks())


async def stored(operation, *args, **kwargs):
    async with app.state.session_factory() as database:
        return await operation(database, *args, **kwargs)


async def run_storage_checks():
    await seed_legacy_users()
    async with app.router.lifespan_context(app), client() as admin, client() as regular:
        async with app.state.engine.begin() as database:
            user_id = await seed_hr_user(database, PASSWORD)
            outsider = await database.scalar(
                sa.select(hr_users.c.id).where(hr_users.c.email == REGULAR_EMAIL)
            )
        admin_session = await sign_in(admin, DEMO_HR_EMAIL)
        await sign_in(regular, REGULAR_EMAIL)
        async with app.state.engine.connect() as database:
            session_id = await database.scalar(
                sa.select(auth_sessions.c.id).where(auth_sessions.c.user_id == user_id)
            )

        async def admit(request, key, owner=user_id, session=session_id):
            return await stored(
                runs.admit_run,
                request,
                user_id=owner,
                auth_session_id=session,
                idempotency_key=key,
                runtime_fingerprint="test-runtime",
                runtime_limits={"max_tool_calls": 3},
                start_timeout=TIMEOUT,
            )

        key, execution_owner = uuid4(), uuid4()
        request = RunRequest(question="What is median Engineering pay in India?")
        (run, created), (duplicate, duplicate_created) = await asyncio.gather(
            admit(request, key), admit(request, key)
        )
        assert run.id == duplicate.id and {created, duplicate_created} == {True, False}
        assert (
            run.last_event_sequence == 1
            and run.pay_analyst_version == run.answer_writer_version == 1
        )
        assert (await stored(runs.replay_events, run.id, user_id))[
            0
        ].event_type == "accepted"
        with pytest.raises(runs.RunConflict, match="IDEMPOTENCY_CONFLICT"):
            await admit(RunRequest(question="Another question"), key)
        with pytest.raises(runs.RunConflict, match="CONVERSATION_NOT_FOUND"):
            await admit(
                RunRequest(conversation_id=run.conversation_id, question="Secret"),
                uuid4(),
                outsider,
                None,
            )
        with pytest.raises(runs.RunConflict, match="RUN_NOT_FOUND"):
            await stored(runs.replay_events, run.id, outsider)
        assert (await regular.get(CHATS)).json()["items"] == []
        assert (await regular.get(f"{CHATS}/{run.conversation_id}")).status_code == 404

        pinned_v1 = await stored(runs.pinned_prompts, run)
        headers = {"X-CSRF-Token": admin_session["csrf_token"]}
        draft = await admin.put(
            f"{ANALYST}/draft",
            headers=headers,
            json={"body": "New analyst v2", "expected_revision": 0},
        )
        assert draft.status_code == 200, draft.text
        published = await admin.post(
            f"{ANALYST}/publish", headers=headers, json={"expected_revision": 1}
        )
        assert published.status_code == 200, published.text
        new_run, _ = await admit(RunRequest(question="Separate chat"), uuid4())
        assert new_run.conversation_id != run.conversation_id
        assert new_run.pay_analyst_version == 2 and new_run.answer_writer_version == 1
        assert (await stored(runs.pinned_prompts, new_run))[
            "pay_analyst"
        ] == "New analyst v2"
        replay, created = await admit(request, key)
        assert not created and await stored(runs.pinned_prompts, replay) == pinned_v1
        async with app.state.engine.begin() as database:
            assert (
                await database.scalar(
                    sa.select(sa.func.count()).select_from(agent_conversations)
                )
                == 2
            )
            with pytest.raises(DBAPIError) as error:
                async with database.begin_nested():
                    await database.execute(
                        agent_runs.update()
                        .where(agent_runs.c.id == run.id)
                        .values(answer_writer_version=2)
                    )
            assert error.value.orig.sqlstate == "23503"

        assert (
            await stored(runs.claim_run, run.id, execution_owner, TIMEOUT)
        ).status == "running"
        assert await stored(runs.claim_run, run.id, uuid4(), TIMEOUT) is None
        assert await stored(runs.renew_run, run.id, uuid4(), TIMEOUT) is None
        assert (
            await stored(runs.renew_run, run.id, execution_owner, TIMEOUT) is not None
        )
        with pytest.raises(runs.RunConflict, match="EXECUTION_LEASE_LOST"):
            await stored(runs.append_event, run.id, uuid4(), "run_started", {})
        started = await stored(
            runs.start_tool,
            run.id,
            execution_owner,
            attempt_number=1,
            tool_name="get_salary_summary",
            arguments={"country_code": "IN"},
        )
        report = {"revision": 12, "total": "100.00"}
        completed = await stored(
            runs.finish_tool,
            run.id,
            execution_owner,
            started.call_id,
            status="completed",
            summary={"groups": 1},
            result=report,
            report_revision=12,
        )
        assert (
            completed.call_id == started.call_id
            and completed.payload["duration_ms"] >= 0
        )
        async with app.state.engine.connect() as database:
            result = (
                (await database.execute(agent_tool_calls.select())).mappings().one()
            )
            assert result.report_revision == 12 and result.result == report
        await stored(runs.append_event, run.id, execution_owner, "report_ready", report)
        await stored(
            runs.append_event, run.id, execution_owner, "token", {"text": "Median is "}
        )

        chat_response = await admin.get(f"{CHATS}/{run.conversation_id}")
        assert chat_response.status_code == 200, chat_response.text
        assert chat_response.json()["active_run_id"] == str(run.id)
        assert (
            chat_response.json()["turns"][0]["messages"][0]["text"] == request.question
        )
        assert (
            await stored(runs.request_cancel, run.id, user_id)
        ).cancel_requested_at is not None

        final, repeated_final = await asyncio.gather(
            *(
                stored(
                    runs.finalize_run,
                    run.id,
                    execution_owner,
                    status="completed",
                    answer="Completed claim",
                    payload={"report": report},
                )
                for _ in range(2)
            )
        )
        assert final.event_id == repeated_final.event_id and final.payload == {
            "status": "cancelled",
            "answer": "Median is ",
            "is_partial": True,
            "report": report,
        }
        saved_events = await stored(runs.replay_events, run.id, user_id, after=1)
        assert [event.event_type for event in saved_events] == [
            "tool_started",
            "tool_completed",
            "report_ready",
            "token",
            "final",
        ]
        assert [event.sequence for event in saved_events] == list(range(2, 7))

        follow_up = RunRequest(
            conversation_id=run.conversation_id, question="Follow-up"
        )
        outcomes = await asyncio.gather(
            admit(follow_up, uuid4()),
            admit(follow_up, uuid4()),
            return_exceptions=True,
        )
        next_run = next(
            outcome[0] for outcome in outcomes if isinstance(outcome, tuple)
        )
        conflict = next(
            outcome for outcome in outcomes if isinstance(outcome, runs.RunConflict)
        )
        assert conflict.code == "CONVERSATION_BUSY" and conflict.run_id == next_run.id
        assert next_run.turn_number == 2
        history = (await admin.get(f"{CHATS}/{run.conversation_id}?limit=1")).json()
        assert history["active_run_id"] == str(next_run.id)
        assert (
            history["next_before_turn"] == 2 and history["turns"][0]["turn_number"] == 2
        )
        older = (await admin.get(f"{CHATS}/{run.conversation_id}?before_turn=2")).json()
        assert [message["role"] for message in older["turns"][0]["messages"]] == [
            "user",
            "assistant",
        ]
        assert older["turns"][0]["messages"][1]["is_partial"]
        assert (await admin.get(f"{CHATS}/{run.conversation_id}?before_turn=1")).json()[
            "turns"
        ] == []
        assert (await admin.get(f"{CHATS}?limit=1")).json()["next_offset"] == 1

        claim = await stored(runs.claim_run, next_run.id, execution_owner, TIMEOUT)
        assert claim is not None
        cancel, finalized = await asyncio.gather(
            stored(runs.request_cancel, next_run.id, user_id),
            stored(
                runs.finalize_run,
                next_run.id,
                execution_owner,
                status="completed",
                answer="Complete",
                payload={},
            ),
        )
        assert finalized.payload["status"] == (
            "cancelled" if cancel.cancel_requested_at else "completed"
        )
        assert (
            sum(
                event.event_type == "final"
                for event in await stored(runs.replay_events, next_run.id, user_id)
            )
            == 1
        )

        assert (
            await stored(runs.claim_run, new_run.id, execution_owner, TIMEOUT)
            is not None
        )
        async with app.state.engine.begin() as database:
            await database.execute(
                agent_runs.update()
                .where(agent_runs.c.id == new_run.id)
                .values(
                    execution_lease_expires_at=sa.func.clock_timestamp() - TIMEOUT,
                )
            )
        with pytest.raises(runs.RunConflict, match="EXECUTION_LEASE_LOST"):
            await stored(
                runs.append_event, new_run.id, execution_owner, "run_started", {}
            )
        interruption = await stored(runs.interrupt_expired_run, new_run.id)
        assert interruption.payload["status"] == "interrupted"
        assert await stored(runs.interrupt_expired_run, new_run.id) is None

        with pytest.raises(runs.RunConflict, match="INVALID_RUN_SOURCE"):
            await admit(
                RunRequest(
                    conversation_id=new_run.conversation_id,
                    question="Retry",
                    kind="retry",
                    parent_run_id=next_run.id,
                ),
                uuid4(),
            )
        retry, _ = await admit(
            RunRequest(
                conversation_id=new_run.conversation_id,
                question="Separate chat",
                kind="retry",
                parent_run_id=new_run.id,
            ),
            uuid4(),
        )
        assert (
            await stored(runs.claim_run, retry.id, execution_owner, TIMEOUT) is not None
        )
        choices = {"question": "Which currency?", "choices": ["EUR", "INR"]}
        await stored(
            runs.finalize_run,
            retry.id,
            execution_owner,
            status="awaiting_clarification",
            answer=None,
            payload={"clarification": choices},
        )
        retry_chat = (await admin.get(f"{CHATS}/{retry.conversation_id}")).json()
        assert (
            retry_chat["turns"][-1]["messages"][-1]["structured_content"][
                "clarification"
            ]
            == choices
        )
        clarified, _ = await admit(
            RunRequest(
                conversation_id=retry.conversation_id,
                question="INR",
                kind="clarification",
                parent_run_id=retry.id,
            ),
            uuid4(),
        )
        assert clarified.turn_number == 3 and clarified.parent_run_id == retry.id


def test_owned_run_storage_and_concurrency(migrated_database):
    asyncio.run(run_storage_checks())


async def deletion_checks():
    await seed_legacy_users()
    async with app.router.lifespan_context(app), client() as admin, client() as regular:
        async with app.state.engine.begin() as database:
            user_id = await seed_hr_user(database, PASSWORD)
        signed_in = await sign_in(admin, DEMO_HR_EMAIL)
        await sign_in(regular, REGULAR_EMAIL)
        headers = {"X-CSRF-Token": signed_in["csrf_token"]}
        key = uuid4()
        question = RunRequest(question="Deletion fixture")

        async def admit(request, request_key):
            return await stored(
                runs.admit_run, request, user_id=user_id, auth_session_id=None,
                idempotency_key=request_key, runtime_fingerprint="deletion-test",
                runtime_limits={}, start_timeout=TIMEOUT,
            )

        run, _ = await admit(question, key)
        path = f"{CHATS}/{run.conversation_id}"
        assert (await admin.delete(path)).status_code == 403
        assert (await regular.delete(path, headers={"X-CSRF-Token": (await sign_in(regular, REGULAR_EMAIL))["csrf_token"]})).status_code == 404
        assert (await admin.delete(path, headers=headers)).status_code == 409
        owner = uuid4()
        await stored(runs.claim_run, run.id, owner, TIMEOUT)
        await stored(runs.finalize_run, run.id, owner, status="unsupported", answer="Fixture", payload={})
        assert (await admin.delete(path, headers=headers)).status_code == 204
        assert (await admin.delete(path, headers=headers)).status_code == 204
        assert (await admin.get(path)).status_code == 404
        assert not any(item["id"] == str(run.conversation_id) for item in (await admin.get(CHATS)).json()["items"])
        assert (await admin.get(f"/api/agent/runs/{run.id}/events")).status_code == 404
        with pytest.raises(runs.RunConflict, match="CONVERSATION_NOT_FOUND"):
            await stored(runs.find_admitted_run, question, user_id, key)
        with pytest.raises(runs.RunConflict, match="CONVERSATION_NOT_FOUND"):
            await admit(RunRequest(conversation_id=run.conversation_id, question="Hidden"), uuid4())
        assert (await admin.post(path + "/restore", headers=headers)).status_code == 204
        assert (await admin.get(path)).status_code == 200
        assert (await admin.get(path)).json()["turns"][0]["messages"][-1]["text"] == "Fixture"


def test_chat_deletion_is_owned_reversible_and_rejects_active_runs(migrated_database):
    asyncio.run(deletion_checks())
