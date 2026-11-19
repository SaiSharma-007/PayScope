import pytest
from pydantic import ValidationError

from payscope.config import SeedSettings, Settings


def test_postgres_url_accepts_tls_mode():
    settings = Settings(database_url="postgres://user:password@db/payscope?sslmode=require")

    assert settings.sqlalchemy_url.drivername == "postgresql+asyncpg"
    assert settings.sqlalchemy_url.database == "payscope"
    assert settings.sqlalchemy_url.query == {"ssl": "require"}


def test_invalid_database_url_hides_credentials():
    with pytest.raises(ValidationError) as error:
        Settings(database_url="mysql://user:private-password@db/payscope")

    assert "must identify a PostgreSQL database" in str(error.value)
    assert "private-password" not in str(error.value)


def test_seed_requires_a_password(monkeypatch):
    monkeypatch.delenv("DEMO_HR_PASSWORD", raising=False)
    with pytest.raises(ValidationError, match="demo_hr_password"):
        SeedSettings(_env_file=None, database_url="postgresql://db/payscope")
