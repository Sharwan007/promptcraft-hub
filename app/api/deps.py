"""Shared FastAPI dependencies: database session, admin session, CSRF protection."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthRequired, Forbidden
from app.core.security import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, SessionManager
from app.database.connection import get_db
from app.services import admin_service

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

__all__ = ["get_db", "get_settings", "session_manager", "require_admin", "optional_admin", "csrf_protect"]


@lru_cache
def _manager(secret: str, minutes: int) -> SessionManager:
    return SessionManager(secret, minutes)


def session_manager(settings: Settings | None = None) -> SessionManager:
    s = settings or get_settings()
    return _manager(s.secret_key, s.session_expiry_minutes)


def allowed_origins(settings: Settings) -> set[str]:
    origins = set(settings.cors_origin_list)
    for host in settings.allowed_host_list:
        if host == "testserver":
            origins.add("http://testserver")
            continue
        origins.add(f"http://{host}:{settings.port}")
        origins.add(f"http://{host}")
    return origins


async def csrf_protect(request: Request) -> None:
    """Protect every state-changing request.

    Accepted when (a) the X-CSRF-Token header (or ``csrf_token`` form field) matches the signed
    cookie, or (b) the request is JSON, which a cross-site page cannot send without a CORS
    preflight (our CORS policy only allows this application's own origins).
    """
    if request.method not in UNSAFE:
        return
    settings = get_settings()
    mgr = session_manager(settings)
    cookie = request.cookies.get(CSRF_COOKIE)
    origin = request.headers.get("origin")
    if origin and origin not in allowed_origins(settings):
        raise Forbidden("This request was blocked because it came from an unexpected origin.")
    header = request.headers.get(CSRF_HEADER)
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if header and mgr.csrf_valid(cookie, header):
        return
    if ctype in ("application/x-www-form-urlencoded", "multipart/form-data"):
        form = await request.form()
        if mgr.csrf_valid(cookie, form.get("csrf_token")):
            return
    elif ctype == "application/json" and not header:
        return
    raise Forbidden("Your session token is missing or has expired. Reload the page and try again.")


def _admin_state(request: Request, db: Session) -> tuple[bool, str]:
    mgr = session_manager()
    cred = admin_service.get_credential(db)
    token = request.cookies.get(SESSION_COOKIE)
    return mgr.read_session(token, cred.session_nonce if cred else None)


def optional_admin(request: Request, db: Session = Depends(get_db)) -> bool:
    return _admin_state(request, db)[0]


def require_admin(request: Request, db: Session = Depends(get_db)) -> bool:
    ok, reason = _admin_state(request, db)
    if ok:
        return True
    if reason == "expired":
        raise AuthRequired("Your administrator session has expired. Please sign in again.", hint="Open Administration and enter your PIN.")
    raise AuthRequired("Administrator sign-in is required for this action.", hint="Open Administration and enter your PIN.")
