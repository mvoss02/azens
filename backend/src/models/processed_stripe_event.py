from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ProcessedStripeEvent(Base):
    # Dedupe log for Stripe webhooks — any event_id we've seen is a no-op on replay.
    __tablename__ = 'processed_stripe_events'

    # Stripe's own event id (e.g. "evt_1Nxxxxx") — already unique, so it IS the PK.
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    event_type: Mapped[str] = mapped_column(String(255), nullable=False)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
