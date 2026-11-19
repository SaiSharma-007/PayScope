from unittest.mock import Mock

import pytest
from sqlalchemy.pool import NullPool

from payscope import database
from payscope.config import Settings


def test_supabase_transaction_pooler_uses_unnamed_statements(monkeypatch):
    create_engine = Mock()
    monkeypatch.setattr(database, "create_async_engine", create_engine)
    settings = Settings(
        database_url=(
            "postgresql://postgres.project:password@aws-0-region.pooler.supabase.com:6543/postgres"
        ),
    )

    database.create_database_engine(settings)

    options = create_engine.call_args.kwargs
    assert options["poolclass"] is NullPool
    assert options["pool_pre_ping"] is False
    connect_args = options["connect_args"]
    assert connect_args["ssl"] == "require"
    assert connect_args["statement_cache_size"] == 0
    assert connect_args["prepared_statement_cache_size"] == 0
    assert connect_args["prepared_statement_name_func"]() == ""


@pytest.mark.parametrize(
    ("host", "port"),
    [("aws-0-region.pooler.supabase.com", 5432), ("127.0.0.1", 6543)],
)
def test_other_postgres_urls_keep_application_pooling(monkeypatch, host, port):
    create_engine = Mock()
    monkeypatch.setattr(database, "create_async_engine", create_engine)
    settings = Settings(database_url=f"postgresql://postgres:password@{host}:{port}/postgres")

    database.create_database_engine(settings)

    options = create_engine.call_args.kwargs
    assert options["poolclass"] is None
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"timeout": 5}
