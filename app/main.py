"""PromptCraft Hub - FastAPI application factory.

Run with:  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
(or simply double-click start_app.bat).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import (admin, categories, custom_prompts, examples, favorites, health, import_export, learning, pages, prompts, system)
from app.api.deps import allowed_origins, csrf_protect
from app.core.config import APP_DIR, get_settings
from app.core.exceptions import AppError
from app.core.logging_config import setup_logging
from app.core.middleware import CachedStaticFiles, SecurityMiddleware
from app.core.templating import render
from app.database.connection import get_session_factory
from app.database.initialization import initialize_database

logger = logging.getLogger("promptcraft")

ERROR_TEXT = {
    400: ("Bad request", "The request could not be understood.", "Go back and check what you entered, then try again."),
    401: ("Sign-in required", "You need to sign in as administrator to continue.", "Open Administration and enter your PIN."),
    403: ("Access denied", "This action is not allowed or your session token has expired.", "Reload the page and try again."),
    404: ("Page not found", "We could not find what you were looking for.", "Use the search box or open the Prompt Library."),
    405: ("Method not allowed", "That action is not supported for this address.", "Return to the previous page."),
    409: ("Conflict", "That change conflicts with existing data.", "Review the details and try again."),
    413: ("File too large", "The request is larger than the allowed limit.", "Choose a smaller file."),
    422: ("Some details need attention", "The information you submitted is not valid.", "Correct the highlighted fields and try again."),
    429: ("Too many attempts", "Too many attempts were made in a short time.", "Wait a few minutes and try again."),
    500: ("Something went wrong", "An unexpected error occurred. Nothing you saved was lost.", "Try again. If it keeps happening, check the log file in the logs folder."),
    503: ("Temporarily unavailable", "The database is busy right now.", "Wait a moment and try again."),
}


def wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return request.url.path.startswith("/api/") or ("application/json" in accept and "text/html" not in accept)


def error_response(request: Request, status: int, message: str | None = None, details: list[str] | None = None,
                   hint: str | None = None, code: str = "error"):
    title, default_msg, default_hint = ERROR_TEXT.get(status, ERROR_TEXT[500])
    message = message or default_msg
    if request.url.path.startswith("/static/"):
        return PlainTextResponse("Static file not found. Re-run setup_app.bat or restore the app/static folder.", status_code=status)
    if wants_json(request):
        return JSONResponse({"error": {"code": code, "message": message, "details": details or [], "hint": hint or default_hint}}, status_code=status)
    template = f"{status}.html" if status in (400, 403, 404, 422, 500) else "error.html"
    ctx = {"status": status, "title": title, "message": message, "details": details or [], "hint": hint or default_hint}
    try:
        return render(request, template, ctx, status_code=status)
    except Exception:  # last resort: never fail while rendering an error
        logger.exception("Error page template failed")
        return PlainTextResponse(f"{title}: {message}", status_code=status)


def _log_validation(request: Request, messages: list[str]) -> None:
    try:
        from app.services import admin_service
        db = get_session_factory()()
        try:
            admin_service.log_validation_error(db, f"{request.method} {request.url.path}", "; ".join(messages))
        finally:
            db.close()
    except Exception:  # pragma: no cover - logging must never break a response
        logger.debug("Could not record validation error", exc_info=True)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.ensure_directories()
        try:
            initialize_database()
        except Exception:
            logger.exception("Database initialisation failed")
            raise
        pid_file = settings.pid_file
        if settings.app_env != "test":
            try:
                pid_file.write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                logger.warning("Could not write the PID file; stop_app.bat may not work.")
        logger.info("%s %s started at %s", settings.app_name, settings.app_version, settings.base_url)
        yield
        try:
            if pid_file.exists() and pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pid_file.unlink()
        except OSError:
            pass
        logger.info("Application stopped")

    app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url=None, redoc_url=None, lifespan=lifespan,
                  description="Build better prompts. Get better results. Local, offline-capable prompt library, builder, diagnostic and improver.")

    app.add_middleware(SecurityMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=sorted(allowed_origins(settings)), allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list or ["127.0.0.1", "localhost"])

    app.mount("/static", CachedStaticFiles(directory=str(APP_DIR / "static")), name="static")

    guard = [Depends(csrf_protect)]
    for r in (health.router, prompts.router, prompts.search_router, categories.router, favorites.router, custom_prompts.router,
              learning.router, examples.router, admin.router, import_export.router, system.router, pages.router):
        app.include_router(r, dependencies=guard)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return RedirectResponse("/static/icons/favicon.svg", status_code=302)

    # ----------------------------------------------------------- exception handlers
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        if exc.status_code == 401 and not wants_json(request) and request.url.path.startswith("/admin"):
            return RedirectResponse("/admin/login?expired=1", status_code=303)
        if exc.status_code == 422:
            _log_validation(request, [exc.message] + exc.details)
        return error_response(request, exc.status_code, exc.message, exc.details, exc.hint, exc.code)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()) if x not in ("body", "query", "path", "form"))
            details.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        _log_validation(request, details)
        return error_response(request, 422, "Some fields need attention.", details, None, "validation_error")

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        msg = None
        if exc.status_code == 404 and wants_json(request):
            msg = "That resource was not found."
        return error_response(request, exc.status_code, msg, code="http_error")

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, exc: IntegrityError):
        logger.warning("Integrity error on %s %s", request.method, request.url.path)
        return error_response(request, 409, "That change conflicts with existing data (for example a duplicate name).", code="conflict")

    @app.exception_handler(OperationalError)
    async def operational_handler(request: Request, exc: OperationalError):
        locked = "locked" in str(exc).lower() or "busy" in str(exc).lower()
        logger.error("Database operational error on %s %s: %s", request.method, request.url.path, "locked" if locked else "other")
        if locked:
            return error_response(request, 503, code="database_locked")
        return error_response(request, 500, code="database_error")

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(request, 500, code="server_error")

    return app


app = create_app()
