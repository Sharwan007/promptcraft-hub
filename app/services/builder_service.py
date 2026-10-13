"""Prompt Blueprint builder: R(ole) C(ontext) T(ask) I(nput) O(utput) C(onstraints) Q(uality)."""
from __future__ import annotations

from app.services.scoring_service import scoring_service
from app.utilities.text_utils import clean_text

PURPOSES = {
    "write": ("Write", "email", "Write"),
    "summarize": ("Summarize", "summary", "Summarize"),
    "analyze": ("Analyze", "analysis", "Analyze"),
    "compare": ("Compare", "general", "Compare"),
    "plan": ("Plan", "project_plan", "Create a plan for"),
    "brainstorm": ("Brainstorm", "brainstorm", "Brainstorm ideas for"),
    "extract": ("Extract information", "general", "Extract the following information from the input:"),
    "transform": ("Transform content", "general", "Rewrite and restructure the input to"),
    "code": ("Create code", "code", "Write code that"),
    "troubleshoot": ("Troubleshoot", "code", "Diagnose and fix"),
    "presentation": ("Create a presentation", "presentation", "Create a presentation outline about"),
    "report": ("Create a report", "report", "Write a report about"),
    "minutes": ("Create meeting minutes", "meeting_minutes", "Turn the meeting notes into minutes that"),
    "user_stories": ("Generate user stories", "user_stories", "Write user stories for"),
    "acceptance_criteria": ("Create acceptance criteria", "acceptance_criteria", "Write acceptance criteria for"),
}

OUTPUT_FORMATS = {
    "paragraph": ("Paragraph", "Write the answer as clear, well-structured paragraphs."),
    "bullet_list": ("Bullet list", "Present the answer as a concise bullet list."),
    "numbered_steps": ("Numbered steps", "Present the answer as numbered steps in the order they should be performed."),
    "table": ("Table", "Present the answer as a table with clearly labelled columns."),
    "json": ("JSON", "Return valid JSON only, with consistent key names and no text outside the JSON."),
    "markdown": ("Markdown", "Format the answer in Markdown with headings and lists."),
    "email": ("Email", "Provide a subject line followed by the email body."),
    "report": ("Report", "Structure the answer as a report: executive summary, findings, recommendations, next steps."),
    "presentation_outline": ("Presentation outline", "Provide a numbered slide outline: slide title, key bullets and speaker notes for each slide."),
    "meeting_minutes": ("Meeting minutes", "Format as minutes: attendees, discussion summary, decisions, action items (owner, due date), open issues."),
    "user_story": ("User story", "Write each item as: 'As a [role], I want [capability] so that [benefit]'."),
    "acceptance_criteria": ("Acceptance criteria", "Write numbered criteria in Given / When / Then format."),
    "sql_query": ("SQL query", "Provide a formatted SQL query in a code block, then a short explanation of each clause."),
    "code": ("Code", "Provide complete, runnable code in a code block with brief comments, then a short explanation."),
    "custom": ("Custom format", ""),
}

CONSTRAINT_OPTIONS = {
    "tone": "Tone", "word_limit": "Word limit", "audience": "Target audience", "language": "Language",
    "reading_level": "Reading level", "num_options": "Number of options", "required_sections": "Required sections",
    "excluded_topics": "Excluded topics", "citation": "Citation requirements", "privacy": "Data privacy instruction",
    "deadline": "Deadline", "detail": "Level of detail",
}

SAMPLE = {
    "purpose": "write",
    "role": "a senior project manager with experience in stakeholder communication",
    "context": "Our data-migration project is two weeks behind schedule because a vendor delivered the test environment late. The sponsor needs to know before Friday's steering committee.",
    "task": "Write an email to the project sponsor explaining the delay, its impact on the go-live date, and the recovery options.",
    "inputs": "Original go-live: 30 June. New estimate: 14 July. Cause: vendor environment delivered 10 days late. Options: add two contractors, or reduce scope of phase 1.",
    "output_format": "email",
    "custom_format": "",
    "constraints": {"tone": "Professional, transparent and solution-focused", "word_limit": "180", "audience": "Executive project sponsor",
                    "required_sections": "Summary of delay, Impact, Options, Recommendation", "privacy": "yes",
                    "excluded_topics": "Blame on individuals"},
    "quality_criteria": "The sponsor can decide after reading only this email.\nAll dates are consistent with the input.\nNo information is invented.",
}

