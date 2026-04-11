from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models.enums import SessionType


class FeedbackResponse(BaseModel):
    model_config = {'from_attributes': True}
    
    id: UUID
    session_id: UUID
    feedback_type: SessionType
    data: dict
    generated_at: datetime
