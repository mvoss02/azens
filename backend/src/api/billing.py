import logging
from datetime import UTC, datetime
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id
from core.config import settings as settings_billing
from core.database import get_db
from models.enums import SubscriptionPlan
from models.processed_stripe_event import ProcessedStripeEvent
from models.subscription import Subscription
from models.user import User
from schemas.billing import CheckoutRequest, SubscriptionResponse

logger = logging.getLogger(__name__)

stripe.api_key = settings_billing.stripe_api_key
router = APIRouter()

PRICE_TO_PLAN = {
    settings_billing.stripe_price_analyst_monthly: SubscriptionPlan.ANALYST,
    settings_billing.stripe_price_analyst_yearly: SubscriptionPlan.ANALYST,
    settings_billing.stripe_price_associate_monthly: SubscriptionPlan.ASSOCIATE,
    settings_billing.stripe_price_associate_yearly: SubscriptionPlan.ASSOCIATE,
    settings_billing.stripe_price_managing_director_monthly: SubscriptionPlan.MANAGING_DIRECTOR,
    settings_billing.stripe_price_managing_director_yearly: SubscriptionPlan.MANAGING_DIRECTOR,
}


@router.post('/checkout', response_model=None, status_code=status.HTTP_201_CREATED)
async def checkout(
    body: CheckoutRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 1. Create a Stripe Checkout Session
    #    This generates a hosted payment page — Stripe handles the card form,
    #    3D Secure, PCI compliance, everything. You never touch card numbers.
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='User not found')

    session = stripe.checkout.Session.create(
        mode='subscription',
        customer_email=user.email,
        line_items=[{'price': body.price_id, 'quantity': 1}],
        success_url=f'{settings_billing.frontend_url}/billing?success=true',
        cancel_url=f'{settings_billing.frontend_url}/billing?cancelled=true',
        metadata={'user_id': str(user_id)},  # so webhook knows which user paid
    )

    # 2. Return the URL — frontend redirects the user there
    return {'checkout_url': session.url}


@router.post('/webhook', response_model=None, status_code=status.HTTP_200_OK)
async def webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    # No auth dependency here! Stripe calls this, not your user.
    payload = await request.body()
    sig = request.headers.get('stripe-signature')

    # Verify it's really from Stripe (not someone faking it)
    event = stripe.Webhook.construct_event(
        payload, sig, settings_billing.stripe_webhook_secret
    )

    # Idempotency gate — if we've already processed this event_id, ack and skip.
    # Stripe may redeliver the same event (network retries, manual replays).
    # The PK on event_id makes duplicate inserts impossible; on race, one worker
    # wins, the other gets IntegrityError on flush and the whole txn rolls back
    # so Stripe retries — on retry the SELECT below catches it.
    existing = await db.execute(
        select(ProcessedStripeEvent).where(
            ProcessedStripeEvent.event_id == event['id']
        )
    )
    if existing.scalar_one_or_none():
        logger.info('Duplicate Stripe event %s — skipping', event['id'])
        return {'received': True}

    db.add(ProcessedStripeEvent(event_id=event['id'], event_type=event['type']))
    await db.flush()

    # Stripe event timestamp — used to reject stale out-of-order deliveries
    # on updated/deleted events (an old update arriving after a newer one
    # must not roll the Subscription row back).
    event_created = datetime.fromtimestamp(event['created'], tz=UTC)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = UUID(session['metadata']['user_id'])

        # Get price ids and payment interval
        stripe_sub = stripe.Subscription.retrieve(session['subscription'])
        price_id = stripe_sub['items']['data'][0]['price']['id']
        interval = stripe_sub['items']['data'][0]['price']['recurring']['interval']
        period_end = stripe_sub['items']['data'][0]['current_period_end']

        # Create/update subscription record in your DB
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            # Create subscription
            new_sub = Subscription(
                user_id=user_id,
                plan=PRICE_TO_PLAN[price_id],
                is_active=True,
                stripe_customer_id=session['customer'],
                stripe_subscription_id=session['subscription'],
                billing_cycle=interval,
                current_period_end=datetime.fromtimestamp(period_end, tz=UTC),
                last_stripe_event_at=event_created,
            )
            db.add(new_sub)
            await db.flush()  # flush sends the INSERT to DB and populates user.id, but doesn't commit yet
        else:
            # Update exisitng subscription
            sub.is_active = True
            sub.plan = PRICE_TO_PLAN[price_id]
            sub.stripe_customer_id = session['customer']
            sub.stripe_subscription_id = session['subscription']
            sub.billing_cycle = interval
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
            sub.last_stripe_event_at = event_created

    elif event['type'] == 'customer.subscription.updated':
        stripe_sub = event['data']['object']
        period_end = stripe_sub['items']['data'][0]['current_period_end']
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_sub['id']
            )
        )
        sub = result.scalar_one_or_none()

        # Missing sub = event arrived before checkout.session.completed (Stripe
        # does not guarantee order). Ack with 2xx so Stripe stops retrying — the
        # checkout event will create the row when it arrives.
        if not sub:
            logger.warning(
                'Stripe update for unknown sub %s — acking', stripe_sub['id']
            )
            return {'received': True}

        # Reject stale events — we've already applied a newer one to this row.
        if sub.last_stripe_event_at and sub.last_stripe_event_at >= event_created:
            logger.warning(
                'Stale Stripe update for sub %s — skipping', stripe_sub['id']
            )
            return {'received': True}

        if stripe_sub.get('cancel_at_period_end'):
            # User cancelled — still active until period end
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        else:
            # Could be a plan change — update the plan
            price_id = stripe_sub['items']['data'][0]['price']['id']
            sub.plan = PRICE_TO_PLAN.get(price_id, sub.plan)
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)

        sub.last_stripe_event_at = event_created

    elif event['type'] == 'customer.subscription.deleted':
        stripe_sub = event['data']['object']
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_sub['id']
            )
        )
        sub = result.scalar_one_or_none()

        # Missing sub = row never existed or was already wiped. Ack and move on.
        if not sub:
            logger.warning(
                'Stripe delete for unknown sub %s — acking', stripe_sub['id']
            )
            return {'received': True}

        # Reject stale deletes — a replay after the user has resubscribed must
        # not deactivate a healthy row.
        if sub.last_stripe_event_at and sub.last_stripe_event_at >= event_created:
            logger.warning(
                'Stale Stripe delete for sub %s — skipping', stripe_sub['id']
            )
            return {'received': True}

        sub.plan = None
        sub.is_active = False
        sub.last_stripe_event_at = event_created

    return {'received': True}


@router.get(
    '/subscription', response_model=SubscriptionResponse | None, status_code=status.HTTP_200_OK
)
async def subscription(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> SubscriptionResponse:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


@router.post('/portal', response_model=None, status_code=status.HTTP_200_OK)
async def portal(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> dict:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail='Subscription not found'
        )

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f'{settings_billing.frontend_url}/billing',
    )
    return {'portal_url': session.url}
