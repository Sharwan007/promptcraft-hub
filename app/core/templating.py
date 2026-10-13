"""Jinja2 environment, custom filters and the shared page-rendering helper."""
from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import Request
from markupsafe import Markup, escape
from starlette.templating import Jinja2Templates

from app.core.config import APP_DIR, get_settings

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

PLACEHOLDER = re.compile(r"\[([A-Z][A-Z0-9 _/&\-]{1,40})\]")
SECTION_RE = re.compile(r"^(Role|Context|Task|Input|Output format|Constraints|Quality criteria|Audience|Tone)\s*:\s*$", re.M)

NAV = [
    ("dashboard", "/", "Dashboard", "home"),
    ("library", "/prompts", "Prompt Library", "book"),
    ("builder", "/builder", "Prompt Builder", "wand"),
    ("improver", "/improver", "Prompt Improver", "sparkles"),
    ("diagnostic", "/diagnostic", "Prompt Diagnostic", "stethoscope"),
    ("before_after", "/before-after", "Before & After", "columns"),
    ("learning", "/learning", "Learning Center", "graduation"),
    ("favorites", "/favorites", "Favorites", "heart"),
    ("my_prompts", "/my-prompts", "My Prompts", "folder"),
    ("admin", "/admin", "Administration", "shield"),
    ("settings", "/settings", "Settings", "settings"),
]

PRIVACY_WARNING = ("Do not enter confidential, personal, customer, financial, medical, or company-sensitive information "
                   "unless your organization has approved the AI tool and the data-handling process.")
ADMIN_WARNING = ("Local PIN authentication is intended for a local demonstration. Replace it with enterprise "
                 "authentication before deploying the application publicly.")


def highlight(text: str, query: str = "") -> Markup:
    """HTML-escape text and wrap query terms in <mark>. Safe against script injection."""
    text = text or ""
    terms = [t for t in re.split(r"\s+", (query or "").strip()) if len(t) >= 2][:6]
    if not terms:
        return Markup(escape(text))
    pattern = re.compile("(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + ")", re.IGNORECASE)
    out, last = [], 0
    for m in pattern.finditer(text):
        out.append(str(escape(text[last:m.start()])))
        out.append(f"<mark>{escape(m.group(0))}</mark>")
        last = m.end()
    out.append(str(escape(text[last:])))
    return Markup("".join(out))


def placeholders(text: str) -> Markup:
    """Escape text and highlight [PLACEHOLDER] tokens."""
    safe = str(escape(text or ""))
    return Markup(PLACEHOLDER.sub(lambda m: f'<span class="ph" data-ph="{m.group(1)}">[{m.group(1)}]</span>', safe))


def paragraphs(text: str) -> Markup:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return Markup("".join(f"<p>{escape(p).replace(chr(10), Markup('<br>'))}</p>" for p in parts))


def fmt_date(value, fmt: str = "%d %b %Y") -> str:
    return value.strftime(fmt) if isinstance(value, datetime) else str(value or "")


def json_attr(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def local_profile() -> dict:
    """Small helper for the shell (display name, theme preference). Never raises."""
    try:
        from app.database.connection import get_session_factory
        from app.services.prompt_service import get_profile
        db = get_session_factory()()
        try:
            p = get_profile(db)
            return {"display_name": p.display_name, "theme": p.theme, "view_mode": p.view_mode, "role": p.role}
        finally:
            db.close()
    except Exception:
        return {"display_name": "Local User", "theme": "system", "view_mode": "grid", "role": ""}


templates.env.globals["local_profile"] = local_profile
templates.env.policies["json.dumps_kwargs"] = {"sort_keys": True, "default": str, "ensure_ascii": False}
templates.env.filters.update({"highlight": highlight, "placeholders": placeholders, "paragraphs": paragraphs,
                              "fmt_date": fmt_date, "json_attr": json_attr})


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200, active: str = ""):
    settings = get_settings()
    ctx = {
        "app_name": settings.app_name, "app_version": settings.app_version, "nav": NAV, "active": active,
        "csrf_token": getattr(request.state, "csrf_token", ""), "privacy_warning": PRIVACY_WARNING,
        "admin_warning": ADMIN_WARNING, "current_path": request.url.path, "breadcrumbs": [],
    }
    ctx.update(context or {})
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
