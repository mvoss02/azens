from uuid import UUID

from pydantic import BaseModel


class TranscriptRequest(BaseModel):
    session_id: UUID
    role: str
    content: str
