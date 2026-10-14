"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "railway-ai-platform"
    environment: Literal["development", "testing", "production"] = "development"
    database_url: str
    redis_url: str
    jwt_secret: SecretStr | None = None
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
