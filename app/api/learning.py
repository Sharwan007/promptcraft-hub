"""Learning modules, progress and glossary."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, optional_admin, require_admin
from app.schemas.common import Message
from app.schemas.learning import GlossaryIn, LearningModuleIn, ProgressIn
from app.services import learning_service as ls

router = APIRouter(tags=["Learning"])


class FlagsIn(BaseModel):
    published: bool | None = None
    archived: bool | None = None


@router.get("/api/learning/modules", summary="List learning modules with completion state")
def list_modules(db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> list[dict]:
    done = ls.completed_ids(db)
    return [ls.module_dict(x, done) for x in ls.list_modules(db, include_hidden=is_admin)]


@router.get("/api/learning/modules/{key}", summary="Get one lesson by id or slug")
def get_module(key: str, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> dict:
    return ls.module_dict(ls.get_module(db, key, include_hidden=is_admin), ls.completed_ids(db))


@router.post("/api/learning/modules", status_code=201, summary="Create a lesson (admin)")
def create_module(body: LearningModuleIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    return ls.module_dict(ls.save_module(db, body))


@router.put("/api/learning/modules/{module_id}", summary="Update a lesson (admin)")
def update_module(module_id: int, body: LearningModuleIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    return ls.module_dict(ls.save_module(db, body, module_id))


@router.patch("/api/learning/modules/{module_id}/flags", summary="Publish or archive a lesson (admin)")
def module_flags(module_id: int, body: FlagsIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    mod = ls.set_module_flags(db, module_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return {"id": mod.id, "published": mod.published, "archived": mod.archived}


@router.delete("/api/learning/modules/{module_id}", summary="Delete a lesson (admin)")
def delete_module(module_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    mod = ls.get_module(db, module_id, include_hidden=True)
    db.delete(mod)
    db.commit()
    return Message(message="The lesson was deleted.")


@router.get("/api/learning/progress", summary="Learning progress")
def get_progress(db: Session = Depends(get_db)) -> dict:
    return ls.progress(db)


@router.post("/api/learning/progress", summary="Mark a lesson complete or incomplete")
def set_progress(body: ProgressIn, db: Session = Depends(get_db)) -> dict:
    return ls.set_progress(db, body.module_id, body.completed)


@router.get("/api/glossary", summary="Glossary terms")
def list_glossary(db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> list[dict]:
    return [{"id": t.id, "term": t.term, "definition": t.definition, "example": t.example, "published": t.published}
            for t in ls.glossary(db, include_hidden=is_admin)]


@router.post("/api/glossary", status_code=201, summary="Create a glossary term (admin)")
def create_term(body: GlossaryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    t = ls.save_term(db, body)
    return {"id": t.id, "term": t.term}


@router.put("/api/glossary/{term_id}", summary="Update a glossary term (admin)")
def update_term(term_id: int, body: GlossaryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    t = ls.save_term(db, body, term_id)
    return {"id": t.id, "term": t.term}


@router.delete("/api/glossary/{term_id}", summary="Delete a glossary term (admin)")
def delete_term(term_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    ls.delete_term(db, term_id)
    return Message(message="The term was deleted.")
