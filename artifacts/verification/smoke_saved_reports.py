import asyncio
from uuid import uuid4
import sqlalchemy as sa
import httpx2
from payscope.main import app
from payscope.config import SeedSettings
from payscope.seed import DEMO_HR_EMAIL
from payscope.models import hr_users
from payscope.agents import runs
from payscope.agents.schemas import RunRequest
from payscope.agents.runtime import DATABASE_LEASE
from payscope.agents.saved import owned
from fastapi import HTTPException

async def main():
    async with app.router.lifespan_context(app), httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="https://testserver", timeout=120) as client:
        login = await client.post("/api/auth/sign-in", json={"email": DEMO_HR_EMAIL, "password": SeedSettings().demo_hr_password.get_secret_value()})
        assert login.status_code == 200
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        async with app.state.engine.connect() as db:
            user = await db.scalar(sa.select(hr_users.c.id).where(hr_users.c.email == DEMO_HR_EMAIL))
        async with app.state.session_factory() as db:
            run, _ = await runs.admit_run(db, RunRequest(question="Saved report verification fixture"), user_id=user, auth_session_id=None, idempotency_key=uuid4(), runtime_fingerprint="saved-report-test", runtime_limits={}, start_timeout=DATABASE_LEASE)
        token = uuid4()
        async with app.state.session_factory() as db:
            await runs.claim_run(db, run.id, token, DATABASE_LEASE)
        report = {"report_type": "workforce_headcount", "metric": "headcount", "operation": "lowest", "revision": 4, "filters": {"group_by": "country"}, "rows": [{"group_id": "TEST", "evidence_id": str(uuid4()), "group_name": "Fixture group", "headcount": 0, "currency_code": ""}]}
        async with app.state.session_factory() as db:
            await runs.finalize_run(db, run.id, token, status="completed", answer="Fixture group — 0 employees.", payload={"report": report})
        body = {"source_run_id": str(run.id), "title": "Saved report verification fixture", "description": "Independent snapshot", "chart_view": {"measure": "headcount", "sort": "ascending"}}
        assert (await client.post("/api/saved-reports", json=body)).status_code == 403
        saved = await client.post("/api/saved-reports", headers=headers, json=body)
        assert saved.status_code == 200, saved.text
        data = saved.json(); path = "/api/saved-reports/" + data["id"]
        duplicate = await client.post("/api/saved-reports", headers=headers, json=body)
        assert duplicate.json()["id"] == data["id"]
        async with app.state.session_factory() as db:
            try: await owned(db, data["id"], uuid4())
            except HTTPException as error: assert error.status_code == 404
            else: raise AssertionError("Ownership leak")
        assert (await client.delete(f"/api/agent/conversations/{run.conversation_id}", headers=headers)).status_code == 204
        detached = await client.get(path)
        assert detached.status_code == 200 and not detached.json()["source_available"]
        assert detached.json()["report"] == report
        assert (await client.patch(path, headers=headers, json={"title": "Edited fixture", "description": "Still independent"})).status_code == 200
        assert (await client.delete(path, headers=headers)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (await client.post(path + "/restore", headers=headers)).status_code == 204
        assert (await client.get(path)).json()["report"] == report
        assert (await client.delete(path, headers=headers)).status_code == 204
        await client.post("/api/auth/sign-out", headers=headers)
        print("PASS: source ownership, CSRF, duplicate saves, metadata edits, snapshot survival after chat deletion, delete and Undo. Only fixture records changed.")

asyncio.run(main())
