"""Learning modules, progress, glossary and before/after examples (read side + admin writes)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.security import utcnow
from app.database import models as m
from app.schemas.learning import ExampleIn, GlossaryIn, LearningModuleIn
from app.services.prompt_service import get_profile
from app.services.scoring_service import scoring_service
from app.utilities.text_utils import clean_text, slugify, unique_list


def module_dict(mod: m.LearningModule, completed: set[int] | None = None, with_answers: bool = True) -> dict:
    d = {"id": mod.id, "number": mod.number, "slug": mod.slug, "title": mod.title, "summary": mod.summary, "objective": mod.objective,
         "explanation": mod.explanation, "good_example": mod.good_example, "weak_example": mod.weak_example, "tips": mod.tips or [],
         "common_mistakes": mod.common_mistakes or [], "published": mod.published, "completed": bool(completed and mod.id in completed),
         "checks": [{"id": c.id, "question": c.question, "options": c.options, "explanation": c.explanation,
                     **({"correct_index": c.correct_index} if with_answers else {})} for c in mod.checks]}
    return d


def completed_ids(db: Session) -> set[int]:
    pid = get_profile(db).id
    return set(db.scalars(select(m.LearningProgress.module_id).where(m.LearningProgress.profile_id == pid, m.LearningProgress.completed.is_(True))))


def list_modules(db: Session, include_hidden: bool = False) -> list[m.LearningModule]:
    q = select(m.LearningModule).order_by(m.LearningModule.number)
    if not include_hidden:
        q = q.where(m.LearningModule.published.is_(True), m.LearningModule.archived.is_(False))
    return list(db.scalars(q).unique())


def get_module(db: Session, key: str | int, include_hidden: bool = False) -> m.LearningModule:
    mod = db.get(m.LearningModule, int(key)) if str(key).isdigit() else db.scalar(select(m.LearningModule).where(m.LearningModule.slug == key))
    if mod is None or (not include_hidden and (not mod.published or mod.archived)):
        raise NotFound("That lesson could not be found.")
    return mod


def set_progress(db: Session, module_id: int, completed: bool) -> dict:
    mod = get_module(db, module_id)
    pid = get_profile(db).id
    row = db.scalar(select(m.LearningProgress).where(m.LearningProgress.profile_id == pid, m.LearningProgress.module_id == mod.id))
    if row is None:
        row = m.LearningProgress(profile_id=pid, module_id=mod.id)
        db.add(row)
    row.completed = completed
    row.completed_at = utcnow() if completed else None
    db.commit()
    return progress(db)


def progress(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(m.LearningModule).where(m.LearningModule.published.is_(True), m.LearningModule.archived.is_(False))) or 0
    done = completed_ids(db)
    visible = set(db.scalars(select(m.LearningModule.id).where(m.LearningModule.published.is_(True), m.LearningModule.archived.is_(False))))
    n = len(done & visible)
    return {"completed": n, "total": total, "percent": round(100 * n / total) if total else 0, "completed_ids": sorted(done & visible)}


def next_incomplete(db: Session) -> m.LearningModule | None:
    done = completed_ids(db)
    for mod in list_modules(db):
        if mod.id not in done:
            return mod
    return None


# ------------------------------------------------------------------ admin writes
def save_module(db: Session, data: LearningModuleIn, module_id: int | None = None) -> m.LearningModule:
    if not data.explanation.strip() or not data.objective.strip():
        raise ValidationFailed("A lesson needs an objective and an explanation.")
    for chk in data.checks:
        if chk.correct_index >= len(chk.options):
            raise ValidationFailed("A knowledge check's correct answer must match one of its options.")
    mod = get_module(db, module_id, True) if module_id else m.LearningModule()
    clash = db.scalar(select(m.LearningModule.id).where(m.LearningModule.number == data.number, m.LearningModule.id != (module_id or -1)))
    if clash:
        raise Conflict(f"Lesson number {data.number} is already used.")
    try:
        mod.number, mod.title = data.number, clean_text(data.title, 200)
        mod.slug = slugify(f"{data.number}-{data.title}", 110) if not module_id else mod.slug
        mod.summary, mod.objective = clean_text(data.summary), clean_text(data.objective)
        mod.explanation, mod.good_example, mod.weak_example = clean_text(data.explanation), clean_text(data.good_example), clean_text(data.weak_example)
        mod.tips, mod.common_mistakes = unique_list(data.tips), unique_list(data.common_mistakes)
        mod.published = data.published
        mod.checks = [m.KnowledgeCheck(question=clean_text(c.question), options=[clean_text(o, 300) for o in c.options],
                                       correct_index=c.correct_index, explanation=clean_text(c.explanation)) for c in data.checks]
        db.add(mod)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("That lesson conflicts with an existing lesson (duplicate title or number).") from exc
    return mod


def set_module_flags(db: Session, module_id: int, **flags) -> m.LearningModule:
    mod = get_module(db, module_id, True)
    for k, v in flags.items():
        setattr(mod, k, bool(v))
    db.commit()
    return mod


# ------------------------------------------------------------------ glossary
def glossary(db: Session, include_hidden: bool = False) -> list[m.GlossaryTerm]:
    q = select(m.GlossaryTerm).order_by(func.lower(m.GlossaryTerm.term))
    if not include_hidden:
        q = q.where(m.GlossaryTerm.published.is_(True))
    return list(db.scalars(q))


def save_term(db: Session, data: GlossaryIn, term_id: int | None = None) -> m.GlossaryTerm:
    t = db.get(m.GlossaryTerm, term_id) if term_id else m.GlossaryTerm()
    if t is None:
        raise NotFound("Glossary term not found.")
    dup = db.scalar(select(m.GlossaryTerm.id).where(func.lower(m.GlossaryTerm.term) == data.term.strip().lower(), m.GlossaryTerm.id != (term_id or -1)))
    if dup:
        raise Conflict(f"The term '{data.term}' already exists.")
    t.term, t.definition, t.example, t.published = clean_text(data.term, 100), clean_text(data.definition), clean_text(data.example), data.published
    db.add(t)
    db.commit()
    return t


def delete_term(db: Session, term_id: int) -> None:
    t = db.get(m.GlossaryTerm, term_id)
    if t is None:
        raise NotFound("Glossary term not found.")
    db.delete(t)
    db.commit()


# ------------------------------------------------------------------ examples
def example_dict(e: m.BeforeAfterExample) -> dict:
    return {"id": e.id, "slug": e.slug, "scenario": e.scenario, "description": e.description, "weak_prompt": e.weak_prompt,
            "problems": e.problems or [], "improved_prompt": e.improved_prompt, "improvements": e.improvements or [],
            "why_better": e.why_better, "expected_difference": e.expected_difference, "weak_score": e.weak_score,
            "improved_score": e.improved_score, "published": e.published, "archived": e.archived, "sort_order": e.sort_order}


def examples(db: Session, include_hidden: bool = False) -> list[m.BeforeAfterExample]:
    q = select(m.BeforeAfterExample).order_by(m.BeforeAfterExample.sort_order, m.BeforeAfterExample.id)
    if not include_hidden:
        q = q.where(m.BeforeAfterExample.published.is_(True), m.BeforeAfterExample.archived.is_(False))
    return list(db.scalars(q))


def save_example(db: Session, data: ExampleIn, example_id: int | None = None) -> m.BeforeAfterExample:
    e = db.get(m.BeforeAfterExample, example_id) if example_id else m.BeforeAfterExample()
    if e is None:
        raise NotFound("Example not found.")
    slug = e.slug if example_id else slugify(data.scenario, 100)
    if db.scalar(select(m.BeforeAfterExample.id).where(m.BeforeAfterExample.slug == slug, m.BeforeAfterExample.id != (example_id or -1))):
        raise Conflict(f"An example with the slug '{slug}' already exists.")
    e.slug, e.scenario, e.description = slug, clean_text(data.scenario, 200), clean_text(data.description)
    e.weak_prompt, e.improved_prompt = clean_text(data.weak_prompt), clean_text(data.improved_prompt)
    e.problems, e.improvements = unique_list(data.problems), unique_list(data.improvements)
    e.why_better, e.expected_difference = clean_text(data.why_better), clean_text(data.expected_difference)
    e.sort_order, e.published = data.sort_order, data.published
    e.weak_score = scoring_service.analyze(e.weak_prompt)["score"]
    e.improved_score = scoring_service.analyze(e.improved_prompt)["score"]
    db.add(e)
    db.commit()
    return e


def set_example_flags(db: Session, example_id: int, **flags) -> m.BeforeAfterExample:
    e = db.get(m.BeforeAfterExample, example_id)
    if e is None:
        raise NotFound("Example not found.")
    for k, v in flags.items():
        setattr(e, k, bool(v))
    db.commit()
    return e
