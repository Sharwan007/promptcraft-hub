"""Local administration: PIN setup, sign-in, sessions and dashboards data."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, optional_admin, require_admin, session_manager
from app.core.security import SESSION_COOKIE
from app.database import models as m
from app.schemas.common import Message
from app.services import admin_service, export_service, prompt_service, search_service, statistics_service
from app.utilities.file_utils import list_backups

router = APIRouter(prefix="/api/admin", tags=["Administration"])


class PinSetupIn(BaseModel):
    pin: str = Field(max_length=64)
    confirm: str = Field(max_length=64)


class LoginIn(BaseModel):
    pin: str = Field(max_length=64)


class ChangePinIn(BaseModel):
    current: str = Field(max_length=64)
    new: str = Field(max_length=64)
    confirm: str = Field(max_length=64)


def start_session(response: Response, cred: m.AdminCredential) -> None:
    settings = get_settings()
    mgr = session_manager(settings)
    response.set_cookie(SESSION_COOKIE, mgr.create_session(cred.session_nonce), max_age=mgr.max_age, httponly=True,
                        samesite="strict", secure=settings.cookie_secure, path="/")


def end_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/status", summary="Is a PIN configured and is this browser signed in?")
def status(db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> dict:
    return {"configured": admin_service.is_configured(db), "authenticated": is_admin}


@router.post("/setup", summary="First-run PIN setup (signs you in)")
def setup(body: PinSetupIn, response: Response, db: Session = Depends(get_db)) -> Message:
    cred = admin_service.setup_pin(db, body.pin, body.confirm)
    start_session(response, cred)
    return Message(message="The administrator PIN was saved and you are signed in.")


@router.post("/login", summary="Sign in with the administrator PIN")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> Message:
    cred = admin_service.verify_login(db, body.pin)
    start_session(response, cred)
    return Message(message="Signed in.")


@router.post("/logout", summary="Sign out")
def logout(response: Response) -> Message:
    end_session(response)
    return Message(message="Signed out.")


@router.post("/change-pin", summary="Change the administrator PIN (signs out other sessions)")
def change_pin(body: ChangePinIn, response: Response, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    cred = admin_service.change_pin(db, body.current, body.new, body.confirm)
    start_session(response, cred)
    return Message(message="The PIN was changed.")


@router.get("/prompts", summary="All prompts including unpublished and archived (admin)")
def admin_prompts(q: str = "", status: str = "", category: str = "", page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=60),
                  db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    f = search_service.PromptFilters(q=q, category=category, status=status, page=page, page_size=page_size, sort="newest", include_hidden=True)
    res = search_service.search_prompts(db, f)
    res["items"] = [prompt_service.summary_dict(p) for p in res["items"]]
    return res


@router.get("/statistics", summary="Usage statistics (admin)")
def admin_stats(db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    return statistics_service.full_statistics(db)


@router.get("/imports", summary="Import history (admin)")
def imports(db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> list[dict]:
    rows = db.scalars(select(m.ImportHistory).order_by(m.ImportHistory.id.desc()).limit(25))
    return [{"id": h.id, "filename": h.filename, "status": h.status, "mode": h.mode, "total": h.total, "created": h.created_count,
             "updated": h.updated_count, "skipped": h.skipped_count, "errors": h.error_count, "date": h.created_at.isoformat(timespec="seconds")} for h in rows]


@router.get("/imports/{history_id}/errors", summary="Download an import error report (admin)")
def import_errors(history_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Response:
    data = export_service.import_error_report(db, history_id)
    return Response(data, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="import-report-{history_id}.txt"'})


@router.get("/validation-errors", summary="Recent validation errors (admin)")
def validation_errors(db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> list[dict]:
    rows = db.scalars(select(m.ValidationErrorLog).order_by(m.ValidationErrorLog.id.desc()).limit(50))
    return [{"id": r.id, "source": r.source, "message": r.message, "date": r.created_at.isoformat(timespec="seconds")} for r in rows]


@router.get("/backups", summary="List database backups (admin)")
def backups(_: bool = Depends(require_admin)) -> list[dict]:
    return list_backups(get_settings().backup_path)
