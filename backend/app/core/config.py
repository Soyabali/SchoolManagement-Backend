from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _to_psycopg(url: str) -> str:
    """Neon hands out `postgresql://` URLs; SQLAlchemy needs the psycopg 3 dialect."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    raise ValueError("DATABASE_URL must be a PostgreSQL connection string")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "School Management System"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = Field(default_factory=list)

    # SecretStr keeps credentials out of repr() and logs.
    DATABASE_URL: SecretStr
    DATABASE_URL_UNPOOLED: SecretStr | None = None
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 300

    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @property
    def sqlalchemy_database_url(self) -> str:
        return _to_psycopg(self.DATABASE_URL.get_secret_value())

    @property
    def sqlalchemy_migration_url(self) -> str:
        # Migrations go over the direct (non-pooled) endpoint: PgBouncer in
        # transaction mode does not play well with DDL and advisory locks.
        url = self.DATABASE_URL_UNPOOLED or self.DATABASE_URL
        return _to_psycopg(url.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
