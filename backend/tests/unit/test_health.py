from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

import payscope.main


def test_health_reports_a_database_outage_and_disposes_engine(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://127.0.0.1/payscope")
    database_check = AsyncMock(side_effect=[None, ConnectionRefusedError("connection details")])
    dispose = AsyncMock()
    monkeypatch.setattr(payscope.main, "check_database", database_check)
    monkeypatch.setattr(AsyncEngine, "dispose", dispose)

    with TestClient(payscope.main.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert response.headers["x-request-id"]
    assert database_check.await_count == 2
    dispose.assert_awaited_once()
