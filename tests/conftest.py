"""Test configuration: every test run uses its own temporary database, backups and logs.

The environment is prepared BEFORE the application is imported, so the real
data/promptcraft.db can never be opened or overwritten by the tests.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="promptcraft-tests-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(TMP / 'test.db').as_posix()}",
    "BACKUP_DIRECTORY": str(TMP / "backups"),
    "LOG_DIRECTORY": str(TMP / "logs"),
    "APP_ENV": "test",
    "SECRET_KEY": "test-secret-key-not-used-anywhere-else-0123456789",
    "AUTO_OPEN_BROWSER": "false",
    "PORT": "8000",
    "HOST": "127.0.0.1",
    "PIN_MAX_ATTEMPTS": "5",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

assert str(TMP) in str(get_settings().database_path), "tests must use a temporary database"

from app.main import app  # noqa: E402

ADMIN_PIN = "654321"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class Client(TestClient):
    """TestClient that sends the CSRF header automatically, like the browser JavaScript does."""

    def request(self, method, url, *args, **kwargs):  # type: ignore[override]
        if method.upper() in UNSAFE:
            headers = dict(kwargs.get("headers") or {})
            if "X-CSRF-Token" not in headers and not kwargs.pop("no_csrf", False):
                token = self.cookies.get("pch_csrf")
                if not token:
                    super().request("GET", "/api/health")
                    token = self.cookies.get("pch_csrf")
                headers["X-CSRF-Token"] = token or ""
            kwargs["headers"] = headers
        kwargs.pop("no_csrf", None)
        return super().request(method, url, *args, **kwargs)


@pytest.fixture(scope="session")
def client():
    with Client(app, base_url="http://127.0.0.1") as c:  # context manager runs start-up: migrations + seed on the temp DB
        yield c


@pytest.fixture(scope="session")
def admin(client):
    """A second browser session that is signed in as administrator."""
    c = Client(app, base_url="http://127.0.0.1")
    status = c.get("/api/admin/status").json()
    if not status["configured"]:
        r = c.post("/api/admin/setup", json={"pin": ADMIN_PIN, "confirm": ADMIN_PIN})
        assert r.status_code == 200, r.text
    else:
        assert c.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    return c


@pytest.fixture()
def db():
    from app.database.connection import get_session_factory
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def prompt_id(client) -> int:
    return client.get("/api/prompts?page_size=1").json()["items"][0]["id"]
