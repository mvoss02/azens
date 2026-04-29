import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Transcript(Base):
    """
    Individual turns in a session conversation.
    Stored in real-time during the session so we have a partial
    transcript even if the session is interrupted.
    """

    __tablename__ = 'transcripts'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('sessions.id', ondelete='CASCADE'),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # "user" = what the candidate said, "assistant" = what the bot said

    content: Mapped[str] = mapped_column(Text, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
