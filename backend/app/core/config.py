"""Application settings, loaded from environment variables (12-factor).

Every value can be overridden by an environment variable of the same name
(case-insensitive). A local `.env` file is read when present; in containers the
values come from Docker Compose / Kubernetes ConfigMaps and Secrets.
"""

import logging
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

logger = logging.getLogger(__name__)

PLACEHOLDER_PREFIX = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ---- Application ----
    app_name: str = "MediCloud"
    app_env: str = "development"  # development | test | production
    app_version: str = "1.0.0"
    git_commit: str = "local"
    log_level: str = "INFO"
    enable_docs: bool = True
    hospital_timezone: str = "Asia/Kolkata"
    currency: str = "INR"

    # ---- Database: either a full DATABASE_URL or the individual parts ----
    database_url: str | None = None
    postgres_user: str = "medicloud"
    postgres_password: SecretStr = SecretStr("")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medicloud"
    postgres_sslmode: str | None = None  # e.g. "require" for Amazon RDS
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    # ---- Auth ----
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)

    # Comma-separated list of allowed CORS origins (production is same-origin).
    cors_origins: str = ""

    # ---- Demo data (synthetic only) ----
    seed_demo_data: bool = False
    seed_demo_password: SecretStr | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_url(self) -> URL:
        """SQLAlchemy URL using the psycopg 3 driver."""
        if self.database_url:
            url = make_url(self.database_url)
            if url.drivername in ("postgresql", "postgres"):
                url = url.set(drivername="postgresql+psycopg")
            return url
        query = {"sslmode": self.postgres_sslmode} if self.postgres_sslmode else {}
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            query=query,
        )

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        key = self.jwt_secret_key.get_secret_value()
        weak = len(key) < 32 or key.startswith(PLACEHOLDER_PREFIX)
        if weak and self.is_production:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters and not a placeholder in production"
            )
        if weak:
            logger.warning(
                "JWT_SECRET_KEY is weak or a placeholder - acceptable only for local dev"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
