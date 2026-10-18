from typing import Any, Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


DDragonData = dict[str, Any]
