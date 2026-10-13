"""Smoke test for a prepared PromptCraft Hub installation.

Read-only checks against the real local database (nothing is modified, no PID file is written):
structure, database existence and integrity, seed counts, health, home page, library, one prompt, static assets, templates.
Exit code 0 = every check passed.
"""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401
from _bootstrap import ROOT

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((bool(ok), name))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def main() -> int:
    required = ["app/main.py", "app/api/prompts.py", "app/database/models.py", "app/services/scoring_service.py", "app/templates/base.html",
                "app/static/css/base.css", "app/static/js/app.js", "app/seed/prompts.json", "requirements.txt", "start_app.bat", "README.md"]
    missing = [p for p in required if not (ROOT / p).exists()]
    check("Application structure exists", not missing, ", ".join(missing))
    forbidden = [p for p in ("package.json", "node_modules", "frontend", "vite.config.js") if (ROOT / p).exists()]
    check("No Node.js project files present", not forbidden, ", ".join(forbidden))

    from app.core.config import get_settings
    from app.database.initialization import initialize_database, table_counts
    from app.utilities.file_utils import integrity_check

    settings = get_settings()
    try:
        initialize_database()  # idempotent: creates the database on a fresh install, never overwrites data
    except Exception as exc:  # noqa: BLE001
        check("Database can be opened", False, exc.__class__.__name__)
        return 1
    check("Database exists", settings.database_path.exists(), str(settings.database_path))
    ok, detail = integrity_check(settings.database_path)
    check("Database integrity check passes", ok, detail)
    counts = table_counts()
    check("Seed data is loaded", counts["prompts"] > 0, str(counts))
    check("At least 75 prompts exist", counts["prompts"] >= 75, str(counts["prompts"]))
    check("At least 15 Before & After examples exist", counts["examples"] >= 15, str(counts["examples"]))
    check("At least 16 learning modules exist", counts["learning_modules"] >= 16, str(counts["learning_modules"]))
    check("At least 20 glossary terms exist", counts["glossary_terms"] >= 20, str(counts["glossary_terms"]))
    check("At least 8 featured prompts exist", counts["featured"] >= 8, str(counts["featured"]))

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, base_url="http://127.0.0.1")  # no lifespan: no PID file, no start-up side effects
    r = client.get("/api/health")
    check("Health endpoint responds", r.status_code == 200 and r.json().get("status") == "ok")
    r = client.get("/")
    check("Home page responds", r.status_code == 200 and "PromptCraft Hub" in r.text)
    check("Templates can render (dashboard)", "Start here" in r.text)
    r = client.get("/prompts")
    check("Prompt Library responds", r.status_code == 200 and "Prompt Library" in r.text)
    r = client.get("/api/prompts?page_size=1")
    items = r.json().get("items", []) if r.status_code == 200 else []
    check("Prompt list API returns prompts", bool(items))
    if items:
        r = client.get(f"/api/prompts/{items[0]['id']}")
        check("At least one prompt can be retrieved", r.status_code == 200 and bool(r.json().get("full_prompt")))
    r = client.get("/static/css/base.css")
    check("Static CSS loads", r.status_code == 200 and "box-sizing" in r.text)
    r = client.get("/static/js/app.js")
    check("Static JavaScript loads", r.status_code == 200 and "PCH" in r.text)
    for page in ("/builder", "/improver", "/diagnostic", "/before-after", "/learning", "/privacy"):
        r = client.get(page)
        check(f"Page renders: {page}", r.status_code == 200)

    failed = [n for ok, n in results if not ok]
    print()
    print(f"Smoke test: {len(results) - len(failed)} passed, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
