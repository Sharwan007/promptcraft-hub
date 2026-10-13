"""Prompt search and filtering. Modular so SQLite FTS / PostgreSQL search can replace it later."""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import String, case, cast, exists, func, or_, select
from sqlalchemy.orm import Session, contains_eager

from app.core.exceptions import ValidationFailed
from app.database import models as m
from app.utilities.text_utils import escape_like, sanitize_search
from app.utilities.validation import AI_TOOLS, DIFFICULTIES

SORTS = ("relevance", "newest", "viewed", "copied", "alpha")
MAX_TERMS = 6
MAX_PAGE_SIZE = 60


@dataclass
class PromptFilters:
    q: str = ""
    category: str = ""
    subcategory: str = ""
    ai_tool: str = ""
    difficulty: str = ""
    role: str = ""
    tag: str = ""
    featured: bool = False
    favorites_only: bool = False
    sort: str = "relevance"
    page: int = 1
    page_size: int = 12
    include_hidden: bool = False
    profile_id: int | None = None
    status: str = ""  # admin only: published | unpublished | archived

    def validate(self) -> "PromptFilters":
        self.q = sanitize_search(self.q)
        for attr in ("category", "subcategory", "role", "tag"):
            setattr(self, attr, sanitize_search(getattr(self, attr), 80))
        if self.difficulty and self.difficulty not in DIFFICULTIES:
            raise ValidationFailed(f"Difficulty must be one of: {', '.join(DIFFICULTIES)}.")
        if self.ai_tool and self.ai_tool not in AI_TOOLS:
            raise ValidationFailed(f"AI tool must be one of: {', '.join(AI_TOOLS)}.")
        if self.sort not in SORTS:
            raise ValidationFailed(f"Sort must be one of: {', '.join(SORTS)}.")
        self.page = max(1, int(self.page or 1))
        self.page_size = min(MAX_PAGE_SIZE, max(1, int(self.page_size or 12)))
        return self

    def active(self) -> bool:
        return any([self.q, self.category, self.subcategory, self.ai_tool, self.difficulty, self.role, self.tag, self.featured])


def _like(col, term: str):
    return col.ilike(f"%{escape_like(term)}%", escape="\\")