WEIGHTS = {"purpose": 10, "role": 10, "context": 15, "task": 25, "inputs": 10, "output_format": 10, "constraints": 10, "quality_criteria": 10}
STEP_FIELDS = {1: "purpose", 2: "role", 3: "context", 4: "task", 5: "inputs", 6: "output_format", 7: "constraints", 8: "quality_criteria"}
GUIDANCE = {
    "purpose": "Choose what you want the AI to do (write, summarize, analyze...).",
    "role": "Add a role so the AI uses the right expertise and vocabulary.",
    "context": "Add context: the situation, who is involved and why the result is needed.",
    "task": "Describe the task with an action verb and the deliverable you want.",
    "inputs": "Add the source information or a [PLACEHOLDER] the AI should work from.",
    "output_format": "Select an output format so the result is immediately usable.",
    "constraints": "Add at least two constraints (tone, word limit, audience, exclusions...).",
    "quality_criteria": "Define what a good answer looks like and how to handle missing information.",
}


def _lines(value) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = clean_text(value or "").split("\n")
    out = []
    for it in items:
        it = str(it).strip().lstrip("-•* ").strip()
        if it:
            out.append(it)
    return out


def _constraint_lines(c: dict) -> tuple[list[str], str, str]:
    """Return (constraint bullets, audience, tone)."""
    extra = _lines((c or {}).get("extra", ""))[:12]
    c = {k: clean_text(str(v), 500) for k, v in (c or {}).items() if v not in (None, "", False) and k != "extra"}
    bullets: list[str] = []
    if c.get("word_limit"):
        w = c["word_limit"]
        bullets.append(f"Keep the response under {w} words." if w.isdigit() else f"Word limit: {w}.")
    if c.get("language"):
        bullets.append(f"Write the response in {c['language']}.")
    if c.get("reading_level"):
        bullets.append(f"Use a reading level suitable for: {c['reading_level']}.")
    if c.get("num_options"):
        n = c["num_options"]
        bullets.append(f"Provide exactly {n} option(s)." if n.isdigit() else f"Number of options: {n}.")
    if c.get("required_sections"):
        bullets.append(f"Include these sections: {c['required_sections']}.")
    if c.get("excluded_topics"):
        bullets.append(f"Do not discuss or include: {c['excluded_topics']}.")
    if c.get("citation"):
        v = c["citation"]
        bullets.append("Cite the source for every factual claim." if v.lower() in ("yes", "true", "on") else f"Citation requirements: {v}.")
    if c.get("privacy"):
        bullets.append("Do not include or ask for personal, confidential or customer-identifying data; use anonymised placeholders instead.")
    if c.get("deadline"):
        bullets.append(f"The deadline is {c['deadline']}; make sure the content is realistic for that date.")
    if c.get("detail"):
        d = c["detail"].lower()
        bullets.append({"concise": "Be concise: key points only.", "standard": "Use a balanced level of detail.",
                        "detailed": "Be thorough: include reasoning, examples and edge cases."}.get(d, f"Level of detail: {c['detail']}."))
    bullets += [clean_text(x, 300) for x in extra]
    return bullets, c.get("audience", ""), c.get("tone", "")


