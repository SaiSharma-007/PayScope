import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from payscope.analytics.cache import create_report_cache
from payscope.analytics.router import router as analytics_router
from payscope.auth.router import router as auth_router
from payscope.config import Settings
from payscope.database import check_database, create_database_engine
from payscope.employees.router import router as employees_router
from payscope.logging import RequestLoggingMiddleware, configure_logging, log_failure, logger
from payscope.salaries.router import router as salaries_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logging.getLogger("uvicorn.access").disabled = True
    try:
        settings = Settings()
        engine = create_database_engine(settings)
        try:
            await check_database(engine)
            app.state.settings = settings
            app.state.engine = engine
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            report_cache = create_report_cache(settings)
            app.state.report_cache = report_cache
            try:
                logger.info("application.started")
                yield
            finally:
                if report_cache is not None:
                    await report_cache.redis.aclose()
        finally:
            await engine.dispose()
    except Exception as exc:
        log_failure("application.failed", exc)
        raise RuntimeError("Application lifecycle failed") from None
    logger.info("application.stopped")


app = FastAPI(title="PayScope", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
api = APIRouter(prefix="/api")
api.include_router(analytics_router)
api.include_router(auth_router)
api.include_router(employees_router)
api.include_router(salaries_router)
app.include_router(api)


@app.exception_handler(RequestValidationError)
async def validation_failure(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse(
        status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"}
    )


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    try:
        await check_database(request.app.state.engine)
    except (SQLAlchemyError, OSError) as exc:
        log_failure("database.unavailable", exc, request_id=request.state.request_id)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}
