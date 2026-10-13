from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORM
from app.utilities.validation import AI_TOOLS, DIFFICULTIES


class PromptBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    slug: str | None = Field(default=None, max_length=220)
    description: str = Field(min_length=5, max_length=1000)
    full_prompt: str = Field(min_length=10, max_length=20000)
    category: str | None = Field(default=None, description="Category name")
    category_id: int | None = None
    subcategory: str | None = Field(default=None, max_length=100)
    user_role: str = Field(default="", max_length=120)
    use_case: str = Field(default="", max_length=200)
    ai_tools: list[str] = Field(default_factory=lambda: ["Tool-independent"])
    difficulty: str = "Beginner"
    tags: list[str] = Field(default_factory=list)
    expected_output: str = ""
    required_inputs: list[str] = Field(default_factory=list)
    example_inputs: dict[str, str] = Field(default_factory=dict)
    example_output: str = ""
    why_it_works: str = ""
    customization_tips: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    components: dict[str, Any] = Field(default_factory=dict)
    featured: bool = False
    published: bool = True

    @field_validator("difficulty")
    @classmethod
    def _difficulty(cls, v: str) -> str:
        if v not in DIFFICULTIES:
            raise ValueError(f"must be one of {', '.join(DIFFICULTIES)}")
        return v

    @field_validator("ai_tools")
    @classmethod
    def _tools(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if t not in AI_TOOLS]
        if bad:
            raise ValueError(f"unknown AI tool(s): {', '.join(bad)}")
        return v or ["Tool-independent"]


class PromptCreate(PromptBase):
    pass


class PromptUpdate(PromptBase):
    pass


class PromptOut(ORM):
    id: int
    title: str
    slug: str
    description: str
    full_prompt: str
    category: str
    category_id: int
    subcategory: str | None
    user_role: str
    use_case: str
    ai_tools: list[str]
    difficulty: str
    tags: list[str]
    expected_output: str
    required_inputs: list[str]
    example_inputs: dict[str, str]
    example_output: str
    why_it_works: str
    customization_tips: list[str]
    common_mistakes: list[str]
    constraints: list[str]
    components: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    view_count: int
    copy_count: int
    is_favorite: bool = False
    featured: bool
    published: bool
    version: int
    archived: bool


class PromptSummary(ORM):
    id: int
    title: str
    slug: str
    description: str
    category: str
    subcategory: str | None
    difficulty: str
    ai_tools: list[str]
    tags: list[str]
    user_role: str
    view_count: int
    copy_count: int
    is_favorite: bool = False
    featured: bool


class CustomPromptIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=1000)
    content: str = Field(min_length=5, max_length=20000)
    category_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    source_prompt_id: int | None = None
    origin: str = Field(default="manual", max_length=30)
    change_note: str = Field(default="", max_length=200)


class CustomPromptOut(ORM):
    id: int
    title: str
    description: str
    content: str
    category_id: int | None
    category: str | None
    tags: list[str]
    source_prompt_id: int | None
    origin: str
    version: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class CustomVersionOut(ORM):
    version: int
    title: str
    description: str
    content: str
    tags: list[str]
    change_note: str
    created_at: datetime


class SettingsIn(BaseModel):
    display_name: str = Field(default="Local User", max_length=80)
    role: str = Field(default="", max_length=80)
    theme: str = Field(default="system", pattern="^(system|light|dark)$")
    default_ai_tool: str = "Tool-independent"
    view_mode: str = Field(default="grid", pattern="^(grid|list)$")

    @field_validator("default_ai_tool")
    @classmethod
    def _tool(cls, v: str) -> str:
        if v not in AI_TOOLS:
            raise ValueError("unknown AI tool")
        return v
