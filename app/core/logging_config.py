"""Structured logging. Prompt content, PINs and session values are never logged."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import Settings

_CONFIGURED = False
FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(settings: Settings) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings.log_path.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    formatter = logging.Formatter(FORMAT)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)
    try:
        fh = RotatingFileHandler(
            settings.log_path / "promptcraft.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError:
        logging.getLogger("promptcraft").warning("Log file could not be opened; console logging only.")
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # we log requests ourselves (no query strings)
    _CONFIGURED = True


def preview_for_log(text: str, settings: Settings) -> str:
    """Return prompt text for logs only if explicitly enabled; otherwise just its size."""
    if settings.enable_prompt_content_logging:
        return text[:200]
    return f"<{len(text or '')} chars redacted>"
