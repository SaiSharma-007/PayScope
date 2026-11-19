import logging
import traceback
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("payscope")


def configure_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_failure(event: str, exc: Exception, *, request_id: str | None = None) -> None:
    frames = " > ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(exc.__traceback__)
    )
    logger.error(
        "%s request=%s type=%s sqlstate=%s frames=%s",
        event,
        request_id or "-",
        type(exc).__name__,
        getattr(getattr(exc, "orig", exc), "sqlstate", None),
        frames,
    )


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status = None
        logger.info("request.started request=%s method=%s", request_id, scope["method"])

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            log_failure("request.failed", exc, request_id=request_id)
            if status is not None:
                raise RuntimeError("Response failed after sending headers") from None
            response = PlainTextResponse("Internal Server Error", status_code=500)
            await response(scope, receive, send_with_request_id)

        route = getattr(scope.get("route"), "path", "-")
        logger.info(
            "request.completed request=%s method=%s route=%s status=%s duration_ms=%.1f",
            request_id,
            scope["method"],
            route,
            status,
            (perf_counter() - started) * 1000,
        )
