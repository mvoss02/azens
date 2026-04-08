from datetime import datetime

from models.enums import SubscriptionPlan
from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    price_id: str
    
class SubscriptionResponse(BaseModel):
    model_config = {'from_attributes': True}
    
    user_id: str

    plan: SubscriptionPlan | None
    
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    billing_cycle: str | None
    current_period_end: datetime | None

    is_active: bool
