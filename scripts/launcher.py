"""PromptCraft Hub launcher (used by start_app.bat).

 1. initialises the database (migrations + seed data for empty tables only)
 2. checks port 8000: reuses a running PromptCraft Hub, refuses to touch other programs
 3. starts Uvicorn in this single process
 4. waits for /api/health, then opens the default browser

Exit codes: 0 ok / already running, 3 database problem, 4 port used by another program, 5 server failed to start.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import _bootstrap  # noqa: F401
from app.core.config import get_settings
from app.core.logging_config import setup_logging

APP_NAME = "PromptCraft Hub"


def health(base_url: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(base_url + "/api/health", timeout=timeout) as resp:  # noqa: S310 - local URL only
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def open_browser(url: str) -> None:
    try:
        if not webbrowser.open(url):
            raise RuntimeError("no browser")
    except Exception:  # noqa: BLE001
        print(f"[INFO] The browser could not be opened automatically. Open this address yourself: {url}")


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    settings.ensure_directories()
    base = settings.base_url
    log_file = settings.log_path / "promptcraft.log"
    print("=" * 62)
    print(f" {APP_NAME} {settings.app_version}  -  Build better prompts. Get better results.")
    print("=" * 62)

    # ---- already running? -------------------------------------------------
    if port_in_use(settings.host, settings.port):
        info = health(base)
        if info and info.get("app") == APP_NAME:
            print(f"[OK] {APP_NAME} is already running (process {info.get('pid')}). Opening it in your browser instead of starting a second copy.")
            print(f"     Address: {base}")
            if settings.auto_open_browser:
                open_browser(base)
            return 0
        print(f"[ERROR] Port {settings.port} is already used by another program, so {APP_NAME} cannot start.")
        print("        Nothing was stopped or changed. Choose one of these:")
        print(f"          1. Close the program that uses port {settings.port}, then run start_app.bat again.")
        print(f"          2. Or set a different port: add the line PORT=8010 to the file named .env in the project folder (create it if needed) and start again.")
        return 4

    # ---- database ---------------------------------------------------------
    try:
        from app.database.initialization import initialize_database, table_counts
        result = initialize_database()
        counts = table_counts()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] The database could not be prepared ({exc.__class__.__name__}).")
        print("        If the message mentions 'locked', close other programs that use data\\promptcraft.db and try again.")
        print(f"        Technical details: {log_file}")
        return 3
    loaded = {k: v for k, v in result["seeded"].items() if v}
    print(f"[OK] Database ready (schema v{result['schema_version']}). " + (f"Seed data loaded: {loaded}." if loaded else "Existing data kept."))
    print(f"[OK] {counts['prompts']} prompts, {counts['learning_modules']} lessons, {counts['examples']} before/after examples.")

    # ---- server -----------------------------------------------------------
    import uvicorn

    stop_file = settings.database_path.parent / "promptcraft.stop"
    try:
        stop_file.unlink(missing_ok=True)
    except OSError:
        pass
    config = uvicorn.Config("app.main:app", host=settings.host, port=settings.port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    def watcher() -> None:
        deadline = time.time() + 60
        ready = False
        while time.time() < deadline and not server.should_exit:
            info = health(base, 1.5)
            if info and info.get("status") in ("ok", "degraded"):
                ready = True
                break
            time.sleep(0.4)
        if ready:
            print()
            print(f"[OK] {APP_NAME} is running at:  {base}")
            print(f"     API documentation:        {base}/docs")
            print(f"     Log file:                 {log_file}")
            print("     Keep this window open while you use the app. Press Ctrl+C here (or run stop_app.bat) to stop it.")
            if settings.auto_open_browser:
                open_browser(base)
        elif not server.should_exit:
            print(f"[ERROR] The application did not answer within 60 seconds. See the log file: {log_file}")
        while not server.should_exit:
            if stop_file.exists():
                try:
                    stop_file.unlink()
                except OSError:
                    pass
                print("[INFO] Stop requested. Shutting down...")
                server.should_exit = True
            time.sleep(0.5)

    threading.Thread(target=watcher, daemon=True, name="pch-watcher").start()
    print(f"[..] Starting the server on {base} ...")
    try:
        server.run()
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(f"[ERROR] The server could not start. Port {settings.port} may have been taken by another program in the meantime.")
            print(f"        Technical details: {log_file}")
            return 5
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] The server stopped unexpectedly ({exc.__class__.__name__}). Technical details: {log_file}")
        return 5
    if not server.started:
        print(f"[ERROR] The server could not start. Technical details: {log_file}")
        return 5
    print(f"[OK] {APP_NAME} stopped. Your data is saved in {settings.database_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