def _apply(stmt, f: PromptFilters):
    stmt = stmt.join(m.Category, m.Prompt.category_id == m.Category.id).outerjoin(m.Subcategory, m.Prompt.subcategory_id == m.Subcategory.id)
    if not f.include_hidden:
        stmt = stmt.where(m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
    for term in f.q.split()[:MAX_TERMS]:
        tag_match = exists().where(m.PromptTag.prompt_id == m.Prompt.id, m.PromptTag.tag_id == m.Tag.id, _like(m.Tag.name, term))
        stmt = stmt.where(or_(
            _like(m.Prompt.title, term), _like(m.Prompt.description, term), _like(m.Prompt.full_prompt, term),
            _like(m.Prompt.user_role, term), _like(m.Prompt.use_case, term), _like(m.Category.name, term),
            _like(m.Subcategory.name, term), tag_match))
    if f.category:
        stmt = stmt.where(or_(m.Category.slug == f.category.lower(), func.lower(m.Category.name) == f.category.lower()))
    if f.subcategory:
        stmt = stmt.where(func.lower(m.Subcategory.name) == f.subcategory.lower())
    if f.difficulty:
        stmt = stmt.where(m.Prompt.difficulty == f.difficulty)
    if f.ai_tool:
        stmt = stmt.where(or_(cast(m.Prompt.ai_tools, String).like(f'%"{f.ai_tool}"%'),
                              cast(m.Prompt.ai_tools, String).like('%"Tool-independent"%')))
    if f.role:
        stmt = stmt.where(func.lower(m.Prompt.user_role) == f.role.lower())
    if f.tag:
        stmt = stmt.where(exists().where(m.PromptTag.prompt_id == m.Prompt.id, m.PromptTag.tag_id == m.Tag.id,
                                         or_(m.Tag.slug == f.tag.lower(), func.lower(m.Tag.name) == f.tag.lower())))
    if f.featured:
        stmt = stmt.where(m.Prompt.featured.is_(True))
    if f.include_hidden and f.status:
        if f.status == "archived":
            stmt = stmt.where(m.Prompt.archived.is_(True))
        elif f.status == "unpublished":
            stmt = stmt.where(m.Prompt.published.is_(False))
        elif f.status == "published":
            stmt = stmt.where(m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
    if f.favorites_only:
        stmt = stmt.where(exists().where(m.Favorite.prompt_id == m.Prompt.id, m.Favorite.profile_id == (f.profile_id or -1)))
    return stmt


def _order(stmt, f: PromptFilters):
    if f.sort == "newest":
        return stmt.order_by(m.Prompt.created_at.desc(), m.Prompt.id.desc())
    if f.sort == "viewed":
        return stmt.order_by(m.Prompt.view_count.desc(), m.Prompt.id)
    if f.sort == "copied":
        return stmt.order_by(m.Prompt.copy_count.desc(), m.Prompt.id)
    if f.sort == "alpha":
        return stmt.order_by(func.lower(m.Prompt.title))
    if f.q:
        first = f.q.split()[0]
        title_hit = case((_like(m.Prompt.title, first), 0), else_=1)
        return stmt.order_by(title_hit, m.Prompt.featured.desc(), m.Prompt.view_count.desc(), m.Prompt.id)
    return stmt.order_by(m.Prompt.featured.desc(), m.Prompt.id)


def search_prompts(db: Session, f: PromptFilters) -> dict:
    f.validate()
    total = db.scalar(_apply(select(func.count(func.distinct(m.Prompt.id))), f)) or 0
    stmt = _order(_apply(select(m.Prompt), f), f).options(contains_eager(m.Prompt.category), contains_eager(m.Prompt.subcategory))
    stmt = stmt.limit(f.page_size).offset((f.page - 1) * f.page_size)
    items = list(db.scalars(stmt).unique())
    pages = max(1, math.ceil(total / f.page_size))
    return {"items": items, "total": total, "page": f.page, "page_size": f.page_size, "pages": pages}


def suggest(db: Session, q: str, limit: int = 8) -> list[dict]:
    q = sanitize_search(q, 60)
    if len(q) < 2:
        return []
    out: list[dict] = []
    titles = db.execute(select(m.Prompt.title, m.Prompt.slug).where(m.Prompt.published.is_(True), m.Prompt.archived.is_(False),
                                                                    _like(m.Prompt.title, q)).order_by(m.Prompt.view_count.desc()).limit(limit)).all()
    out += [{"type": "prompt", "label": t, "url": f"/prompts/{s}"} for t, s in titles]
    tags = db.scalars(select(m.Tag.name).where(_like(m.Tag.name, q)).order_by(m.Tag.name).limit(4)).all()
    out += [{"type": "tag", "label": f"Tag: {t}", "url": f"/prompts?tag={t}"} for t in tags]
    cats = db.execute(select(m.Category.name, m.Category.slug).where(_like(m.Category.name, q)).limit(3)).all()
    out += [{"type": "category", "label": f"Category: {n}", "url": f"/prompts?category={s}"} for n, s in cats]
    return out[:limit + 4]


def facets(db: Session) -> dict:
    visible = (m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
    cats = db.execute(
        select(m.Category, func.count(m.Prompt.id)).outerjoin(m.Prompt, (m.Prompt.category_id == m.Category.id) & m.Prompt.published.is_(True) & m.Prompt.archived.is_(False))
        .where(m.Category.archived.is_(False)).group_by(m.Category.id).order_by(m.Category.sort_order, m.Category.name)).all()
    subs = db.execute(select(m.Subcategory, m.Category.slug).join(m.Category).order_by(m.Subcategory.name)).all()
    roles = db.scalars(select(m.Prompt.user_role).where(*visible, m.Prompt.user_role != "").distinct().order_by(m.Prompt.user_role)).all()
    tags = db.execute(select(m.Tag.name, m.Tag.slug, func.count(m.PromptTag.prompt_id)).join(m.PromptTag).group_by(m.Tag.id)
                      .order_by(func.count(m.PromptTag.prompt_id).desc(), m.Tag.name).limit(40)).all()
    return {
        "categories": [{"id": c.id, "name": c.name, "slug": c.slug, "icon": c.icon, "description": c.description, "count": n} for c, n in cats],
        "subcategories": [{"id": s.id, "name": s.name, "category_id": s.category_id, "category_slug": cs} for s, cs in subs],
        "roles": roles, "tags": [{"name": n, "slug": s, "count": c} for n, s, c in tags],
        "ai_tools": list(AI_TOOLS), "difficulties": list(DIFFICULTIES),
    }
