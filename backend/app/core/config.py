"""Application settings, read from environment variables prefixed with FLAKERADAR_."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLAKERADAR_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://flakeradar:flakeradar@localhost:5432/flakeradar"
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "ingest"

    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = 10 * 1024 * 1024

    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
