"""HTTP middleware: security headers, CSRF cookie issuing, request-size limit, access log."""
from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.security import CSRF_COOKIE

logger = logging.getLogger("promptcraft.http")

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        from app.api.deps import session_manager  # local import avoids a circular import at start-up
        mgr = session_manager(settings)

        limit = settings.max_request_body_mb * 1024 * 1024
        try:
            length = int(request.headers.get("content-length") or 0)
        except ValueError:
            length = 0
        if length > limit:
            msg = f"The request is larger than the {settings.max_request_body_mb} MB limit."
            if request.url.path.startswith("/api/"):
                return JSONResponse({"error": {"code": "payload_too_large", "message": msg, "details": [], "hint": None}}, status_code=413)
            return PlainTextResponse(msg, status_code=413)

        cookie = request.cookies.get(CSRF_COOKIE)
        issue = not (cookie and mgr.csrf_valid(cookie, cookie))
        token = mgr.new_csrf() if issue else cookie
        request.state.csrf_token = token

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000

        if issue:
            response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure, path="/")
        path = request.url.path
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not path.startswith("/static/"):
            h.setdefault("Content-Security-Policy", CSP)
            h.setdefault("Cache-Control", "no-store")
        logger.info("%s %s -> %s (%.0f ms)", request.method, path, response.status_code, elapsed)  # path only: no query strings
        return response


class CachedStaticFiles(StaticFiles):
    """Static files with a one-day cache (assets are non-sensitive)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response
