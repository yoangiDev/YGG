from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

JobStatusValue = Literal["queued", "processing", "done", "error"]


class SnapshotCreate(BaseModel):
    """Lo que recibe la API al lanzar un análisis."""
    player_id: int
    date_from: int      # Unix timestamp (segundos)
    date_to: int
    description: str = ""

    @model_validator(mode='after')
    def validate_dates(self) -> 'SnapshotCreate':
        if self.date_from >= self.date_to:
            raise ValueError("date_from must be earlier than date_to.")
        return self


class SnapshotResponse(BaseModel):
    """Lo que devuelve la API al listar snapshots."""
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
    """Para editar las notas inline desde la UI."""
    notes: str


class SnapshotDescriptionUpdate(BaseModel):
    """Para editar la descripción de un snapshot."""
    description: str


class SnapshotJobResponse(BaseModel):
    """Respuesta al lanzar un análisis. Si ya había uno igual en marcha, es ese mismo job."""
    job_id: str
    status: JobStatusValue = "queued"


class SnapshotJobStatus(BaseModel):
    """Estado de un análisis. Mismo formato en GET /jobs/{id} y en los eventos SSE."""
    job_id: str
    status: JobStatusValue
    progress: int = 0       # 0-100
    snapshot_id: int | None = None
    error: str | None = None
    attempts: int = 0
