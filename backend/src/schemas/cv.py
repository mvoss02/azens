from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models.enums import CVParsingStatus


class UploadUrlRequest(BaseModel):
    filename: str
    file_size: int


class UploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str


class ConfirmUploadRequest(BaseModel):
    s3_key: str
    filename: str
    file_size: int | None


class CVResponse(BaseModel):
    model_config = {'from_attributes': True}

    id: UUID
    filename: str
    file_size: int | None

    is_active: bool
    # Drives the "Analysing… / Ready / Failed" pill on the frontend and the
    # retry affordance. parsing_error is intentionally exposed so the UI can
    # show a short hint on failed CVs — it's already truncated server-side.
    parsing_status: CVParsingStatus
    parsing_error: str | None

    created_at: datetime
