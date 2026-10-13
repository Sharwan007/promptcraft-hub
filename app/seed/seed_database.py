"""Idempotent seed loader.

Each content table is seeded only when it is empty *and* it has never been seeded before
(tracked with ``seeded:<table>`` app settings). A restart therefore never overwrites or
re-adds content, even if a user deliberately deleted everything.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import models as m
from app.services.scoring_service import scoring_service
from app.utilities.text_utils import slugify

logger = logging.getLogger("promptcraft.seed")
SEED_DIR = Path(__file__).resolve().parent


def _load(name: str) -> dict:
    with (SEED_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _flag(db: Session, table: str) -> bool:
    return db.get(m.AppSetting, f"seeded:{table}") is not None


def _set_flag(db: Session, table: str) -> None:
    db.merge(m.AppSetting(key=f"seeded:{table}", value="1"))


def _empty(db: Session, model) -> bool:
    return (db.scalar(select(func.count()).select_from(model)) or 0) == 0


def _should_seed(db: Session, model, table: str, ignore_flags: bool) -> bool:
    if not _empty(db, model):
        return False
    return ignore_flags or not _flag(db, table)


def seed_categories_and_prompts(db: Session, ignore_flags: bool = False) -> int:
    if not _should_seed(db, m.Prompt, "prompts", ignore_flags):
        return 0
    data = _load("prompts.json")
    cat_by_name: dict[str, m.Category] = {c.name: c for c in db.scalars(select(m.Category))}
    for c in data["categories"]:
        cat = cat_by_name.get(c["name"])
        if cat is None:
            cat = m.Category(name=c["name"], slug=slugify(c["name"]), description=c.get("description", ""),
                             icon=c.get("icon", "folder"), sort_order=c.get("sort_order", 0))
            db.add(cat)
            db.flush()
            cat_by_name[cat.name] = cat
        existing_subs = {s.name for s in cat.subcategories}
        for sname in c.get("subcategories", []):
            if sname not in existing_subs:
                db.add(m.Subcategory(category_id=cat.id, name=sname, slug=slugify(sname)))
    db.flush()
    subs = {(s.category_id, s.name): s for s in db.scalars(select(m.Subcategory))}
    tag_cache: dict[str, m.Tag] = {t.slug: t for t in db.scalars(select(m.Tag))}
    count = 0
    for item in data["prompts"]:
        cat = cat_by_name[item["category"]]
        sub = subs.get((cat.id, item.get("subcategory")))
        tags = []
        for name in item.get("tags", []):
            slug = slugify(name, 60)
            tag = tag_cache.get(slug)
            if tag is None:
                tag = m.Tag(name=name.lower(), slug=slug)
                db.add(tag)
                db.flush()
                tag_cache[slug] = tag
            tags.append(tag)
        db.add(m.Prompt(
            title=item["title"], slug=slugify(item["title"], 200), description=item["description"], full_prompt=item["full_prompt"],
            category_id=cat.id, subcategory_id=sub.id if sub else None, user_role=item.get("user_role", ""),
            use_case=item.get("use_case", ""), ai_tools=item.get("ai_tools", ["Tool-independent"]),
            difficulty=item.get("difficulty", "Beginner"), expected_output=item.get("expected_output", ""),
            required_inputs=item.get("required_inputs", []), example_inputs=item.get("example_inputs", {}),
            example_output=item.get("example_output", ""), why_it_works=item.get("why_it_works", ""),
            customization_tips=item.get("customization_tips", []), common_mistakes=item.get("common_mistakes", []),
            constraints=item.get("constraints", []), components=item.get("components", {}),
            featured=bool(item.get("featured")), published=True, tags=tags,
        ))
        count += 1
    _set_flag(db, "prompts")
    return count


def seed_learning(db: Session, ignore_flags: bool = False) -> int:
    if not _should_seed(db, m.LearningModule, "learning", ignore_flags):
        return 0
    n = 0
    for item in _load("learning_modules.json")["modules"]:
        mod = m.LearningModule(
            number=item["number"], slug=slugify(f"{item['number']}-{item['title']}", 110), title=item["title"],
            summary=item.get("summary", ""), objective=item["objective"], explanation=item["explanation"],
            good_example=item.get("good_example", ""), weak_example=item.get("weak_example", ""),
            tips=item.get("tips", []), common_mistakes=item.get("common_mistakes", []))
        mod.checks = [m.KnowledgeCheck(question=c["question"], options=c["options"], correct_index=c["correct_index"],
                                       explanation=c.get("explanation", "")) for c in item.get("checks", [])]
        db.add(mod)
        n += 1
    _set_flag(db, "learning")
    return n


def seed_examples(db: Session, ignore_flags: bool = False) -> int:
    if not _should_seed(db, m.BeforeAfterExample, "examples", ignore_flags):
        return 0
    n = 0
    for item in _load("examples.json")["examples"]:
        db.add(m.BeforeAfterExample(
            slug=slugify(item["scenario"], 100), scenario=item["scenario"], description=item.get("description", ""),
            weak_prompt=item["weak_prompt"], problems=item.get("problems", []), improved_prompt=item["improved_prompt"],
            improvements=item.get("improvements", []), why_better=item.get("why_better", ""),
            expected_difference=item.get("expected_difference", ""),
            weak_score=scoring_service.analyze(item["weak_prompt"])["score"],
            improved_score=scoring_service.analyze(item["improved_prompt"])["score"],
            sort_order=item.get("sort_order", 0)))
        n += 1
    _set_flag(db, "examples")
    return n


def seed_glossary(db: Session, ignore_flags: bool = False) -> int:
    if not _should_seed(db, m.GlossaryTerm, "glossary", ignore_flags):
        return 0
    n = 0
    for item in _load("glossary.json")["terms"]:
        db.add(m.GlossaryTerm(term=item["term"], definition=item["definition"], example=item.get("example", "")))
        n += 1
    _set_flag(db, "glossary")
    return n


def seed_all(db: Session, ignore_flags: bool = False) -> dict:
    """Seed every empty table in its own transaction. Safe to call repeatedly."""
    counts: dict[str, int] = {}
    for name, fn in (("prompts", seed_categories_and_prompts), ("learning_modules", seed_learning),
                     ("examples", seed_examples), ("glossary_terms", seed_glossary)):
        try:
            counts[name] = fn(db, ignore_flags)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Seeding %s failed and was rolled back", name)
            raise
    if any(counts.values()):
        logger.info("Seed data loaded: %s", counts)
    return counts
