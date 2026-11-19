import asyncio

from alembic import context

from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.models import metadata


def include_name(name, type_, parent_names):
    return type_ != "schema" or name == metadata.schema


def migrate(**connection_options):
    context.configure(
        **connection_options,
        target_metadata=metadata,
        include_schemas=True,
        include_name=include_name,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def migrate_online():
    engine = create_database_engine(Settings(), pooled=False)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(lambda sync_connection: migrate(connection=sync_connection))
    finally:
        await engine.dispose()


if context.is_offline_mode():
    migrate(url=Settings().sqlalchemy_url, literal_binds=True)
else:
    asyncio.run(migrate_online())
