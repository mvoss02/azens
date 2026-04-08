from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    file_size: int

    is_active: bool
    created_at: datetime
