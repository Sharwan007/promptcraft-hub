from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    use_case: str | None = Field(default=None, max_length=40)


class ImproveOptions(BaseModel):
    purpose: str | None = Field(default=None, max_length=40)
    audience: str = Field(default="", max_length=200)
    ai_tool: str = Field(default="", max_length=40)
    output_type: str = Field(default="", max_length=40)
    tone: str = Field(default="", max_length=120)
    word_limit: str = Field(default="", max_length=10)
    detail_level: str = Field(default="", max_length=20)


class ImproveIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    options: ImproveOptions = Field(default_factory=ImproveOptions)


class BuildIn(BaseModel):
    purpose: str = ""
    role: str = Field(default="", max_length=300)
    context: str = Field(default="", max_length=3000)
    task: str = Field(default="", max_length=3000)
    inputs: str = Field(default="", max_length=6000)
    output_format: str = ""
    custom_format: str = Field(default="", max_length=800)
    constraints: dict[str, Any] = Field(default_factory=dict)
    quality_criteria: str = Field(default="", max_length=2000)


class RenderIn(BaseModel):
    title: str = Field(default="prompt", max_length=120)
    content: str = Field(min_length=1, max_length=40000)
    format: str = Field(default="txt", pattern="^(txt|md|json)$")
