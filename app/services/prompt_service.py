"""Prompt CRUD, taxonomy resolution, favorites, usage tracking."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.security import utcnow
from app.database import models as m
from app.schemas.prompt import PromptCreate
from app.utilities.text_utils import clean_text, find_placeholders, slugify, unique_list
from app.utilities.validation import normalize_tags

RECENT_LIMIT = 20


# ----------------------------------------------------------------------- profile
def get_profile(db: Session) -> m.LocalProfile:
    profile = db.scalar(select(m.LocalProfile).order_by(m.LocalProfile.id).limit(1))
    if profile is None:
        profile = m.LocalProfile()
        db.add(profile)
        db.flush()
    return profile


# ----------------------------------------------------------------------- serialization
def favorite_ids(db: Session, profile_id: int | None = None) -> set[int]:
    pid = profile_id or get_profile(db).id
    return set(db.scalars(select(m.Favorite.prompt_id).where(m.Favorite.profile_id == pid)))


def summary_dict(p: m.Prompt, fav: set[int] | None = None) -> dict:
    return {
        "id": p.id, "title": p.title, "slug": p.slug, "description": p.description,
        "category": p.category.name, "category_slug": p.category.slug,
        "subcategory": p.subcategory.name if p.subcategory else None,
        "difficulty": p.difficulty, "ai_tools": p.ai_tools or [], "tags": [t.name for t in p.tags],
        "user_role": p.user_role, "view_count": p.view_count, "copy_count": p.copy_count,
        "is_favorite": bool(fav and p.id in fav), "featured": p.featured, "published": p.published, "archived": p.archived,
    }


def prompt_dict(p: m.Prompt, fav: set[int] | None = None) -> dict:
    d = summary_dict(p, fav)
    d.update({
        "category_id": p.category_id, "full_prompt": p.full_prompt, "use_case": p.use_case,
        "expected_output": p.expected_output, "required_inputs": p.required_inputs or [],
        "example_inputs": p.example_inputs or {}, "example_output": p.example_output,
        "why_it_works": p.why_it_works, "customization_tips": p.customization_tips or [],
        "common_mistakes": p.common_mistakes or [], "constraints": p.constraints or [],
        "components": p.components or {}, "created_at": p.created_at, "updated_at": p.updated_at,
        "version": p.version,
    })
    return d


# ----------------------------------------------------------------------- taxonomy
def resolve_category(db: Session, name: str | None, category_id: int | None = None) -> m.Category:
    cat = None
    if category_id:
        cat = db.get(m.Category, category_id)
    elif name:
        cat = db.scalar(select(m.Category).where(func.lower(m.Category.name) == name.strip().lower()))
    if cat is None or cat.archived:
        valid = ", ".join(db.scalars(select(m.Category.name).where(m.Category.archived.is_(False)).order_by(m.Category.sort_order)))
        raise ValidationFailed(f"Category {name or category_id!r} does not exist.", hint=f"Valid categories: {valid}.")
    return cat


def resolve_subcategory(db: Session, cat: m.Category, name: str | None) -> m.Subcategory | None:
    name = clean_text(name or "", 100)
    if not name:
        return None
    sub = db.scalar(select(m.Subcategory).where(m.Subcategory.category_id == cat.id, func.lower(m.Subcategory.name) == name.lower()))
    if sub is None:
        sub = m.Subcategory(category_id=cat.id, name=name, slug=slugify(name))
        db.add(sub)
        db.flush()
    return sub


def get_or_create_tags(db: Session, names: list[str]) -> list[m.Tag]:
    tags = []
    for name in normalize_tags(names):
        slug = slugify(name, 60)
        tag = db.scalar(select(m.Tag).where(m.Tag.slug == slug))
        if tag is None:
            tag = m.Tag(name=name, slug=slug)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def unique_slug(db: Session, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while True:
        q = select(m.Prompt.id).where(m.Prompt.slug == slug)
        if exclude_id:
            q = q.where(m.Prompt.id != exclude_id)
        if db.scalar(q) is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


# ----------------------------------------------------------------------- CRUD
def get_prompt(db: Session, key: int | str, include_hidden: bool = False) -> m.Prompt:
    if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
        p = db.get(m.Prompt, int(key))
    else:
        p = db.scalar(select(m.Prompt).where(m.Prompt.slug == key))
    if p is None or (not include_hidden and (p.archived or not p.published)):
        raise NotFound("That prompt could not be found. It may have been archived or unpublished.")
    return p


def _apply(p: m.Prompt, db: Session, data: PromptCreate) -> None:
    cat = resolve_category(db, data.category, data.category_id)
    sub = resolve_subcategory(db, cat, data.subcategory)
    p.title = clean_text(data.title, 200)
    p.description = clean_text(data.description, 1000)
    p.full_prompt = clean_text(data.full_prompt)
    p.category_id = cat.id
    p.subcategory_id = sub.id if sub else None
    p.user_role = clean_text(data.user_role, 120)
    p.use_case = clean_text(data.use_case, 200)
    p.ai_tools = unique_list(data.ai_tools) or ["Tool-independent"]
    p.difficulty = data.difficulty
    p.expected_output = clean_text(data.expected_output)
    p.required_inputs = unique_list(data.required_inputs) or find_placeholders(p.full_prompt)
    p.example_inputs = {clean_text(k, 60): clean_text(v, 1000) for k, v in data.example_inputs.items()}
    p.example_output = clean_text(data.example_output)
    p.why_it_works = clean_text(data.why_it_works)
    p.customization_tips = unique_list(data.customization_tips)
    p.common_mistakes = unique_list(data.common_mistakes)
    p.constraints = unique_list(data.constraints)
    p.components = data.components or {}
    p.featured = data.featured
    p.published = data.published
    p.tags = get_or_create_tags(db, data.tags)


def create_prompt(db: Session, data: PromptCreate) -> m.Prompt:
    slug = slugify(data.slug or data.title, 200)
    if db.scalar(select(m.Prompt.id).where(m.Prompt.slug == slug)):
        raise Conflict(f"A prompt with the slug '{slug}' already exists.", hint="Choose a different title or slug.")
    p = m.Prompt(slug=slug, version=1)
    try:
        _apply(p, db, data)
        db.add(p)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("The prompt could not be saved because it duplicates an existing record.") from exc
    except Exception:
        db.rollback()
        raise
    return get_prompt(db, p.id, include_hidden=True)


def update_prompt(db: Session, prompt_id: int, data: PromptCreate) -> m.Prompt:
    p = get_prompt(db, prompt_id, include_hidden=True)
    new_slug = slugify(data.slug, 200) if data.slug else p.slug
    if new_slug != p.slug:
        if db.scalar(select(m.Prompt.id).where(m.Prompt.slug == new_slug, m.Prompt.id != p.id)):
            raise Conflict(f"A prompt with the slug '{new_slug}' already exists.")
        p.slug = new_slug
    changed = clean_text(data.full_prompt) != p.full_prompt
    try:
        _apply(p, db, data)
        if changed:
            p.version += 1
        p.updated_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_prompt(db, p.id, include_hidden=True)


def set_flags(db: Session, prompt_id: int, **flags) -> m.Prompt:
    p = get_prompt(db, prompt_id, include_hidden=True)
    for k, v in flags.items():
        if k not in {"archived", "published", "featured"}:
            raise ValidationFailed(f"Unknown flag {k}.")
        setattr(p, k, bool(v))
    db.commit()
    return p


def delete_permanently(db: Session, prompt_id: int) -> None:
    p = get_prompt(db, prompt_id, include_hidden=True)
    db.delete(p)  # tag links, favorites and recent views cascade; usage events and custom copies keep a NULL reference
    db.commit()


# ----------------------------------------------------------------------- usage
def record_view(db: Session, p: m.Prompt) -> None:
    profile = get_profile(db)
    p.view_count = (p.view_count or 0) + 1
    db.add(m.PromptUsageEvent(prompt_id=p.id, event_type="view"))
    row = db.scalar(select(m.RecentlyViewedPrompt).where(m.RecentlyViewedPrompt.profile_id == profile.id, m.RecentlyViewedPrompt.prompt_id == p.id))
    if row:
        row.viewed_at = utcnow()
    else:
        db.add(m.RecentlyViewedPrompt(profile_id=profile.id, prompt_id=p.id))
    db.commit()
    old = db.scalars(select(m.RecentlyViewedPrompt.id).where(m.RecentlyViewedPrompt.profile_id == profile.id)
                     .order_by(m.RecentlyViewedPrompt.viewed_at.desc()).offset(RECENT_LIMIT)).all()
    if old:
        db.execute(delete(m.RecentlyViewedPrompt).where(m.RecentlyViewedPrompt.id.in_(old)))
        db.commit()


def record_copy(db: Session, p: m.Prompt) -> None:
    p.copy_count = (p.copy_count or 0) + 1
    db.add(m.PromptUsageEvent(prompt_id=p.id, event_type="copy"))
    db.commit()


def record_event(db: Session, event: str, prompt_id: int | None = None) -> None:
    db.add(m.PromptUsageEvent(prompt_id=prompt_id, event_type=event[:40]))
    db.commit()


def recently_viewed(db: Session, limit: int = 6) -> list[m.Prompt]:
    profile = get_profile(db)
    q = (select(m.Prompt).join(m.RecentlyViewedPrompt, m.RecentlyViewedPrompt.prompt_id == m.Prompt.id)
         .where(m.RecentlyViewedPrompt.profile_id == profile.id, m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
         .order_by(m.RecentlyViewedPrompt.viewed_at.desc()).limit(limit))
    return list(db.scalars(q).unique())


def related_prompts(db: Session, p: m.Prompt, limit: int = 4) -> list[m.Prompt]:
    tag_ids = [t.id for t in p.tags]
    shared = func.count(m.PromptTag.tag_id)
    q = (select(m.Prompt, shared.label("shared"))
         .outerjoin(m.PromptTag, (m.PromptTag.prompt_id == m.Prompt.id) & (m.PromptTag.tag_id.in_(tag_ids or [-1])))
         .where(m.Prompt.id != p.id, m.Prompt.published.is_(True), m.Prompt.archived.is_(False))
         .group_by(m.Prompt.id)
         .order_by((m.Prompt.category_id == p.category_id).desc(), shared.desc(), m.Prompt.view_count.desc())
         .limit(limit))
    return [row[0] for row in db.execute(q).unique()]


def prompt_of_the_day(db: Session) -> m.Prompt | None:
    ids = list(db.scalars(select(m.Prompt.id).where(m.Prompt.published.is_(True), m.Prompt.archived.is_(False)).order_by(m.Prompt.id)))
    if not ids:
        return None
    day = utcnow().date().toordinal()
    return db.get(m.Prompt, ids[day % len(ids)])


# ----------------------------------------------------------------------- favorites
def add_favorite(db: Session, prompt_id: int) -> bool:
    p = get_prompt(db, prompt_id)
    profile = get_profile(db)
    if db.scalar(select(m.Favorite.id).where(m.Favorite.profile_id == profile.id, m.Favorite.prompt_id == p.id)):
        return False
    db.add(m.Favorite(profile_id=profile.id, prompt_id=p.id))
    db.commit()
    return True


def remove_favorite(db: Session, prompt_id: int) -> bool:
    profile = get_profile(db)
    res = db.execute(delete(m.Favorite).where(m.Favorite.profile_id == profile.id, m.Favorite.prompt_id == prompt_id))
    db.commit()
    return res.rowcount > 0
