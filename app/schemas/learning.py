from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeCheckIn(BaseModel):
    question: str = Field(min_length=5)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)
    explanation: str = ""


class LearningModuleIn(BaseModel):
    number: int = Field(ge=1, le=999)
    title: str = Field(min_length=3, max_length=200)
    summary: str = ""
    objective: str = Field(min_length=5)
    explanation: str = Field(min_length=10)
    good_example: str = ""
    weak_example: str = ""
    tips: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    checks: list[KnowledgeCheckIn] = Field(default_factory=list)
    published: bool = True


class ProgressIn(BaseModel):
    module_id: int
    completed: bool = True


class GlossaryIn(BaseModel):
    term: str = Field(min_length=2, max_length=100)
    definition: str = Field(min_length=5)
    example: str = ""
    published: bool = True


class ExampleIn(BaseModel):
    scenario: str = Field(min_length=3, max_length=200)
    description: str = ""
    weak_prompt: str = Field(min_length=3)
    problems: list[str] = Field(default_factory=list)
    improved_prompt: str = Field(min_length=10)
    improvements: list[str] = Field(default_factory=list)
    why_better: str = ""
    expected_difference: str = ""
    sort_order: int = 0
    published: bool = True
