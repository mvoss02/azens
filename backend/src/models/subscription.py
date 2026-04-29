import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
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

    # Sessions started in the current Stripe billing period. Incremented
    # atomically in /session/start (compare-and-increment against the tier's
    # cap from config). Reset to 0 on the `invoice.paid` webhook for
    # billing_reason='subscription_cycle' — i.e. when Stripe charges the
    # next period. Deletion of a session does NOT decrement (option C in
    # the design discussion: counter tracks "sessions started", not
    # "sessions currently in DB", so users can't game the cap by deleting).
    sessions_used_this_period: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default='0'
    )

    # Timestamp of the most recent Stripe event applied to this row.
    # Used to reject stale/out-of-order webhook deliveries.
    last_stripe_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
