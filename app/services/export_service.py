"""Export (TXT / Markdown / JSON), library export, and validated JSON import."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailed
from app.database import models as m
from app.schemas.prompt import PromptCreate
from app.services import prompt_service
from app.utilities.file_utils import parse_json_bytes
from app.utilities.text_utils import safe_filename, slugify

FORMAT_FORMAT = "promptcraft-library"
FORMAT_VERSION = 1
MIME = {"txt": "text/plain; charset=utf-8", "md": "text/markdown; charset=utf-8", "json": "application/json; charset=utf-8"}


def render_text(title: str, content: str, fmt: str, meta: dict | None = None) -> tuple[bytes, str, str]:
    """Return (bytes, mime, filename) for a title + prompt body."""
    if fmt not in MIME:
        raise ValidationFailed("Export format must be txt, md or json.")
    meta = meta or {}
    if fmt == "txt":
        body = f"{title}\n{'=' * len(title)}\n\n{content}\n"
    elif fmt == "md":
        lines = [f"# {title}", ""]
        for k, v in meta.items():
            if v:
                lines.append(f"- **{k}:** {', '.join(v) if isinstance(v, list) else v}")
        if meta:
            lines.append("")
        lines += ["```text", content, "```", ""]
        body = "\n".join(lines)
    else:
        body = json.dumps({"title": title, "prompt": content, **meta, "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                          ensure_ascii=False, indent=2)
    return body.encode("utf-8"), MIME[fmt], safe_filename(title, fmt)


def prompt_export_dict(p: m.Prompt) -> dict:
    return {
        "title": p.title, "slug": p.slug, "description": p.description, "full_prompt": p.full_prompt,
        "category": p.category.name, "subcategory": p.subcategory.name if p.subcategory else None,
        "user_role": p.user_role, "use_case": p.use_case, "ai_tools": p.ai_tools or [], "difficulty": p.difficulty,
        "tags": [t.name for t in p.tags], "expected_output": p.expected_output, "required_inputs": p.required_inputs or [],
        "example_inputs": p.example_inputs or {}, "example_output": p.example_output, "why_it_works": p.why_it_works,
        "customization_tips": p.customization_tips or [], "common_mistakes": p.common_mistakes or [],
        "constraints": p.constraints or [], "components": p.components or {}, "featured": p.featured, "published": p.published,
    }


def export_prompt(p: m.Prompt, fmt: str) -> tuple[bytes, str, str]:
    meta = {"Category": p.category.name, "Difficulty": p.difficulty, "AI tools": p.ai_tools or [], "Tags": [t.name for t in p.tags]}
    if fmt == "json":
        data = json.dumps({"format": FORMAT_FORMAT, "version": FORMAT_VERSION, "prompts": [prompt_export_dict(p)]}, ensure_ascii=False, indent=2)
        return data.encode("utf-8"), MIME["json"], safe_filename(p.title, "json")
    body = p.full_prompt
    if fmt == "md" and p.why_it_works:
        pass
    return render_text(p.title, body, fmt, meta if fmt == "md" else None)


def export_library(db: Session) -> bytes:
    prompts = list(db.scalars(select(m.Prompt).order_by(m.Prompt.id)).unique())
    cats = list(db.scalars(select(m.Category).order_by(m.Category.sort_order, m.Category.name)))
    payload = {
        "format": FORMAT_FORMAT, "version": FORMAT_VERSION, "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": [{"name": c.name, "description": c.description, "icon": c.icon, "subcategories": [s.name for s in c.subcategories]} for c in cats],
        "prompts": [{**prompt_export_dict(p), "archived": p.archived} for p in prompts],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_custom(db: Session, items: list[m.CustomPrompt], fmt: str) -> tuple[bytes, str, str]:
    if fmt == "json":
        data = {"format": "promptcraft-custom-prompts", "version": 1,
                "prompts": [{"title": c.title, "description": c.description, "content": c.content, "tags": c.tags or [], "version": c.version} for c in items]}
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), MIME["json"], "my-prompts.json"
    if fmt not in ("txt", "md"):
        raise ValidationFailed("Export format must be txt, md or json.")
    chunks = []
    for c in items:
        chunks.append(f"{'# ' if fmt == 'md' else ''}{c.title}\n\n{c.content}\n")
    body = ("\n---\n\n" if fmt == "md" else "\n" + "=" * 40 + "\n\n").join(chunks)
    return body.encode("utf-8"), MIME[fmt], f"my-prompts.{fmt}"


# ------------------------------------------------------------------ import
def _extract_items(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("prompts"), list):
        return payload["prompts"]
    raise ValidationFailed("The JSON must be a list of prompts or an object with a 'prompts' list.",
                           hint="Download a library export or samples/sample_prompt_import.json to see the expected format.")


def _fmt_errors(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e["loc"])
        out.append(f"{loc}: {e['msg']}")
    return out


def analyze_import(db: Session, data: bytes, duplicates: str = "skip") -> dict:
    """Validate an import file without writing. Returns a per-item report."""
    payload = parse_json_bytes(data)
    items = _extract_items(payload)
    if not items:
        raise ValidationFailed("The file contains no prompts.")
    if len(items) > 2000:
        raise ValidationFailed("An import may contain at most 2000 prompts.")
    valid_cats = {c.lower() for c in db.scalars(select(m.Category.name).where(m.Category.archived.is_(False)))}
    existing = {s for s in db.scalars(select(m.Prompt.slug))}
    seen: set[str] = set()
    report = []
    for i, raw in enumerate(items, start=1):
        entry = {"index": i, "title": str(raw.get("title", ""))[:80] if isinstance(raw, dict) else "", "status": "new", "errors": []}
        if not isinstance(raw, dict):
            entry.update(status="invalid", errors=["Each prompt must be a JSON object."])
            report.append(entry)
            continue
        try:
            item = PromptCreate.model_validate({k: v for k, v in raw.items() if k not in ("archived", "id", "created_at", "updated_at", "version", "view_count", "copy_count")})
        except ValidationError as exc:
            entry.update(status="invalid", errors=_fmt_errors(exc))
            report.append(entry)
            continue
        if not item.category or item.category.strip().lower() not in valid_cats:
            entry["errors"].append(f"category: '{item.category}' is not an existing category.")
        slug = slugify(item.slug or item.title, 200)
        entry["slug"] = slug
        if slug in seen:
            entry["errors"].append(f"slug: '{slug}' appears more than once in the file.")
        seen.add(slug)
        if entry["errors"]:
            entry["status"] = "invalid"
        elif slug in existing:
            entry["status"] = "duplicate"
        report.append(entry)
    summary = {s: sum(1 for r in report if r["status"] == s) for s in ("new", "duplicate", "invalid")}
    return {"total": len(report), "summary": summary, "items": report, "duplicates_mode": duplicates, "_items": items}


def run_import(db: Session, data: bytes, filename: str, duplicates: str = "skip", on_error: str = "abort") -> dict:
    if duplicates not in ("skip", "update"):
        raise ValidationFailed("Duplicate handling must be 'skip' or 'update'.")
    if on_error not in ("abort", "skip_invalid"):
        raise ValidationFailed("Error handling must be 'abort' or 'skip_invalid'.")
    rep = analyze_import(db, data, duplicates)
    raw_items = rep.pop("_items")
    errors = [f"#{r['index']} {r['title']!r}: {e}" for r in rep["items"] for e in r["errors"]]
    hist = m.ImportHistory(filename=filename, mode=f"{duplicates}/{on_error}", total=rep["total"], errors=errors, error_count=len(errors))
    if errors and on_error == "abort":
        hist.status = "aborted"
        db.add(hist)
        db.commit()
        return {**rep, "status": "aborted", "history_id": hist.id, "created": 0, "updated": 0, "skipped": 0,
                "message": "Import aborted: the file contains errors. Nothing was imported."}
    created = updated = skipped = 0
    try:
        for entry, raw in zip(rep["items"], raw_items):
            if entry["status"] == "invalid":
                skipped += 1
                continue
            item = PromptCreate.model_validate({k: v for k, v in raw.items() if k not in ("archived", "id", "created_at", "updated_at", "version", "view_count", "copy_count")})
            if entry["status"] == "duplicate":
                if duplicates == "skip":
                    skipped += 1
                    continue
                existing = db.scalar(select(m.Prompt).where(m.Prompt.slug == entry["slug"]))
                item.slug = entry["slug"]
                _update_in_txn(db, existing, item)
                updated += 1
            else:
                item.slug = entry["slug"]
                _create_in_txn(db, item)
                created += 1
        hist.created_count, hist.updated_count, hist.skipped_count, hist.status = created, updated, skipped, "completed"
        db.add(hist)
        db.commit()
    except Exception:
        db.rollback()
        h2 = m.ImportHistory(filename=filename, mode=f"{duplicates}/{on_error}", total=rep["total"], status="failed",
                             errors=["The import failed unexpectedly and was rolled back. See the application log."], error_count=1)
        db.add(h2)
        db.commit()
        raise
    return {**rep, "status": "completed", "history_id": hist.id, "created": created, "updated": updated, "skipped": skipped,
            "message": f"Import complete: {created} created, {updated} updated, {skipped} skipped."}


def _create_in_txn(db: Session, data: PromptCreate) -> None:
    p = m.Prompt(slug=data.slug, version=1)
    prompt_service._apply(p, db, data)
    db.add(p)
    db.flush()


def _update_in_txn(db: Session, p: m.Prompt, data: PromptCreate) -> None:
    if data.full_prompt.strip() != p.full_prompt:
        p.version += 1
    prompt_service._apply(p, db, data)
    db.flush()


def import_error_report(db: Session, history_id: int) -> bytes:
    h = db.get(m.ImportHistory, history_id)
    if h is None:
        raise ValidationFailed("That import record does not exist.")
    lines = [f"PromptCraft Hub import report", f"File: {h.filename}", f"Status: {h.status}", f"Date (UTC): {h.created_at:%Y-%m-%d %H:%M:%S}",
             f"Total: {h.total}  Created: {h.created_count}  Updated: {h.updated_count}  Skipped: {h.skipped_count}  Errors: {h.error_count}", ""]
    lines += h.errors or ["No errors recorded."]
    return ("\n".join(lines) + "\n").encode("utf-8")
