import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    checksum: str
    size_bytes: int
    commit_sha: str | None
    branch: str | None
    ci_run_id: str | None
    attempt: int
    error: str | None
    created_at: datetime
    processed_at: datetime | None
    run_id: uuid.UUID | None = None
    duplicate: bool = False
