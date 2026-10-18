from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

JobStatusValue = Literal["queued", "processing", "done", "error"]


class SnapshotCreate(BaseModel):
    """What the API receives when launching an analysis."""
    player_id: int
    date_from: int      # Unix timestamp (seconds)
    date_to: int
    description: str = ""
    # Plus the replay analysis of the replays (accounts with replay access only, and from PremiumCoverage.since).
    premium: bool = False

    @model_validator(mode='after')
    def validate_dates(self) -> 'SnapshotCreate':
        if self.date_from >= self.date_to:
            raise ValueError("date_from must be earlier than date_to.")
        return self


class SnapshotResponse(BaseModel):
    """What the API returns when listing snapshots."""
    id: int
    player_id: int
    date_from: datetime
    date_to: datetime
    description: str | None = ""
    notes: str | None = ""
    match_count: int = 0

    model_config = {"from_attributes": True}

    @field_validator("match_count", mode="before")
    @classmethod
    def validate_match_count(cls, v):
        return 0 if v is None else v


class SnapshotNotesUpdate(BaseModel):
    """For editing the notes inline from the UI."""
    notes: str


class SnapshotDescriptionUpdate(BaseModel):
    """For editing a snapshot's description."""
    description: str


class SnapshotJobResponse(BaseModel):
    """Response when launching an analysis. If an identical one was already running, it is that same job."""
    job_id: str
    status: JobStatusValue = "queued"


class SnapshotJobStatus(BaseModel):
    """Status of an analysis. Same format in GET /jobs/{id} and in the SSE events."""
    job_id: str
    status: JobStatusValue
    progress: int = 0       # 0-100
    snapshot_id: int | None = None
    error: str | None = None
    attempts: int = 0


class PremiumCoverage(BaseModel):
    """Since when a replay analysis can be requested: the first patch with replays and exe."""
    since: int  # Unix timestamp (s)


class WaitingGame(BaseModel):
    """A match in the snapshot whose replay is still to be uploaded."""
    match_id: str
    champion: str
    played_at: datetime


class PremiumAnalysisResponse(BaseModel):
    """A snapshot's replay analysis. `result` is the numbers and the chart series; `review`,
    what Claude writes. Both empty until it finishes."""
    snapshot_id: int
    status: JobStatusValue
    progress: int = 0
    error: str | None = None
    result: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    # while it is running, the matches whose replay is still to be uploaded
    waiting: list[WaitingGame] = []

    model_config = {"from_attributes": True}
