import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import (
    FeedbackStatus,
    Language,
    SeniorityLevel,
    SessionDuration,
    SessionStatus,
    SessionType,
)


class Session(Base):
    __tablename__ = 'sessions'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id'), nullable=False
    )
    # CV used for this session — null for knowledge drills (no CV needed)
    cv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('cvs.id'), nullable=True
    )

    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.PENDING
    )
    # Lifecycle of the async feedback generation task. Distinct from
    # SessionStatus because feedback can still be PENDING after the session
    # itself has COMPLETED. Frontend polls this to know when to render the
    # report vs keep showing "Generating…".
    feedback_status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus), nullable=False, default=FeedbackStatus.PENDING
    )

    # Snapshot of user's settings at time of session — user may change these later
    seniority_level: Mapped[SeniorityLevel | None] = mapped_column(
        Enum(SeniorityLevel), nullable=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language), nullable=False, default=Language.EN
    )

    # Daily.co room info — needed to connect the user and bot
    daily_room_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    daily_room_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    daily_token: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Pipecat Cloud session reference
    pipecat_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # User can choose between various length of interviews
    duration_minutes: Mapped[SessionDuration] = mapped_column(
        Enum(SessionDuration), nullable=True, default=SessionDuration.MEDIUM
    )