def build_prompt_text(data: dict) -> str:
    role = clean_text(data.get("role", ""), 300)
    context = clean_text(data.get("context", ""), 3000)
    task = clean_text(data.get("task", ""), 3000)
    inputs = clean_text(data.get("inputs", ""), 6000)
    fmt_key = data.get("output_format") or ""
    fmt_text = clean_text(data.get("custom_format", ""), 800) if fmt_key == "custom" else (OUTPUT_FORMATS.get(fmt_key, ("", ""))[1])
    bullets, audience, tone = _constraint_lines(data.get("constraints") or {})
    quality = _lines(data.get("quality_criteria", ""))
    parts: list[str] = []
    if role:
        r = role.rstrip(".")
        low = r.lower()
        parts.append(r + "." if low.startswith(("act as", "you are")) else f"Act as {r}.")
    if context:
        parts.append(f"Context:\n{context}")
    if task:
        parts.append(f"Task:\n{task}")
    if inputs:
        parts.append(f"Input:\n{inputs}")
    if fmt_text:
        parts.append(f"Output format:\n{fmt_text}")
    if audience:
        parts.append(f"Audience:\n{audience}")
    if tone:
        parts.append(f"Tone:\n{tone}")
    if bullets:
        parts.append("Constraints:\n" + "\n".join(f"- {b}" for b in bullets))
    if quality:
        parts.append("Quality criteria:\n" + "\n".join(f"- {q}" for q in quality))
    return "\n\n".join(parts)


def completion(data: dict) -> tuple[int, list[dict]]:
    filled = {
        "purpose": bool(data.get("purpose")),
        "role": len(clean_text(data.get("role", ""))) >= 3,
        "context": len(clean_text(data.get("context", ""))) >= 15,
        "task": len(clean_text(data.get("task", ""))) >= 10,
        "inputs": len(clean_text(data.get("inputs", ""))) >= 3,
        "output_format": bool(data.get("output_format")) and (data.get("output_format") != "custom" or bool(clean_text(data.get("custom_format", "")))),
        "constraints": sum(1 for v in (data.get("constraints") or {}).values() if v) >= 2,
        "quality_criteria": len(_lines(data.get("quality_criteria", ""))) >= 1,
    }
    score = sum(WEIGHTS[k] for k, ok in filled.items() if ok)
    missing = [{"section": k, "guidance": GUIDANCE[k]} for k, ok in filled.items() if not ok]
    return score, missing


def validate_steps(data: dict) -> dict[int, list[str]]:
    errors: dict[int, list[str]] = {}
    if not data.get("purpose"):
        errors[1] = ["Choose a purpose for the prompt."]
    elif data["purpose"] not in PURPOSES:
        errors[1] = ["Unknown purpose selected."]
    if len(clean_text(data.get("role", ""))) < 3:
        errors[2] = ["Define a role (for example: a senior business analyst)."]
    if len(clean_text(data.get("task", ""))) < 10:
        errors[4] = ["Describe the task in at least 10 characters."]
    fmt = data.get("output_format")
    if not fmt:
        errors[6] = ["Select an output format."]
    elif fmt not in OUTPUT_FORMATS:
        errors[6] = ["Unknown output format selected."]
    elif fmt == "custom" and not clean_text(data.get("custom_format", "")):
        errors[6] = ["Describe your custom format."]
    return errors


def build(data: dict) -> dict:
    prompt = build_prompt_text(data)
    score, missing = completion(data)
    errors = validate_steps(data)
    analysis = scoring_service.analyze(prompt) if prompt else None
    return {
        "prompt": prompt,
        "valid": not errors,
        "step_errors": {str(k): v for k, v in errors.items()},
        "completion_score": score,
        "missing": missing,
        "quality": analysis,
    }


def catalog() -> dict:
    return {
        "purposes": [{"key": k, "label": v[0], "starter": v[2]} for k, v in PURPOSES.items()],
        "output_formats": [{"key": k, "label": v[0], "instruction": v[1]} for k, v in OUTPUT_FORMATS.items()],
        "constraint_options": [{"key": k, "label": v} for k, v in CONSTRAINT_OPTIONS.items()],
        "sample": SAMPLE,
    }
