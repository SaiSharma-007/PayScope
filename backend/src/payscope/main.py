from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from payscope.config import Settings
from payscope.database import check_database, create_database_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_database_engine(Settings())
    try:
        await check_database(engine)
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="PayScope", lifespan=lifespan)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    try:
        await check_database(request.app.state.engine)
    except (SQLAlchemyError, OSError):
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}
