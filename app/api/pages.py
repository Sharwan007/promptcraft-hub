"""Server-rendered web pages (Jinja2)."""
from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin import end_session, start_session
from app.api.deps import get_db, get_settings, optional_admin
from app.core.exceptions import AppError, NotFound
from app.core.templating import render
from app.database import models as m
from app.services import (admin_service, builder_service, content_service, custom_service, learning_service, prompt_service,
                          search_service, statistics_service)
from app.services.scoring_service import parse_sections, scoring_service
from app.services.use_case_profiles import use_case_choices
from app.utilities.file_utils import list_backups

router = APIRouter(include_in_schema=False)

TIPS = [
    "Start with the task: one action verb and one clear deliverable.",
    "Tell the AI who the audience is. The same facts read differently for executives and for a project team.",
    "Ask for 'Not stated' when information is missing so the AI does not invent details.",
    "Name the output format: table columns, numbered steps, or a subject line plus body.",
    "Ask for assumptions and verification steps instead of just an answer.",
    "Change one thing at a time when you iterate, so you can see what helped.",
    "Replace vague words like 'good' or 'short' with measurable limits such as 'under 150 words'.",
    "Save prompts that worked as templates with [PLACEHOLDERS].",
]

COMPONENT_ORDER = [("role", "Role"), ("context", "Context"), ("task", "Task"), ("input", "Input"), ("output_format", "Output format"),
                   ("constraints", "Constraints"), ("quality_criteria", "Quality criteria")]


def _profile(db: Session) -> m.LocalProfile:
    return prompt_service.get_profile(db)


def _cards(db: Session, items, fav=None) -> list[dict]:
    fav = fav if fav is not None else prompt_service.favorite_ids(db)
    return [prompt_service.summary_dict(p, fav) for p in items]


def _full_prompts(db: Session, items, fav=None) -> list[dict]:
    """Card dicts that also carry the full prompt text for the Copy button."""
    fav = fav if fav is not None else prompt_service.favorite_ids(db)
    out = []
    for p in items:
        d = prompt_service.summary_dict(p, fav)
        d["full_prompt"] = p.full_prompt
        out.append(d)
    return out


def prompt_components(p: m.Prompt) -> list[dict]:
    comps = p.components or {}
    parsed = parse_sections(p.full_prompt)
    out = []
    for key, label in COMPONENT_ORDER:
        val = comps.get(key)
        if not val:
            val = parsed.get(key, "")
            if key == "role" and not val:
                first = p.full_prompt.splitlines()[0] if p.full_prompt else ""
                val = first if first.lower().startswith(("act as", "you are")) else ""
        if isinstance(val, list):
            val = "\n".join(f"- {v}" for v in val)
        if val:
            out.append({"key": key, "label": label, "text": str(val)})
    return out


# ============================================================ dashboard
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    profile = _profile(db)
    fav_ids = prompt_service.favorite_ids(db, profile.id)

    def many(**kw):
        f = search_service.PromptFilters(page_size=kw.pop("page_size", 6), **kw)
        return _full_prompts(db, search_service.search_prompts(db, f)["items"], fav_ids)

    day = date.today()
    ctx = {
        "profile": profile,
        "stats": statistics_service.dashboard_stats(db),
        "featured": many(featured=True, sort="relevance"),
        "recent": _full_prompts(db, prompt_service.recently_viewed(db, 6), fav_ids),
        "favorites": many(favorites_only=True, profile_id=profile.id, sort="newest"),
        "newest": many(sort="newest"),
        "potd": prompt_service.prompt_of_the_day(db),
        "popular": statistics_service.popular_categories(db, 6),
        "progress": learning_service.progress(db),
        "next_lesson": learning_service.next_incomplete(db),
        "tips": [TIPS[(day.toordinal() + i) % len(TIPS)] for i in range(3)],
    }
    if ctx["potd"] is not None:
        ctx["potd"] = prompt_service.summary_dict(ctx["potd"], fav_ids)
    return render(request, "dashboard.html", ctx, active="dashboard")


