"""Stop ONLY the PromptCraft Hub server (used by stop_app.bat).

Safety rules:
  * the PID file is trusted only if the process behind it answers /api/health as PromptCraft Hub
    with the very same process id;
  * a graceful stop is requested first (stop file watched by the launcher);
  * only that one verified process may be terminated, and only as a last resort;
  * stale PID files are removed; no other process is ever touched.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import urllib.request

import _bootstrap  # noqa: F401
from app.core.config import get_settings

APP_NAME = "PromptCraft Hub"


def health(base: str) -> dict | None:
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=2) as r:  # noqa: S310 - local URL only
            d = json.loads(r.read().decode("utf-8"))
            return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        return None


def pid_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == 259  # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def main() -> int:
    s = get_settings()
    base = s.base_url
    pid_file = s.pid_file
    stop_file = s.database_path.parent / "promptcraft.stop"
    recorded = None
    if pid_file.exists():
        try:
            recorded = int(pid_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            recorded = None

    info = health(base)
    ours = bool(info and info.get("app") == APP_NAME)
    if not ours:
        if pid_file.exists():
            if recorded and pid_alive(recorded):
                print(f"[WARN] The PID file points to process {recorded}, but it does not answer as {APP_NAME}.")
                print("       To avoid stopping an unrelated program it was NOT terminated. Close the 'PromptCraft Hub' server window instead.")
                return 2
            try:
                pid_file.unlink()
                print("[OK] Removed a stale PID file (the application was not running).")
            except OSError:
                print("[WARN] A stale PID file exists but could not be removed.")
        print(f"[OK] {APP_NAME} is not running. Nothing to stop.")
        return 0

    pid = int(info.get("pid") or 0)
    if recorded and recorded != pid:
        print(f"[WARN] PID file ({recorded}) and the running application ({pid}) differ. Using the verified running instance ({pid}).")
    print(f"[..] Stopping {APP_NAME} (process {pid}) ...")
    try:
        stop_file.write_text("stop", encoding="utf-8")
    except OSError:
        pass
    for _ in range(40):  # up to ~10 s for a graceful stop
        time.sleep(0.25)
        if not (health(base) or {}).get("app") == APP_NAME:
            break
    else:
        # last resort: this one verified process only
        again = health(base)
        if again and again.get("app") == APP_NAME and int(again.get("pid") or 0) == pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1.0)
            except OSError as exc:
                print(f"[ERROR] The process could not be stopped: {exc}")
                return 1
    try:
        stop_file.unlink(missing_ok=True)
    except OSError:
        pass
    if (health(base) or {}).get("app") == APP_NAME:
        print("[ERROR] The application is still running. Close its server window or press Ctrl+C in it.")
        return 1
    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass
    print(f"[OK] {APP_NAME} stopped. Your data was saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
