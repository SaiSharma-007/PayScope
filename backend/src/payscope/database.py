from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import func, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from payscope.config import Settings
from payscope.models import report_state


def create_database_engine(settings: Settings, *, pooled: bool = True) -> AsyncEngine:
    url = settings.sqlalchemy_url
    host = (url.host or "").lower()
    transaction_pooler = url.port == 6543 and host.endswith(".pooler.supabase.com")
    connect_args: dict[str, object] = {"timeout": 5}
    if host.endswith(".pooler.supabase.com"):
        connect_args["ssl"] = url.query.get("ssl", "require")
    if transaction_pooler:
        pooled = False
        connect_args.update(
            ssl=url.query.get("ssl", "require"),
            statement_cache_size=0,
            prepared_statement_cache_size=0,
            # SQLAlchemy still calls prepare(), so use an unnamed statement.
            prepared_statement_name_func=lambda: "",
        )

    return create_async_engine(
        url,
        poolclass=None if pooled else NullPool,
        pool_pre_ping=pooled,
        connect_args=connect_args,
    )


async def check_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


async def advance_report_revision(database: AsyncConnection | AsyncSession) -> None:
    result = await database.execute(
        update(report_state)
        .where(report_state.c.id == 1)
        .values(revision=report_state.c.revision + 1, updated_at=func.clock_timestamp())
        .returning(report_state.c.revision)
    )
    result.scalar_one()
