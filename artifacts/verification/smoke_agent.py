"""Exercise the updated loopback API using configured demo credentials, never logging secrets."""
import asyncio
import json
from time import perf_counter
from uuid import uuid4

import httpx2

from payscope.auth.router import SESSION_COOKIE
from payscope.config import SeedSettings
from payscope.seed import DEMO_HR_EMAIL


async def main():
    settings = SeedSettings()
    async with httpx2.AsyncClient(base_url="http://127.0.0.1:8001", timeout=100) as client:
        response = await client.post(
            "/api/auth/sign-in",
            json={"email": DEMO_HR_EMAIL, "password": settings.demo_hr_password.get_secret_value()},
        )
        assert response.status_code == 200, f"Sign-in returned {response.status_code}"
        headers = {
            "Cookie": f"{SESSION_COOKIE}={response.cookies[SESSION_COOKIE]}",
            "X-CSRF-Token": response.json()["csrf_token"],
            "Idempotency-Key": str(uuid4()),
        }
        started = perf_counter()
        events = []
        async with client.stream(
            "POST", "/api/agent/runs", headers=headers,
            json={"question": "What is the average annual base pay in Germany in EUR?"},
        ) as stream:
            assert stream.status_code == 200, f"Run returned {stream.status_code}"
            async for line in stream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                events.append(event)
                print(json.dumps({"event": event["type"], "elapsed_s": round(perf_counter() - started, 2)}), flush=True)
        assert events and events[-1]["type"] == "final"
        final = events[-1]["payload"]
        print(json.dumps({"status": final["status"], "answer_source": final.get("answer_source")}), flush=True)
        assert final["status"] == "completed"
        chat_id = events[0]["payload"]["conversation_id"]
        saved = await client.get(f"/api/agent/conversations/{chat_id}", headers=headers)
        saved.raise_for_status()
        trace = saved.json()["turns"][-1]["events"]
        assert any(item["type"] == "verification_completed" for item in trace)
        assert any(item["type"] == "model_completed" for item in trace)
        print(json.dumps({"saved_activity_events": len(trace), "chat_id": chat_id}), flush=True)
        await client.post("/api/auth/sign-out", headers=headers)


if __name__ == "__main__":
    asyncio.run(main())
