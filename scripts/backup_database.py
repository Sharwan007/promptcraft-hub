"""Create a timestamped, integrity-checked backup of the SQLite database."""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.utilities.file_utils import backup_database


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    try:
        target = backup_database(settings.database_path, settings.backup_path)
    except FileNotFoundError:
        print("[ERROR] The database file does not exist yet. Start the application once (start_app.bat) and try again.")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Backup failed: {exc}")
        print("        Check free disk space and that the backups folder is writable. Technical details are in the log file.")
        return 1
    print("[OK] Database integrity check passed.")
    print(f"[OK] Backup saved: {target}")
    print("     Keep backups private: they contain all of your saved prompts and settings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
