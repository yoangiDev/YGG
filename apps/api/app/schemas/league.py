from datetime import datetime

from pydantic import BaseModel


class RankCutoffsResponse(BaseModel):
    region: str
    platform: str
    grandmaster_cutoff_lp: int
    challenger_cutoff_lp: int
    fetched_at: datetime
