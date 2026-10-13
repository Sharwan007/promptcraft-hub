"""Environment checks used by the batch files.

  python scripts/check_environment.py --deps     exit 0 when every Python package is importable
  python scripts/check_environment.py --config   health-oriented configuration check (human readable)
"""
from __future__ import annotations

import importlib
import sys

import _bootstrap  # noqa: F401
from _bootstrap import ROOT

REQUIRED = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "pydantic_settings", "jinja2", "multipart", "itsdangerous", "dotenv"]
TEST_ONLY = ["pytest", "httpx"]


def missing(modules: list[str]) -> list[str]:
    out = []
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception:  # noqa: BLE001
            out.append(m)
    return out


def deps(include_tests: bool) -> int:
    gone = missing(REQUIRED + (TEST_ONLY if include_tests else []))
    if gone:
        print("Missing packages: " + ", ".join(gone))
        return 1
    return 0


def config() -> int:
    problems = 0

    def ok(msg: str) -> None:
        print(f"[OK]   {msg}")

    def bad(msg: str) -> None:
        nonlocal problems
        problems += 1
        print(f"[FAIL] {msg}")

    if sys.version_info >= (3, 11):
        ok(f"Python {sys.version.split()[0]}")
    else:
        bad(f"Python {sys.version.split()[0]} is too old (3.11 or later is required)")
    gone = missing(REQUIRED)
    ok("All required Python packages are installed") if not gone else bad("Missing packages: " + ", ".join(gone))
    for rel in ("app/main.py", "app/templates/base.html", "app/static/css/base.css", "app/static/js/app.js", "app/seed/prompts.json"):
        ok(f"Found {rel}") if (ROOT / rel).exists() else bad(f"Missing file: {rel}")
    if not gone:
        try:
            from app.core.config import get_settings
            s = get_settings()
            s.ensure_directories()
            ok(f"Configuration loaded (host {s.host}, port {s.port})")
            for label, path in (("data", s.database_path.parent), ("backups", s.backup_path), ("logs", s.log_path)):
                probe = path / ".write_test"
                try:
                    probe.write_text("x")
                    probe.unlink()
                    ok(f"The {label} folder is writable: {path}")
                except OSError:
                    bad(f"The {label} folder is not writable: {path}. Move the project to a folder you own (for example Documents).")
            if s.host not in ("127.0.0.1", "localhost"):
                print(f"[WARN] HOST is {s.host}: the app may be reachable from other computers. Use 127.0.0.1 for local-only access.")
        except Exception as exc:  # noqa: BLE001
            bad(f"Configuration could not be loaded: {exc.__class__.__name__}")
    print("Configuration check passed." if not problems else f"Configuration check found {problems} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    if "--deps" in sys.argv:
        sys.exit(deps("--tests" in sys.argv))
    if "--config" in sys.argv:
        sys.exit(config())
    print(__doc__)
    sys.exit(2)
