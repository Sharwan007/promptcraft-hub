from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="folder", max_length=40)
    sort_order: int = 0


class SubcategoryIn(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=100)


class TagIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)


class SubcategoryOut(ORM):
    id: int
    category_id: int
    name: str
    slug: str


class CategoryOut(ORM):
    id: int
    name: str
    slug: str
    description: str
    icon: str
    prompt_count: int = 0
    subcategories: list[SubcategoryOut] = []


class TagOut(ORM):
    id: int
    name: str
    slug: str
    prompt_count: int = 0
