"""Library import / export and database backup (administrator only)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_admin
from app.core.exceptions import AppError, ValidationFailed
from app.services import export_service, prompt_service
from app.utilities.file_utils import backup_database, check_upload, list_backups

logger = logging.getLogger("promptcraft.import_export")
router = APIRouter(prefix="/api", tags=["Import, export and backup"])


async def _read_limited(file: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    return data


@router.get("/export", summary="Export the whole prompt library as JSON (admin)")
def export_library(db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Response:
    try:
        data = export_service.export_library(db)
    except Exception as exc:
        logger.exception("Library export failed")
        raise AppError("The library could not be exported.", hint="Check the log file for technical details.") from exc
    prompt_service.record_event(db, "export_library")
    return Response(data, media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="promptcraft-library.json"'})


@router.post("/import", summary="Validate (preview) or import prompts from a JSON file (admin)")
async def import_prompts(file: UploadFile = File(...), action: str = Form("preview"), duplicates: str = Form("skip"),
                         on_error: str = Form("abort"), db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> JSONResponse:
    settings = get_settings()
    data = await _read_limited(file, settings.max_import_file_mb)
    name = check_upload(file.filename, len(data), settings.max_import_file_mb)
    if action not in ("preview", "commit"):
        raise ValidationFailed("Action must be 'preview' or 'commit'.")
    if action == "preview":
        report = export_service.analyze_import(db, data, duplicates)
        report.pop("_items", None)
        report["status"] = "preview"
        return JSONResponse({**report, "filename": name})
    result = export_service.run_import(db, data, name, duplicates, on_error)
    result.pop("_items", None)
    return JSONResponse({**result, "filename": name})


@router.post("/backup", status_code=201, summary="Create a timestamped database backup (admin)")
def create_backup(_: bool = Depends(require_admin)) -> dict:
    settings = get_settings()
    try:
        path = backup_database(settings.database_path, settings.backup_path)
    except FileNotFoundError as exc:
        raise AppError("The database file was not found, so no backup was made.") from exc
    except Exception as exc:
        logger.exception("Backup failed")
        raise AppError("The backup could not be created.", hint="Check free disk space and folder permissions; details are in the log file.") from exc
    return {"message": "Backup created. The integrity check passed.", "file": path.name, "size_kb": round(path.stat().st_size / 1024, 1),
            "location": str(settings.backup_path)}


@router.get("/backup", summary="List existing backups (admin)")
def list_backup_files(_: bool = Depends(require_admin)) -> list[dict]:
    return list_backups(get_settings().backup_path)
