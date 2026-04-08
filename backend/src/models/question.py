import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import Difficulty, Language, SeniorityLevel, Topic


class Question(Base):
    __tablename__ = 'questions'  # Actual table name in PostgreSQL

    # Mapped[type] tells SQLAlchemy both the Python type AND the column type
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    question: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[Topic] = mapped_column(Enum(Topic), nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty), nullable=False)

    seniority_level: Mapped[SeniorityLevel] = mapped_column(
        Enum(SeniorityLevel), nullable=False
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language), nullable=False, default=Language.EN
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
