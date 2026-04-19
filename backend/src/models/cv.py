import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import CVParsingStatus


class CV(Base):
    __tablename__ = 'cvs'  # Actual table name in PostgreSQL

    # Mapped[type] tells SQLAlchemy both the Python type AND the column type
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id'), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    s3_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsing lifecycle. `parsed_text` is the canonical "is it ready" signal
    # (session-start gates on that); `parsing_status` is the UX-friendly mirror
    # that drives pills/badges on the CV list without exposing the raw text.
    parsing_status: Mapped[CVParsingStatus] = mapped_column(
        Enum(CVParsingStatus, name='cvparsingstatus'),
        nullable=False,
        default=CVParsingStatus.PENDING,
        server_default=CVParsingStatus.PENDING.name,
    )
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
