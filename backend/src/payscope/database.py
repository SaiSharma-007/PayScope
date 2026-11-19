from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from payscope.config import Settings


def create_database_engine(settings: Settings, *, pooled: bool = True) -> AsyncEngine:
    url = settings.sqlalchemy_url
    host = (url.host or "").lower()
    transaction_pooler = url.port == 6543 and host.endswith(".pooler.supabase.com")
    connect_args: dict[str, object] = {"timeout": 5}
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
