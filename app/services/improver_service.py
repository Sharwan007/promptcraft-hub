"""Prompt improvement through a provider abstraction.

RuleBasedPromptImprover is the active provider: deterministic templates and rules, no network,
no API key. FutureAIProvider is a stub that documents where an AI-backed provider will plug in.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.services.builder_service import OUTPUT_FORMATS
from app.services.scoring_service import (
    ACTION_VERBS, AUDIENCE_NOUNS, STOPWORDS, TONE_WORDS, analyze_text, parse_sections, scoring_service,
)
from app.services.use_case_profiles import get_profile
from app.utilities.text_utils import clean_text, find_placeholders, word_count

WHY = {
    "role": "A role tells the AI which expertise, vocabulary and perspective to use, which makes answers more consistent.",
    "context": "Context explains the situation and purpose, so the AI can make relevant choices instead of generic ones.",
    "task": "A specific task with a defined deliverable removes guesswork about what to produce.",
    "input": "Supplying the source information (or a clearly marked placeholder) keeps the answer grounded in your facts.",
    "output_format": "Defining the output format makes the result immediately usable and easier to compare or reuse.",
    "audience": "Naming the audience controls the level of detail, vocabulary and emphasis.",
    "tone": "Stating the tone keeps the writing style consistent with your situation.",
    "constraints": "Constraints (length, scope, exclusions) prevent rambling and keep the answer inside your boundaries.",
    "quality_criteria": "Quality criteria tell the AI how its answer will be judged and what to do when information is missing.",
}
TOOL_TIPS = {
    "Microsoft Copilot": "Tip for Microsoft Copilot: where possible, reference the file, email or meeting you want it to use instead of pasting long text.",
    "ChatGPT": "Tip for ChatGPT: paste source text between clear delimiters (for example triple quotes) so instructions and data are not mixed.",
    "Claude": "Tip for Claude: wrap pasted documents in tags such as <document>...</document> to keep input separate from instructions.",
    "Gemini": "Tip for Gemini: state the output format explicitly and refine the result with short follow-up prompts.",
}
DETAIL = {
    "concise": "Be concise: key points only.",
    "standard": "Use a balanced level of detail.",
    "detailed": "Be thorough: include reasoning, examples and edge cases.",
}


class PromptImproverProvider(ABC):
    name = "base"
    label = "Base provider"

    @abstractmethod
    def improve(self, prompt: str, options: dict) -> dict: ...


class FutureAIProvider(PromptImproverProvider):
    """Placeholder for an optional AI-backed provider (not active, requires configuration)."""
    name = "future_ai"
    label = "AI provider (not configured)"

    def improve(self, prompt: str, options: dict) -> dict:
        raise NotImplementedError("No AI provider is configured in this local version.")


class RuleBasedPromptImprover(PromptImproverProvider):
    name = "rule_based"
    label = "Rule-based improver (local, deterministic)"

    # ------------------------------------------------------------------ extraction
    def _extract(self, text: str, analysis) -> dict:
        parts = {"role": "", "context": "", "task": "", "input": "", "output_format": "", "audience": "", "tone": "",
                 "constraints": [], "quality_criteria": [], "labelled": set()}
        sections = parse_sections(text)
        for k, v in sections.items():
            parts["labelled"].add(k)
            if k in ("constraints", "quality_criteria"):
                parts[k] = [ln.strip().lstrip("-•* ").strip() for ln in v.split("\n") if ln.strip()]
            else:
                parts[k] = v.strip()
        if sections:
            m = re.match(r"\s*(act as|you are)\s+(?:an? |the )?(.+)", text.split("\n")[0], re.IGNORECASE)
            if m and "role" not in sections:
                parts["role"] = m.group(0).strip().rstrip(".")
                parts["labelled"].add("role")
            return parts
        task_parts, ctx_parts = [], []
        for s in re.split(r"(?<=[.!?])\s+|\n+", text):
            s = s.strip()
            if not s:
                continue
            low = s.lower()
            toks = re.findall(r"[\w'’\-]+", low)
            if re.match(r"(act as|you are|you're|take on the role)", low):
                parts["role"] = s.rstrip(".")
            elif re.search(r"\b(under|no more than|at most|maximum|do not|don't|avoid|must not|limit(ed)? to|within \d+)\b", low) and not toks[:3] == ["write", "a", "report"]:
                parts["constraints"].append(s.rstrip("."))
            elif re.search(r"\b(in a table|as a table|bullet points?|numbered list|in json|as json|subject line|in markdown|format(ted)? as|in the form of)\b", low):
                parts["output_format"] = (parts["output_format"] + " " + s).strip()
            elif any(t in ACTION_VERBS for t in toks[:7]) or (toks and toks[0] in ("what", "how", "why", "which") and s.endswith("?")):
                task_parts.append(s)
            else:
                ctx_parts.append(s)
        parts["task"] = " ".join(task_parts)
        parts["context"] = " ".join(ctx_parts)
        if analysis.components["tone"].strength >= 0.8:
            found = [w for w in TONE_WORDS if re.search(r"\b" + re.escape(w) + r"\b", text.lower())]
            parts["tone"] = ", ".join(found[:3]).capitalize()
        if analysis.components["audience"].strength >= 0.7:
            nouns = "|".join(sorted(set(AUDIENCE_NOUNS), key=len, reverse=True))
            m = re.search(r"\b(?:for|to|audience:?)\s+(?:the |our |my |a |an )?((?:[\w-]+ ){0,2}(?:" + nouns + r"))\b", text, re.IGNORECASE)
            if m:
                parts["audience"] = m.group(1).strip().capitalize()
        return parts

    @staticmethod
    def _content_words(s: str) -> int:
        toks = re.findall(r"[\w'’\-]+", s.lower())
        return len([t for t in toks if t not in STOPWORDS and t not in ACTION_VERBS])

    # ------------------------------------------------------------------ main
    def improve(self, prompt: str, options: dict) -> dict:
        original = clean_text(prompt, 12000)
        options = options or {}
        analysis = analyze_text(original, options.get("purpose"))
        profile = get_profile(analysis.use_case)
        before = scoring_service.analyze(original, analysis.use_case)
        parts = self._extract(original, analysis)
        changes: list[dict] = []

        def change(component: str, kind: str, what: str):
            changes.append({"component": component, "type": kind, "change": what, "why": WHY[component]})

        # task
        generic_task = (not parts["task"]) or (self._content_words(parts["task"]) <= 2 and "task" not in parts["labelled"])
        if generic_task:
            task = profile["task"]
            if parts["task"]:
                change("task", "refined", f"Expanded your short request (\"{parts['task'][:60]}\") into a specific task with a defined deliverable.")
            else:
                change("task", "added", "Added a clear task with a defined deliverable.")
        else:
            task = parts["task"]
            if before["breakdown"][0]["points"] >= 18:
                change("task", "kept", "Kept your task wording, which was already clear.")
            else:
                change("task", "kept", "Kept your task and placed it in its own labelled section.")

        # role
        if parts["role"]:
            role = parts["role"] if parts["role"].lower().startswith(("act as", "you are")) else f"Act as {parts['role']}"
            change("role", "kept", "Kept your role definition.")
        else:
            role = f"Act as {profile['role']}"
            change("role", "added", f"Added the role \"{profile['role']}\".")
        role = role.rstrip(".") + "."

        # context
        if parts["context"]:
            context = parts["context"]
            change("context", "kept", "Moved your background information into a Context section.")
        elif generic_task:
            context = profile["context"]
            change("context", "added", "Added a default scenario for this type of request. Edit it so it matches your real situation.")
        else:
            context = "Background: [DESCRIBE THE SITUATION - who is involved, what happened and why this is needed]."
            change("context", "added", "Added a Context section with a placeholder for the details only you know.")

        # input
        if parts["input"]:
            inp = parts["input"]
            change("input", "kept", "Kept your input information.")
        else:
            inp = profile["input"]
            change("input", "added", "Added an Input section with placeholders for the source information.")

        # output format
        out_key = options.get("output_type")
        if out_key and out_key in OUTPUT_FORMATS and out_key != "custom":
            fmt = OUTPUT_FORMATS[out_key][1]
            change("output_format", "added", f"Applied your chosen output type: {OUTPUT_FORMATS[out_key][0]}.")
        elif parts["output_format"]:
            fmt = parts["output_format"]
            change("output_format", "kept", "Kept your format instruction in a dedicated section.")
        else:
            fmt = profile["output_format"]
            change("output_format", "added", "Added an output format suited to this type of request.")

        # audience / tone
        audience = clean_text(options.get("audience", ""), 200) or parts["audience"] or profile["audience"]
        change("audience", "kept" if (options.get("audience") or parts["audience"]) else "added",
               "Used the audience you provided." if (options.get("audience") or parts["audience"]) else "Added a target audience for this type of request.")
        tone = clean_text(options.get("tone", ""), 120) or parts["tone"] or profile["tone"]
        change("tone", "kept" if (options.get("tone") or parts["tone"]) else "added",
               "Used the tone you provided." if (options.get("tone") or parts["tone"]) else "Added a suitable tone.")

        # constraints
        cons = list(parts["constraints"])
        limit = str(options.get("word_limit") or "").strip()
        has_limit = bool(limit) or any(re.search(r"\bwords\b", c.lower()) for c in cons)
        base = [c for c in profile["constraints"] if not (has_limit and re.search(r"\b(words|under \d+)\b", c.lower()))]
        for c in base:
            if len(cons) >= 5:
                break
            if not any(c.lower()[:18] == x.lower()[:18] for x in cons):
                cons.append(c)
        if limit:
            cons.insert(0, f"Keep the response under {limit} words." if limit.isdigit() else f"Word limit: {limit}.")
        detail = (options.get("detail_level") or "").lower()
        if detail in DETAIL:
            cons.append(DETAIL[detail])
        cons = [c.rstrip(".") + "." for c in cons]
        change("constraints", "kept" if parts["constraints"] else "added",
               "Combined your limits with additional boundaries." if parts["constraints"] else "Added length, scope and exclusion constraints.")

        # quality
        quality = parts["quality_criteria"] or list(profile["quality"])
        change("quality_criteria", "kept" if parts["quality_criteria"] else "added",
               "Kept your quality criteria." if parts["quality_criteria"] else "Added quality criteria, including how to handle missing information.")

        blocks = [
            role, f"Context:\n{context}", f"Task:\n{task}", f"Input:\n{inp}", f"Output format:\n{fmt}",
            f"Audience:\n{audience}", f"Tone:\n{tone}",
            "Constraints:\n" + "\n".join(f"- {c}" for c in cons),
            "Quality criteria:\n" + "\n".join(f"- {q.rstrip('.')}." for q in quality),
        ]
        improved = "\n\n".join(blocks)
        after = scoring_service.analyze(improved, analysis.use_case)
        placeholders = find_placeholders(improved)
        notes = []
        if placeholders:
            notes.append("Replace the highlighted [PLACEHOLDERS] with your own details before using the prompt.")
        tip = TOOL_TIPS.get(options.get("ai_tool") or "")
        if tip:
            notes.append(tip)
        if before["privacy"]:
            notes.append("The original prompt contains possible sensitive data. Remove it before using any AI tool.")
        return {
            "provider": self.name, "provider_label": self.label,
            "original": original, "improved": improved,
            "original_score": before["score"], "improved_score": after["score"],
            "original_label": before["label"], "improved_label": after["label"],
            "original_quality": before, "improved_quality": after,
            "use_case": analysis.use_case, "use_case_label": profile["label"],
            "missing_components": [m for m in before["missing"]],
            "changes": changes, "placeholders": placeholders, "notes": notes,
            "words": {"original": word_count(original), "improved": word_count(improved)},
        }


PROVIDERS: dict[str, PromptImproverProvider] = {"rule_based": RuleBasedPromptImprover(), "future_ai": FutureAIProvider()}
DEFAULT_PROVIDER = "rule_based"


def get_provider(name: str | None = None) -> PromptImproverProvider:
    prov = PROVIDERS.get(name or DEFAULT_PROVIDER)
    if prov is None or isinstance(prov, FutureAIProvider):
        prov = PROVIDERS[DEFAULT_PROVIDER]
    return prov


def improve_prompt(prompt: str, options: dict | None = None) -> dict:
    return get_provider().improve(prompt, options or {})
