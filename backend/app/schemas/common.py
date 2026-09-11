"""Shared response envelopes, pagination, and query parameter schemas."""
import math
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        pages = math.ceil(total / page_size) if page_size else 0
        return cls(items=items, page=page, page_size=page_size, total=total, pages=max(pages, 0))


class MessageResponse(BaseModel):
    message: str
