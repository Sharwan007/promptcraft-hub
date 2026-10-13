"""Prompt library, search, scoring, diagnosis, improvement and building endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, optional_admin, require_admin
from app.core.exceptions import ValidationFailed
from app.schemas.common import Message, Page
from app.schemas.improver import AnalyzeIn, BuildIn, ImproveIn, RenderIn
from app.schemas.prompt import PromptCreate, PromptOut, PromptSummary, PromptUpdate
from app.services import builder_service, export_service, prompt_service, search_service
from app.services.improver_service import improve_prompt
from app.services.scoring_service import parse_sections, scoring_service
from app.utilities.text_utils import clean_text

router = APIRouter(prefix="/api/prompts", tags=["Prompts"])
search_router = APIRouter(prefix="/api/search", tags=["Search"])


class FlagsIn(BaseModel):
    published: bool | None = None
    featured: bool | None = None
    archived: bool | None = None


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


def filters_from_query(q: str = "", category: str = "", subcategory: str = "", ai_tool: str = "", difficulty: str = "",
                       role: str = "", tag: str = "", featured: bool = False, sort: str = "relevance",
                       page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60)) -> search_service.PromptFilters:
    return search_service.PromptFilters(q=q, category=category, subcategory=subcategory, ai_tool=ai_tool, difficulty=difficulty,
                                        role=role, tag=tag, featured=featured, sort=sort, page=page, page_size=page_size)


@search_router.get("/suggestions", summary="Search suggestions for the typed text")
def suggestions(q: str = "", db: Session = Depends(get_db)) -> dict:
    return {"query": q, "suggestions": search_service.suggest(db, q)}


@router.get("", response_model=Page[PromptSummary], summary="Search and filter prompts")
def list_prompts(f: search_service.PromptFilters = Depends(filters_from_query), db: Session = Depends(get_db)):
    fav = prompt_service.favorite_ids(db)
    res = search_service.search_prompts(db, f)
    res["items"] = [prompt_service.summary_dict(p, fav) for p in res["items"]]
    return res


@router.get("/facets", summary="Filter options (categories, roles, tags...)")
def get_facets(db: Session = Depends(get_db)) -> dict:
    return search_service.facets(db)


# ----------------------------------------------------------------- analysis tools (no data is stored)
@router.post("/analyze", summary="Score a prompt (0-100) with a transparent breakdown")
def analyze(body: AnalyzeIn, db: Session = Depends(get_db)) -> dict:
    prompt_service.record_event(db, "analyze")
    return scoring_service.analyze(body.prompt, body.use_case)


@router.post("/diagnose", summary="Diagnose which prompt components are present or missing")
def diagnose(body: AnalyzeIn, db: Session = Depends(get_db)) -> dict:
    prompt_service.record_event(db, "diagnose")
    return scoring_service.diagnose(body.prompt, body.use_case)


@router.post("/improve", summary="Improve a prompt with the rule-based improver")
def improve(body: ImproveIn, db: Session = Depends(get_db)) -> dict:
    prompt_service.record_event(db, "improve")
    return improve_prompt(body.prompt, body.options.model_dump())


@router.post("/build", summary="Generate a prompt from Blueprint fields")
def build(body: BuildIn, db: Session = Depends(get_db)) -> dict:
    prompt_service.record_event(db, "build")
    return builder_service.build(body.model_dump())


@router.get("/build/options", summary="Purposes, output formats and constraint options for the builder")
def build_options() -> dict:
    return builder_service.catalog()


@router.post("/parse", summary="Split a structured prompt into Blueprint components")
def parse(body: ParseIn) -> dict:
    text = clean_text(body.text)
    sections = parse_sections(text)
    first = text.splitlines()[0].strip() if text else ""
    role = sections.get("role", "")
    if not role and first.lower().startswith(("act as", "you are")):
        role = first.rstrip(".")
    return {"role": role, "context": sections.get("context", ""), "task": sections.get("task", "") or (text if not sections else ""),
            "inputs": sections.get("input", ""), "output_text": sections.get("output_format", ""),
            "constraints_text": sections.get("constraints", ""), "quality_criteria": sections.get("quality_criteria", ""),
            "audience": sections.get("audience", ""), "tone": sections.get("tone", "")}


@router.post("/render", summary="Render prompt text as a TXT, Markdown or JSON download")
def render(body: RenderIn) -> Response:
    data, mime, filename = export_service.render_text(body.title, body.content, body.format)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ----------------------------------------------------------------- library records
@router.get("/{key}", response_model=PromptOut, summary="Get one prompt by id or slug")
def get_prompt(key: str, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)):
    p = prompt_service.get_prompt(db, key, include_hidden=is_admin)
    return prompt_service.prompt_dict(p, prompt_service.favorite_ids(db))


@router.post("", response_model=PromptOut, status_code=201, summary="Create a prompt (admin)")
def create_prompt(body: PromptCreate, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    return prompt_service.prompt_dict(prompt_service.create_prompt(db, body))


@router.put("/{prompt_id}", response_model=PromptOut, summary="Update a prompt (admin)")
def update_prompt(prompt_id: int, body: PromptUpdate, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    return prompt_service.prompt_dict(prompt_service.update_prompt(db, prompt_id, body))


@router.patch("/{prompt_id}/flags", summary="Publish, feature or archive a prompt (admin)")
def set_flags(prompt_id: int, body: FlagsIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    flags = {k: v for k, v in body.model_dump().items() if v is not None}
    if not flags:
        raise ValidationFailed("Provide at least one of: published, featured, archived.")
    p = prompt_service.set_flags(db, prompt_id, **flags)
    return {"id": p.id, "published": p.published, "featured": p.featured, "archived": p.archived}


@router.delete("/{prompt_id}", summary="Archive a prompt, or delete it permanently with ?permanent=true (admin)")
def delete_prompt(prompt_id: int, permanent: bool = False, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    if permanent:
        prompt_service.delete_permanently(db, prompt_id)
        return Message(message="The prompt was permanently deleted.")
    prompt_service.set_flags(db, prompt_id, archived=True)
    return Message(message="The prompt was archived. You can restore it from Administration.")


@router.post("/{prompt_id}/copy", summary="Record that a prompt was copied")
def record_copy(prompt_id: int, db: Session = Depends(get_db)) -> dict:
    p = prompt_service.get_prompt(db, prompt_id)
    prompt_service.record_copy(db, p)
    return {"id": p.id, "copy_count": p.copy_count}


@router.get("/{prompt_id}/export", summary="Export a prompt as txt, md or json")
def export_prompt(prompt_id: int, format: str = Query("txt", pattern="^(txt|md|json)$"), db: Session = Depends(get_db)) -> Response:
    p = prompt_service.get_prompt(db, prompt_id)
    prompt_service.record_event(db, "export", p.id)
    data, mime, filename = export_service.export_prompt(p, format)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
