"""Small text helpers shared across services."""
from __future__ import annotations

import re
import unicodedata

PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z0-9 _/&\-]{1,40})\]")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def slugify(value: str, max_len: int = 80) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    value = _SLUG_STRIP.sub("-", value).strip("-")
    return (value[:max_len].strip("-")) or "item"


def clean_text(value: str | None, max_len: int = 20000) -> str:
    """Normalise newlines, strip control characters and trim. Unicode is preserved."""
    if value is None:
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL.sub("", value)
    return value.strip()[:max_len]


def sanitize_search(q: str | None, max_len: int = 100) -> str:
    q = clean_text(q or "", max_len)
    return re.sub(r"\s+", " ", q)


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def find_placeholders(text: str) -> list[str]:
    seen: list[str] = []
    for m in PLACEHOLDER_RE.finditer(text or ""):
        name = m.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def fill_placeholders(text: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        v = (values.get(m.group(1)) or "").strip()
        return v if v else m.group(0)
    return PLACEHOLDER_RE.sub(repl, text or "")


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text or "", flags=re.UNICODE))


def safe_filename(name: str, ext: str = "", max_len: int = 60) -> str:
    base = slugify(name, max_len) or "export"
    ext = re.sub(r"[^a-z0-9]", "", ext.lower())
    return f"{base}.{ext}" if ext else base


def unique_list(items) -> list[str]:
    out, seen = [], set()
    for it in items or []:
        s = str(it).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out