# ============================================================ library
@router.get("/prompts", response_class=HTMLResponse)
def library(request: Request, q: str = "", category: str = "", subcategory: str = "", ai_tool: str = "", difficulty: str = "",
            role: str = "", tag: str = "", featured: bool = False, sort: str = "", view: str = "", page: int = Query(1, ge=1),
            partial: bool = False, db: Session = Depends(get_db)):
    profile = _profile(db)
    view = view if view in ("grid", "list") else profile.view_mode
    sort = sort or ("relevance" if q else "relevance")
    f = search_service.PromptFilters(q=q, category=category, subcategory=subcategory, ai_tool=ai_tool, difficulty=difficulty,
                                     role=role, tag=tag, featured=featured, sort=sort, page=page, page_size=12)
    try:
        res = search_service.search_prompts(db, f)
        error = None
    except AppError as exc:
        res = {"items": [], "total": 0, "page": 1, "page_size": 12, "pages": 1}
        error = exc.message
    params = {k: v for k, v in {"q": f.q, "category": f.category, "subcategory": f.subcategory, "ai_tool": f.ai_tool,
                                "difficulty": f.difficulty, "role": f.role, "tag": f.tag, "featured": "true" if f.featured else "",
                                "sort": f.sort if f.sort != "relevance" else "", "view": view if view != profile.view_mode else ""}.items() if v}
    ctx = {"items": _full_prompts(db, res["items"]), "total": res["total"], "page": res["page"], "pages": res["pages"],
           "q": f.q, "view": view, "params": params, "base_qs": urlencode(params), "has_filters": f.active(), "error": error,
           "filters": {"category": f.category, "subcategory": f.subcategory, "ai_tool": f.ai_tool, "difficulty": f.difficulty,
                       "role": f.role, "tag": f.tag, "featured": f.featured, "sort": f.sort}}
    if partial:
        return render(request, "partials/prompt_results.html", ctx)
    ctx["facets"] = search_service.facets(db)
    ctx["breadcrumbs"] = [("Dashboard", "/"), ("Prompt Library", None)]
    return render(request, "prompt_library.html", ctx, active="library")


