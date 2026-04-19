from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from models.enums import SubscriptionPlan

# Slugs used by the checkout endpoint to look up the real Stripe price ID.
# Keeping them Literal here means Pydantic rejects anything else at the
# request boundary — the frontend can't ask for a plan we don't offer.
PlanSlug = Literal['analyst', 'associate', 'managing_director']
CycleSlug = Literal['monthly', 'halfyearly']


class CheckoutRequest(BaseModel):
    plan: PlanSlug
    cycle: CycleSlug


class SubscriptionResponse(BaseModel):
    model_config = {'from_attributes': True}

    # UUID matches the ORM column type. Serializes to a plain string over the
    # wire (JSON), so the frontend sees a string either way — but Pydantic
    # now accepts the raw UUID object from SQLAlchemy without complaining.
    user_id: UUID

    plan: SubscriptionPlan | None

    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    billing_cycle: str | None
    current_period_end: datetime | None

    is_active: bool
