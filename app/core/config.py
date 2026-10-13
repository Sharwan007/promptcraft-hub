"""Application configuration.

Settings are read from environment variables and an optional local ``.env`` file.
Environment variables always win over the file, which is how the automated tests
point the app at a separate database.
"""
from __future__ import annotations

import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BASE_DIR / "app"
ENV_FILE = BASE_DIR / ".env"

logger = logging.getLogger("promptcraft.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "PromptCraft Hub"
    app_version: str = "1.0.0"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite:///./data/promptcraft.db"
    log_level: str = "INFO"
    log_directory: str = "./logs"
    enable_prompt_content_logging: bool = False
    local_admin_mode: bool = True
    auto_open_browser: bool = True
    session_expiry_minutes: int = 60
    max_import_file_mb: int = 5
    backup_directory: str = "./backups"
    secret_key: str = ""
    cookie_secure: bool = False
    allowed_hosts: str = "127.0.0.1,localhost,[::1],testserver"
    cors_origins: str = ""
    max_request_body_mb: int = 8
    pin_max_attempts: int = 5
    pin_lock_minutes: int = 5

    @field_validator("log_level")
    @classmethod
    def _level(cls, v: str) -> str:
        v = (v or "INFO").upper()
        return v if v in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    # ---- derived paths -------------------------------------------------
    def resolve_path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def database_path(self) -> Path:
        url = self.database_url
        if not url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// database URLs are supported by this local version.")
        raw = url[len("sqlite:///"):]
        return self.resolve_path(raw)

    @property
    def sqlalchemy_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def backup_path(self) -> Path:
        return self.resolve_path(self.backup_directory)

    @property
    def log_path(self) -> Path:
        return self.resolve_path(self.log_directory)

    @property
    def pid_file(self) -> Path:
        return self.database_path.parent / "promptcraft.pid"

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [h.strip() for h in self.cors_origins.split(",") if h.strip()]

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def ensure_directories(self) -> None:
        for p in (self.database_path.parent, self.backup_path, self.log_path):
            p.mkdir(parents=True, exist_ok=True)


def ensure_secret_key(settings: Settings) -> Settings:
    """Generate a local secret on first start and store it in the git-ignored .env file."""
    if settings.secret_key:
        return settings
    key = secrets.token_urlsafe(48)
    try:
        lines: list[str] = []
        if ENV_FILE.exists():
            lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        lines = [ln for ln in lines if not ln.strip().upper().startswith("SECRET_KEY=")]
        lines.append(f"SECRET_KEY={key}")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("A new local secret key was generated and stored in the local .env file.")
    except OSError:
        # Read-only folder: fall back to a per-process key (sessions reset on restart).
        logger.warning("Could not write .env; using a temporary in-memory secret key.")
    settings.secret_key = key
    os.environ.setdefault("SECRET_KEY", key)
    return settings


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return ensure_secret_key(settings)