@router.get("/prompts/{slug}", response_class=HTMLResponse)
def prompt_detail(request: Request, slug: str, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    p = prompt_service.get_prompt(db, slug, include_hidden=is_admin)
    if p.slug != slug and slug.isdigit():
        return RedirectResponse(f"/prompts/{p.slug}", status_code=307)
    if p.published and not p.archived:
        prompt_service.record_view(db, p)
    fav = prompt_service.favorite_ids(db)
    d = prompt_service.prompt_dict(p, fav)
    d["components_list"] = prompt_components(p)
    ctx = {"p": d, "related": _cards(db, prompt_service.related_prompts(db, p, 4), fav),
           "score": scoring_service.analyze(p.full_prompt), "share_url": f"{get_settings().base_url}/prompts/{p.slug}",
           "breadcrumbs": [("Dashboard", "/"), ("Prompt Library", "/prompts"), (p.category.name, f"/prompts?category={p.category.slug}"), (p.title, None)]}
    return render(request, "prompt_detail.html", ctx, active="library")


@router.get("/prompts/{slug}/print", response_class=HTMLResponse)
def prompt_print(request: Request, slug: str, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    p = prompt_service.get_prompt(db, slug, include_hidden=is_admin)
    return render(request, "prompt_print.html", {"p": prompt_service.prompt_dict(p), "components_list": prompt_components(p)})


# ============================================================ tools
@router.get("/builder", response_class=HTMLResponse)
def builder(request: Request, db: Session = Depends(get_db)):
    ctx = {"catalog": builder_service.catalog(), "breadcrumbs": [("Dashboard", "/"), ("Prompt Builder", None)],
           "roles": ["a senior business analyst", "an experienced project manager", "an agile coach and Scrum Master",
                     "a customer-service specialist", "a data analyst", "a senior SQL developer", "an Excel expert",
                     "a presentation designer", "a senior software engineer", "a marketing strategist", "an HR business partner",
                     "a financial analyst", "a research analyst", "a professional editor and writer"],
           "tones": ["Professional", "Friendly", "Formal", "Persuasive", "Empathetic", "Neutral and factual", "Concise and direct"]}
    return render(request, "prompt_builder.html", ctx, active="builder")


@router.get("/improver", response_class=HTMLResponse)
def improver(request: Request):
    from app.services.builder_service import OUTPUT_FORMATS, PURPOSES
    ctx = {"purposes": [(k, v[0]) for k, v in PURPOSES.items()], "formats": [(k, v[0]) for k, v in OUTPUT_FORMATS.items() if k != "custom"],
           "tools": ["Microsoft Copilot", "ChatGPT", "Claude", "Gemini", "Tool-independent"],
           "breadcrumbs": [("Dashboard", "/"), ("Prompt Improver", None)]}
    return render(request, "prompt_improver.html", ctx, active="improver")


@router.get("/diagnostic", response_class=HTMLResponse)
def diagnostic(request: Request):
    return render(request, "prompt_diagnostic.html", {"use_cases": use_case_choices(), "breadcrumbs": [("Dashboard", "/"), ("Prompt Diagnostic", None)]},
                  active="diagnostic")


@router.get("/before-after", response_class=HTMLResponse)
def before_after(request: Request, db: Session = Depends(get_db)):
    items = [learning_service.example_dict(e) for e in learning_service.examples(db)]
    return render(request, "before_after.html", {"examples": items, "breadcrumbs": [("Dashboard", "/"), ("Before & After", None)]}, active="before_after")


# ============================================================ learning
@router.get("/learning", response_class=HTMLResponse)
def learning_center(request: Request, db: Session = Depends(get_db)):
    done = learning_service.completed_ids(db)
    mods = [learning_service.module_dict(x, done, with_answers=False) for x in learning_service.list_modules(db)]
    ctx = {"modules": mods, "progress": learning_service.progress(db), "glossary": learning_service.glossary(db),
           "breadcrumbs": [("Dashboard", "/"), ("Learning Center", None)]}
    return render(request, "learning_center.html", ctx, active="learning")


@router.get("/learning/{slug}", response_class=HTMLResponse)
def learning_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    mod = learning_service.get_module(db, slug)
    mods = learning_service.list_modules(db)
    idx = next((i for i, x in enumerate(mods) if x.id == mod.id), 0)
    done = learning_service.completed_ids(db)
    ctx = {"mod": learning_service.module_dict(mod, done), "prev": mods[idx - 1] if idx > 0 else None,
           "next": mods[idx + 1] if idx < len(mods) - 1 else None, "progress": learning_service.progress(db), "index": idx + 1,
           "total": len(mods), "breadcrumbs": [("Dashboard", "/"), ("Learning Center", "/learning"), (mod.title, None)]}
    return render(request, "learning_detail.html", ctx, active="learning")


# ============================================================ personal
@router.get("/favorites", response_class=HTMLResponse)
def favorites(request: Request, q: str = "", category: str = "", difficulty: str = "", page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    profile = _profile(db)
    f = search_service.PromptFilters(q=q, category=category, difficulty=difficulty, page=page, page_size=12, favorites_only=True,
                                     profile_id=profile.id, sort="newest" if not q else "relevance")
    try:
        res = search_service.search_prompts(db, f)
        error = None
    except AppError as exc:
        res, error = {"items": [], "total": 0, "page": 1, "pages": 1}, exc.message
    params = {k: v for k, v in {"q": f.q, "category": f.category, "difficulty": f.difficulty}.items() if v}
    ctx = {"items": _full_prompts(db, res["items"], {p.id for p in res["items"]}), "total": res["total"], "page": res["page"], "pages": res["pages"],
           "q": f.q, "view": profile.view_mode, "params": params, "base_qs": urlencode(params), "has_filters": bool(params), "error": error,
           "filters": {"category": f.category, "difficulty": f.difficulty}, "facets": search_service.facets(db), "base_path": "/favorites",
           "breadcrumbs": [("Dashboard", "/"), ("Favorites", None)]}
    return render(request, "favorites.html", ctx, active="favorites")


@router.get("/my-prompts", response_class=HTMLResponse)
def my_prompts(request: Request, q: str = "", category_id: int | None = None, archived: bool = False, page: int = Query(1, ge=1),
               db: Session = Depends(get_db)):
    res = custom_service.list_custom(db, q=q, category_id=category_id, archived=archived, page=page, page_size=12)
    params = {k: v for k, v in {"q": q, "category_id": category_id or "", "archived": "true" if archived else ""}.items() if v}
    ctx = {"items": res["items"], "total": res["total"], "page": res["page"], "pages": res["pages"], "q": q, "archived": archived,
           "category_id": category_id, "counts": custom_service.counts(db), "categories": content_service.categories_with_counts(db, False),
           "base_qs": urlencode(params), "base_path": "/my-prompts", "params": params,
           "breadcrumbs": [("Dashboard", "/"), ("My Prompts", None)]}
    return render(request, "my_prompts.html", ctx, active="my_prompts")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    return render(request, "settings.html", {"profile": _profile(db), "tools": ["Microsoft Copilot", "ChatGPT", "Claude", "Gemini", "Tool-independent"],
                                              "db_path": str(s.database_path), "backup_path": str(s.backup_path), "log_path": str(s.log_path),
                                              "breadcrumbs": [("Dashboard", "/"), ("Settings", None)]}, active="settings")


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    s = get_settings()
    return render(request, "privacy.html", {"db_path": str(s.database_path), "breadcrumbs": [("Dashboard", "/"), ("Privacy", None)]})


@router.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return render(request, "help.html", {"breadcrumbs": [("Dashboard", "/"), ("Help", None)]})


@router.get("/docs", response_class=HTMLResponse)
def api_docs(request: Request):
    return render(request, "api_docs.html", {"breadcrumbs": [("Dashboard", "/"), ("API documentation", None)]})


# ============================================================ administration
def _gate(request: Request, db: Session, is_admin: bool):
    if is_admin:
        return None
    target = "/admin/login" if admin_service.is_configured(db) else "/admin/setup"
    return RedirectResponse(f"{target}?next={request.url.path}", status_code=303)


def _safe_next(value: str | None) -> str:
    return value if value and value.startswith("/admin") and not value.startswith("//") else "/admin"


@router.get("/admin/setup", response_class=HTMLResponse)
def admin_setup_page(request: Request, db: Session = Depends(get_db)):
    if admin_service.is_configured(db):
        return RedirectResponse("/admin/login", status_code=303)
    return render(request, "admin_login.html", {"mode": "setup", "breadcrumbs": [("Dashboard", "/"), ("Administration", None)]}, active="admin")


@router.post("/admin/setup", response_class=HTMLResponse)
def admin_setup_submit(request: Request, pin: str = Form(""), confirm: str = Form(""), db: Session = Depends(get_db)):
    try:
        cred = admin_service.setup_pin(db, pin, confirm)
    except AppError as exc:
        return render(request, "admin_login.html", {"mode": "setup", "error": exc.message, "details": exc.details, "hint": exc.hint,
                                                    "breadcrumbs": [("Dashboard", "/"), ("Administration", None)]}, status_code=exc.status_code, active="admin")
    resp = RedirectResponse("/admin", status_code=303)
    start_session(resp, cred)
    return resp


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, next: str = "/admin", expired: bool = False, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if not admin_service.is_configured(db):
        return RedirectResponse("/admin/setup", status_code=303)
    if is_admin:
        return RedirectResponse(_safe_next(next), status_code=303)
    return render(request, "admin_login.html", {"mode": "login", "next": _safe_next(next), "error": "Your session has expired. Please sign in again." if expired else None,
                                                "breadcrumbs": [("Dashboard", "/"), ("Administration", None)]}, active="admin")


@router.post("/admin/login", response_class=HTMLResponse)
def admin_login_submit(request: Request, pin: str = Form(""), next: str = Form("/admin"), db: Session = Depends(get_db)):
    try:
        cred = admin_service.verify_login(db, pin)
    except AppError as exc:
        return render(request, "admin_login.html", {"mode": "login", "next": _safe_next(next), "error": exc.message, "hint": exc.hint,
                                                    "breadcrumbs": [("Dashboard", "/"), ("Administration", None)]}, status_code=exc.status_code, active="admin")
    resp = RedirectResponse(_safe_next(next), status_code=303)
    start_session(resp, cred)
    return resp


@router.post("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/", status_code=303)
    end_session(resp)
    return resp


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if (g := _gate(request, db, is_admin)):
        return g
    s = get_settings()
    imports = db.scalars(select(m.ImportHistory).order_by(m.ImportHistory.id.desc()).limit(8)).all()
    errors = db.scalars(select(m.ValidationErrorLog).order_by(m.ValidationErrorLog.id.desc()).limit(8)).all()
    ctx = {"stats": statistics_service.full_statistics(db), "imports": imports, "validation_errors": errors,
           "backups": list_backups(s.backup_path)[:6], "backup_path": str(s.backup_path), "categories": content_service.categories_with_counts(db),
           "session_minutes": s.session_expiry_minutes, "breadcrumbs": [("Dashboard", "/"), ("Administration", None)]}
    return render(request, "admin_dashboard.html", ctx, active="admin")


def _prompt_form_ctx(db: Session, prompt: dict | None):
    return {"prompt": prompt, "categories": content_service.categories_with_counts(db, False),
            "tools": ["Microsoft Copilot", "ChatGPT", "Claude", "Gemini", "Tool-independent"], "difficulties": ["Beginner", "Intermediate", "Advanced"]}


@router.get("/admin/prompts/new", response_class=HTMLResponse)
def admin_prompt_new(request: Request, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if (g := _gate(request, db, is_admin)):
        return g
    ctx = _prompt_form_ctx(db, None)
    ctx["breadcrumbs"] = [("Dashboard", "/"), ("Administration", "/admin"), ("New prompt", None)]
    return render(request, "admin_prompt_form.html", ctx, active="admin")


@router.get("/admin/prompts/{prompt_id}/edit", response_class=HTMLResponse)
def admin_prompt_edit(request: Request, prompt_id: int, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if (g := _gate(request, db, is_admin)):
        return g
    p = prompt_service.get_prompt(db, prompt_id, include_hidden=True)
    ctx = _prompt_form_ctx(db, prompt_service.prompt_dict(p))
    ctx["breadcrumbs"] = [("Dashboard", "/"), ("Administration", "/admin"), (f"Edit: {p.title}", None)]
    return render(request, "admin_prompt_form.html", ctx, active="admin")


@router.get("/admin/import", response_class=HTMLResponse)
def admin_import(request: Request, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if (g := _gate(request, db, is_admin)):
        return g
    imports = db.scalars(select(m.ImportHistory).order_by(m.ImportHistory.id.desc()).limit(10)).all()
    return render(request, "admin_import.html", {"imports": imports, "max_mb": get_settings().max_import_file_mb,
                                                 "breadcrumbs": [("Dashboard", "/"), ("Administration", "/admin"), ("Import and export", None)]}, active="admin")


@router.get("/admin/content", response_class=HTMLResponse)
def admin_content(request: Request, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    if (g := _gate(request, db, is_admin)):
        return g
    return render(request, "admin_content.html", {"breadcrumbs": [("Dashboard", "/"), ("Administration", "/admin"), ("Manage content", None)]}, active="admin")
