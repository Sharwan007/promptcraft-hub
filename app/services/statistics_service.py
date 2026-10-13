"""Local usage statistics (counts only; never prompt text)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import models as m
from app.services import learning_service
from app.services.prompt_service import get_profile


def _count(db: Session, model, *where) -> int:
    q = select(func.count()).select_from(model)
    for w in where:
        q = q.where(w)
    return db.scalar(q) or 0


def dashboard_stats(db: Session) -> dict:
    pid = get_profile(db).id
    visible = (m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
    return {
        "total_prompts": _count(db, m.Prompt, *visible),
        "total_categories": _count(db, m.Category, m.Category.archived.is_(False)),
        "favorites": _count(db, m.Favorite, m.Favorite.profile_id == pid),
        "custom_prompts": _count(db, m.CustomPrompt, m.CustomPrompt.profile_id == pid, m.CustomPrompt.archived.is_(False)),
        "completed_lessons": learning_service.progress(db)["completed"],
    }


def full_statistics(db: Session) -> dict:
    stats = dashboard_stats(db)
    stats.update({
        "unpublished_prompts": _count(db, m.Prompt, m.Prompt.published.is_(False)),
        "archived_prompts": _count(db, m.Prompt, m.Prompt.archived.is_(True)),
        "featured_prompts": _count(db, m.Prompt, m.Prompt.featured.is_(True)),
        "examples": _count(db, m.BeforeAfterExample),
        "learning_modules": _count(db, m.LearningModule),
        "glossary_terms": _count(db, m.GlossaryTerm),
        "total_views": db.scalar(select(func.coalesce(func.sum(m.Prompt.view_count), 0))) or 0,
        "total_copies": db.scalar(select(func.coalesce(func.sum(m.Prompt.copy_count), 0))) or 0,
    })
    rows = db.execute(select(m.PromptUsageEvent.event_type, func.count()).group_by(m.PromptUsageEvent.event_type)).all()
    stats["events"] = {t: n for t, n in rows}
    top = db.execute(select(m.Prompt.title, m.Prompt.slug, m.Prompt.view_count, m.Prompt.copy_count).where(m.Prompt.view_count > 0)
                     .order_by(m.Prompt.view_count.desc()).limit(5)).all()
    stats["top_prompts"] = [{"title": t, "slug": s, "views": v, "copies": c} for t, s, v, c in top]
    cats = db.execute(select(m.Category.name, m.Category.slug, func.count(m.Prompt.id)).join(m.Prompt, m.Prompt.category_id == m.Category.id)
                      .where(m.Prompt.published.is_(True), m.Prompt.archived.is_(False)).group_by(m.Category.id)
                      .order_by(func.count(m.Prompt.id).desc()).limit(8)).all()
    stats["categories"] = [{"name": n, "slug": s, "count": c} for n, s, c in cats]
    return stats


def popular_categories(db: Session, limit: int = 6) -> list[dict]:
    return full_statistics(db)["categories"][:limit]
