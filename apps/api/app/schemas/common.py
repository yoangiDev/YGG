from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams:
    """Parámetros de paginación: `page: PageParams = Depends()`."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Elementos por página"),
        offset: int = Query(0, ge=0, description="Elementos a saltar"),
    ) -> None:
        self.limit = limit
        self.offset = offset


class MessageResponse(BaseModel):
    message: str
    status: str
