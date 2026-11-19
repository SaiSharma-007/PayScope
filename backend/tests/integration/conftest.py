import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from payscope.config import Settings
from payscope.database import create_database_engine


async def require_empty_database() -> None:
    engine = create_database_engine(Settings())
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT to_regnamespace('app') IS NULL")), (
                "TEST_DATABASE_URL must point to a separate, empty PostgreSQL database"
            )
    finally:
        await engine.dispose()


@pytest.fixture
def migrated_database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is unset")
    monkeypatch.setenv("DATABASE_URL", url)
    asyncio.run(require_empty_database())
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    command.upgrade(config, "head")
    try:
        yield config
    finally:
        command.downgrade(config, "base")
