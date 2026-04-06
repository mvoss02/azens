import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import Language, SeniorityLevel


class User(Base):
    __tablename__ = 'users'  # Actual table name in PostgreSQL

    # Mapped[type] tells SQLAlchemy both the Python type AND the column type
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    google_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    seniority_level: Mapped[SeniorityLevel | None] = mapped_column(
        Enum(SeniorityLevel), nullable=True
    )
    preferred_language: Mapped[Language] = mapped_column(
        Enum(Language), nullable=False, default=Language.EN
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    
    verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
