import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import SessionType


class Feedback(Base):
    __tablename__ = 'feedback'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('sessions.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )

    feedback_type: Mapped[SessionType] = mapped_column(
        Enum(SessionType), nullable=False
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
