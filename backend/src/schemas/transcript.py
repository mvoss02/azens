from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# 10 kB per transcript chunk is generous — typical chunks are 50-500 chars.
# A chunk larger than this is almost certainly a bug or abuse and we want
# a 422 rather than an unbounded row in the DB.
MAX_TRANSCRIPT_CONTENT_LENGTH = 10_000


class TranscriptRequest(BaseModel):
    session_id: UUID
    # Literal pins role to exactly these two values — Pydantic rejects
    # anything else with a 422, so the DB never sees garbage values.
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CONTENT_LENGTH)
