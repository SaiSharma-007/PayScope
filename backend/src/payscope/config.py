from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    redis_url: SecretStr | None = None
    session_ttl_seconds: int = Field(default=28_800, ge=60, le=86_400)

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value():
            return None
        try:
            url = urlsplit(value.get_secret_value())
            if url.scheme in {"redis", "rediss"} and url.hostname and url.port != 0:
                return value
        except ValueError:
            pass
        raise ValueError("REDIS_URL must be a redis:// or rediss:// connection URL")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL") from None
        if (
            url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}
            or not url.database
        ):
            raise ValueError("DATABASE_URL must identify a PostgreSQL database")
        return value

    @property
    def sqlalchemy_url(self) -> URL:
        url = make_url(self.database_url.get_secret_value()).set(drivername="postgresql+asyncpg")
        if "sslmode" in url.query:
            url = url.difference_update_query(["sslmode"]).update_query_dict(
                {"ssl": url.query["sslmode"]}
            )
        return url


class SeedSettings(Settings):
    demo_hr_password: SecretStr = Field(min_length=12)
