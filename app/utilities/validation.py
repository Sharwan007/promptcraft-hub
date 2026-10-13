"""Reusable validation helpers (server-side)."""
from __future__ import annotations

from app.core.exceptions import ValidationFailed
from app.utilities.text_utils import clean_text, unique_list

DIFFICULTIES = ("Beginner", "Intermediate", "Advanced")
AI_TOOLS = ("Microsoft Copilot", "ChatGPT", "Claude", "Gemini", "Tool-independent")
MAX_TAGS = 15


def require(value: str | None, label: str, *, min_len: int = 1, max_len: int = 20000) -> str:
    v = clean_text(value, max_len + 1)
    if len(v) < min_len:
        raise ValidationFailed(f"{label} is required." if min_len <= 1 else f"{label} must be at least {min_len} characters.")
    if len(v) > max_len:
        raise ValidationFailed(f"{label} must be {max_len} characters or fewer.")
    return v


def normalize_tags(tags) -> list[str]:
    tags = unique_list([clean_text(str(t), 40).lower() for t in (tags or [])])
    return tags[:MAX_TAGS]


def check_choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    if value not in allowed:
        raise ValidationFailed(f"{label} must be one of: {', '.join(allowed)}.")
    return value


def check_tools(tools) -> list[str]:
    tools = unique_list(tools or [])
    if not tools:
        return ["Tool-independent"]
    bad = [t for t in tools if t not in AI_TOOLS]
    if bad:
        raise ValidationFailed(f"Unknown AI tool(s): {', '.join(bad)}. Allowed: {', '.join(AI_TOOLS)}.")
    return tools
