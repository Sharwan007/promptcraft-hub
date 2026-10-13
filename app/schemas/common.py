from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str
    data: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] = []
    hint: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
