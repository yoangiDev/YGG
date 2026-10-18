from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel, BeforeValidator

T = TypeVar("T")

SUPPORTED_REGIONS = ("EUW", "NA", "LAS", "LAN", "KR", "EUNE", "BR")
# Regions the API accepts as input (upper or lower case).
Region = Annotated[Literal[SUPPORTED_REGIONS], BeforeValidator(lambda value: value.upper() if isinstance(value, str) else value)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams:
    """Pagination parameters: `page: PageParams = Depends()`."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Items per page"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset


class MessageResponse(BaseModel):
    message: str
    status: str
