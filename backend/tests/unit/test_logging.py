import logging
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from payscope.logging import RequestLoggingMiddleware, logger


@pytest.fixture
def logged_app(monkeypatch, caplog):
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    monkeypatch.setattr(logger, "propagate", False)
    caplog.set_level(logging.INFO, logger=logger.name)
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    return app, caplog


def test_request_logs_use_route_templates_and_omit_input(logged_app):
    app, caplog = logged_app

    @app.post("/employees/{employee_id}")
    async def update_employee():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post(
            "/employees/private-employee-id?token=private-query-value",
            headers={"Authorization": "Bearer private-auth-token", "X-Request-ID": "client-id"},
            json={"salary": "private-body-value"},
        )

    request_id = response.headers["x-request-id"]
    assert response.status_code == 200
    assert UUID(request_id).version == 4
    assert f"request.started request={request_id}" in caplog.text
    assert f"request.completed request={request_id}" in caplog.text
    assert "route=/employees/{employee_id} status=200 duration_ms=" in caplog.text
    assert "private-" not in caplog.text
    assert "client-id" not in caplog.text


def test_unhandled_failure_has_a_request_id_and_safe_diagnostics(logged_app):
    app, caplog = logged_app

    @app.get("/failure")
    async def fail():
        raise RuntimeError("private-exception-details")

    with TestClient(app) as client:
        response = client.get("/failure")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert f"request.failed request={response.headers['x-request-id']}" in caplog.text
    assert "type=RuntimeError" in caplog.text
    assert ":fail" in caplog.text
    assert "private-exception-details" not in caplog.text


def test_stream_failure_does_not_reraise_sensitive_details(logged_app):
    app, caplog = logged_app

    async def chunks():
        yield b"first chunk"
        raise RuntimeError("private-stream-details")

    @app.get("/stream")
    async def stream():
        return StreamingResponse(chunks())

    with TestClient(app) as client:
        with pytest.raises(RuntimeError, match="Response failed after sending headers") as error:
            client.get("/stream")

    assert error.value.__suppress_context__
    assert "request.failed" in caplog.text
    assert "request.completed" not in caplog.text
    assert "private-stream-details" not in caplog.text
