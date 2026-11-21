"""Check reversible deletion using only a newly created fixture conversation."""
import asyncio
from uuid import uuid4

import httpx2
import sqlalchemy as sa
from fastapi import HTTPException

from payscope.agents.history import set_deleted
from payscope.agents import runs
from payscope.agents.schemas import RunRequest
from payscope.agents.runtime import DATABASE_LEASE
from payscope.config import SeedSettings
from payscope.main import app
from payscope.models import hr_users
from payscope.seed import DEMO_HR_EMAIL


async def main():
    settings = SeedSettings()
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://testserver"
    ) as client:
        login = await client.post("/api/auth/sign-in", json={"email": DEMO_HR_EMAIL, "password": settings.demo_hr_password.get_secret_value()})
        assert login.status_code == 200
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        async with app.state.engine.connect() as connection:
            owner = await connection.scalar(sa.select(hr_users.c.id).where(hr_users.c.email == DEMO_HR_EMAIL))
        async with app.state.session_factory() as database:
            run, _ = await runs.admit_run(
                database, RunRequest(question="Reversible deletion verification fixture"),
                user_id=owner, auth_session_id=None, idempotency_key=uuid4(),
                runtime_fingerprint="chat-deletion-smoke", runtime_limits={}, start_timeout=DATABASE_LEASE,
            )
        path = f"/api/agent/conversations/{run.conversation_id}"
        assert (await client.delete(path)).status_code == 403
        assert (await client.delete(path, headers=headers)).status_code == 409
        async with app.state.session_factory() as database:
            try:
                await set_deleted(database, run.conversation_id, uuid4(), True)
            except HTTPException as error:
                assert error.status_code == 404
            else:
                raise AssertionError("Another owner must not delete the fixture")
        execution_owner = uuid4()
        async with app.state.session_factory() as database:
            assert await runs.claim_run(database, run.id, execution_owner, DATABASE_LEASE) is not None
        async with app.state.session_factory() as database:
            await runs.finalize_run(database, run.id, execution_owner, status="unsupported", answer="Deletion verification fixture", payload={})
        assert (await client.delete(path, headers=headers)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (await client.get(f"/api/agent/runs/{run.id}/events")).status_code == 404
        async with app.state.session_factory() as database:
            try:
                await runs.owned_run(database, run.id, owner)
            except runs.RunConflict:
                pass
            else:
                raise AssertionError("Deleted run must not be readable")
        assert (await client.post(path + "/restore", headers=headers)).status_code == 204
        restored = await client.get(path)
        assert restored.status_code == 200 and restored.json()["turns"]
        assert (await client.delete(path, headers=headers)).status_code == 204
        await client.post("/api/auth/sign-out", headers=headers)
        print("PASS: CSRF, owner isolation, active-run conflict, hidden reads, and Undo; fixture left soft-deleted.")


if __name__ == "__main__":
    asyncio.run(main())
