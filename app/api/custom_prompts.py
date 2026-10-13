"""My Prompts: custom prompts with versions, archive and restore."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import ValidationFailed
from app.schemas.prompt import CustomPromptIn, CustomPromptOut, CustomVersionOut
from app.services import custom_service, export_service, prompt_service

router = APIRouter(prefix="/api/custom-prompts", tags=["My prompts"])


class DuplicateIn(BaseModel):
    content: str | None = Field(default=None, max_length=20000)


@router.get("", summary="List and search my prompts")
def list_custom(q: str = "", category_id: int | None = None, archived: bool = False, tag: str = "",
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    return custom_service.list_custom(db, q, category_id, archived, tag, page, page_size)


@router.get("/export", summary="Export my prompts as txt, md or json")
def export_many(format: str = Query("json", pattern="^(txt|md|json)$"), archived: bool = False, db: Session = Depends(get_db)) -> Response:
    items = custom_service.list_custom(db, archived=archived, page_size=100)["items"]
    rows = [custom_service.get_custom(db, i["id"]) for i in items]
    data, mime, filename = export_service.export_custom(db, rows, format)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("", response_model=CustomPromptOut, status_code=201, summary="Create a custom prompt")
def create_custom(body: CustomPromptIn, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.create_custom(db, body))


@router.post("/from-prompt/{prompt_id}", response_model=CustomPromptOut, status_code=201, summary="Duplicate a library prompt into My Prompts")
def duplicate(prompt_id: int, body: DuplicateIn | None = None, db: Session = Depends(get_db)):
    created = custom_service.duplicate_from_library(db, prompt_id, body.content if body else None)
    prompt_service.record_event(db, "customize", prompt_id)
    return custom_service.to_dict(created)


@router.get("/{cid}", response_model=CustomPromptOut, summary="Get a custom prompt")
def get_custom(cid: int, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.get_custom(db, cid))


@router.put("/{cid}", response_model=CustomPromptOut, summary="Edit a custom prompt (creates a new version when content changes)")
def update_custom(cid: int, body: CustomPromptIn, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.update_custom(db, cid, body))


@router.post("/{cid}/archive", response_model=CustomPromptOut, summary="Archive a custom prompt")
def archive(cid: int, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.set_archived(db, cid, True))


@router.post("/{cid}/restore", response_model=CustomPromptOut, summary="Restore an archived custom prompt")
def restore(cid: int, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.set_archived(db, cid, False))


@router.delete("/{cid}", summary="Permanently delete a custom prompt (requires ?permanent=true)")
def delete(cid: int, permanent: bool = False, db: Session = Depends(get_db)) -> dict:
    if not permanent:
        raise ValidationFailed("Deleting is permanent and was not confirmed.",
                               hint="Use POST /api/custom-prompts/{id}/archive to archive, or add ?permanent=true to delete for good.")
    custom_service.delete_permanently(db, cid)
    return {"deleted": True, "id": cid}


@router.get("/{cid}/versions", response_model=list[CustomVersionOut], summary="Version history")
def versions(cid: int, db: Session = Depends(get_db)):
    return custom_service.versions(db, cid)


@router.post("/{cid}/versions/{version}/restore", response_model=CustomPromptOut, summary="Restore an earlier version as a new version")
def restore_version(cid: int, version: int, db: Session = Depends(get_db)):
    return custom_service.to_dict(custom_service.restore_version(db, cid, version))


@router.get("/{cid}/export", summary="Export one custom prompt")
def export_one(cid: int, format: str = Query("txt", pattern="^(txt|md|json)$"), db: Session = Depends(get_db)) -> Response:
    c = custom_service.get_custom(db, cid)
    if format == "json":
        data, mime, _ = export_service.export_custom(db, [c], "json")
        name = export_service.safe_filename(c.title, "json")
    else:
        data, mime, name = export_service.render_text(c.title, c.content, format)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
