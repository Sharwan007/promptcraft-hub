"""Safe file handling helpers."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.exceptions import PayloadTooLarge, ValidationFailed

ALLOWED_IMPORT_EXT = {".json"}


def check_upload(filename: str | None, size: int, max_mb: int) -> str:
    name = Path(filename or "").name
    if not name:
        raise ValidationFailed("Please choose a JSON file to import.")
    if Path(name).suffix.lower() not in ALLOWED_IMPORT_EXT:
        raise ValidationFailed("Only .json files can be imported.", hint="Export the library from Administration to see the expected format.")
    if size > max_mb * 1024 * 1024:
        raise PayloadTooLarge(f"The file is larger than the {max_mb} MB import limit.")
    if size == 0:
        raise ValidationFailed("The selected file is empty.")
    return re.sub(r"[^\w.\- ]", "_", name)[:120]


def parse_json_bytes(data: bytes):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValidationFailed("The file is not valid UTF-8 text.") from exc
    except json.JSONDecodeError as exc:
        raise ValidationFailed(f"The file is not valid JSON (line {exc.lineno}, column {exc.colno}).") from exc


def integrity_check(db_path: Path) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        ok = bool(row) and row[0] == "ok"
        return ok, str(row[0]) if row else "no result"
    except sqlite3.Error as exc:
        return False, str(exc)


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    """Integrity-check then copy the live DB with SQLite's online backup API (never overwrites)."""
    if not db_path.exists():
        raise FileNotFoundError("The database file does not exist yet.")
    ok, detail = integrity_check(db_path)
    if not ok:
        raise RuntimeError(f"Database integrity check failed: {detail}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"promptcraft-backup-{stamp}.db"
    n = 1
    while target.exists():
        target = backup_dir / f"promptcraft-backup-{stamp}-{n}.db"
        n += 1
    src = sqlite3.connect(db_path.as_posix(), timeout=10)
    dst = sqlite3.connect(target.as_posix())
    try:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")  # a single self-contained file, no -wal/-shm companions
    finally:
        dst.close()
        src.close()
    ok2, detail2 = integrity_check(target)
    if not ok2:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Backup verification failed: {detail2}")
    return target


def list_backups(backup_dir: Path) -> list[dict]:
    if not backup_dir.exists():
        return []
    items = []
    for p in sorted(backup_dir.glob("promptcraft-backup-*.db"), reverse=True):
        st = p.stat()
        items.append({"name": p.name, "size_kb": round(st.st_size / 1024, 1),
                      "created": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return items
