import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from payscope.config import Settings
from payscope.database import check_database, create_database_engine
from payscope.logging import RequestLoggingMiddleware, configure_logging, log_failure, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logging.getLogger("uvicorn.access").disabled = True
    try:
        engine = create_database_engine(Settings())
        try:
            await check_database(engine)
            app.state.engine = engine
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            logger.info("application.started")
            yield
        finally:
            await engine.dispose()
    except Exception as exc:
        log_failure("application.failed", exc)
        raise RuntimeError("Application lifecycle failed") from None
    logger.info("application.stopped")


app = FastAPI(title="PayScope", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    try:
        await check_database(request.app.state.engine)
    except (SQLAlchemyError, OSError) as exc:
        log_failure("database.unavailable", exc, request_id=request.state.request_id)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}
