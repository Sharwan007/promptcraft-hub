"""Before & After examples."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, optional_admin, require_admin
from app.core.exceptions import NotFound
from app.database import models as m
from app.schemas.common import Message
from app.schemas.learning import ExampleIn
from app.services import learning_service as ls

router = APIRouter(prefix="/api/examples", tags=["Before and after"])


@router.get("", summary="List Before & After examples with score comparison")
def list_examples(db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> list[dict]:
    return [ls.example_dict(e) for e in ls.examples(db, include_hidden=is_admin)]


@router.get("/{example_id}", summary="Get one example")
def get_example(example_id: int, db: Session = Depends(get_db)) -> dict:
    e = db.get(m.BeforeAfterExample, example_id)
    if e is None or not e.published or e.archived:
        raise NotFound("That example could not be found.")
    return ls.example_dict(e)


@router.post("", status_code=201, summary="Create an example (admin)")
def create_example(body: ExampleIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    return ls.example_dict(ls.save_example(db, body))


@router.put("/{example_id}", summary="Update an example (admin)")
def update_example(example_id: int, body: ExampleIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    return ls.example_dict(ls.save_example(db, body, example_id))


@router.delete("/{example_id}", summary="Delete an example (admin)")
def delete_example(example_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    e = db.get(m.BeforeAfterExample, example_id)
    if e is None:
        raise NotFound("Example not found.")
    db.delete(e)
    db.commit()
    return Message(message="The example was deleted.")
