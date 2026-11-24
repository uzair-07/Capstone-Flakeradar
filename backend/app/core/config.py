"""Application settings, read from environment variables prefixed with FLAKERADAR_."""

import secrets
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

    # Sessions. Set FLAKERADAR_SECRET_KEY in production; without it a random key is used and
    # everyone is logged out when the API restarts.
    secret_key: str = ""
    session_days: int = 7
    cookie_secure: bool = False  # set true when served over HTTPS
    allow_registration: bool = True

    def model_post_init(self, __context: object) -> None:
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    return Settings()
