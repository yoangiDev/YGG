from typing import Any, Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


class UrlResponse(BaseModel):
    url: str


DDragonData = dict[str, Any]
