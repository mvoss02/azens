from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models.enums import (
    FeedbackStatus,
    Language,
    SeniorityLevel,
    SessionDuration,
    SessionStatus,
    SessionType,
)


class SessionRequest(BaseModel):
    cv_id: UUID | None
    session_type: SessionType
    seniority_level: SeniorityLevel | None
    language: Language
    duration_minutes: SessionDuration
    personality: str = 'balanced'


class StartSessionResponse(BaseModel):
    model_config = {'from_attributes': True}

    id: UUID
    cv_id: UUID | None
    session_type: SessionType
    seniority_level: SeniorityLevel | None
    language: Language
    duration_minutes: SessionDuration

    # Daily.co room info — needed to connect the user and bot
    daily_room_url: str | None
    daily_room_name: str | None
    daily_token: str | None

    # Pipecat Cloud session reference
    pipecat_session_id: str | None

    status: SessionStatus


class SessionResponse(BaseModel):
    model_config = {'from_attributes': True}

    id: UUID
    cv_id: UUID | None
    session_type: SessionType
    seniority_level: SeniorityLevel | None
    language: Language
    duration_minutes: SessionDuration
    status: SessionStatus
    feedback_status: FeedbackStatus
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    # Present for ACTIVE sessions owned by the caller so the session-room
    # component can (re)join the Daily room on refresh / reconnect. Null for
    # ended or other users' sessions. Token is freshly minted on each read.
    daily_room_url: str | None = None
    daily_token: str | None = None
