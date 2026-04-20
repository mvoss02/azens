import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import Language


class Waitlist(Base):
    __tablename__ = 'waitlist'  # Actual table name in PostgreSQL

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # e.g. 'case_studies'

    language: Mapped[Language | None] = mapped_column(
        Enum(Language, name='language'), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    unsubscribe_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid.uuid4,
    )

    # Composite uniqueness — same email can be on multiple waitlists (e.g.
    # case_studies now, knowledge_drills later), but not the same one twice.
    # Name must match the migration's constraint name for alembic parity.
    __table_args__ = (
        UniqueConstraint('email', 'source', name='uq_waitlist_email_source'),
    )
