import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.enums import SubscriptionPlan


class Subscription(Base):
    __tablename__ = 'subscriptions'  # Actual table name in PostgreSQL

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

    plan: Mapped[SubscriptionPlan | None] = mapped_column(
        Enum(SubscriptionPlan), nullable=True
    )

    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    billing_cycle: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "monthly" or "yearly"
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
