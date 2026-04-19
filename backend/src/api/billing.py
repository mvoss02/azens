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

# Single source of truth for (plan, cycle) -> Stripe price ID.
# The frontend sends plan + cycle slugs; we resolve them here. Never trust
# a price_id string coming from the client — a leaked valid price from a
# different product / tier would otherwise let a user checkout at the
# wrong plan level.
PLAN_CYCLE_TO_PRICE_ID: dict[tuple[str, str], str] = {
    ('analyst', 'monthly'): settings_billing.stripe_price_analyst_monthly,
    ('analyst', 'halfyearly'): settings_billing.stripe_price_analyst_halfyearly,
    ('associate', 'monthly'): settings_billing.stripe_price_associate_monthly,
    ('associate', 'halfyearly'): settings_billing.stripe_price_associate_halfyearly,
    ('managing_director', 'monthly'): settings_billing.stripe_price_managing_director_monthly,
    ('managing_director', 'halfyearly'): settings_billing.stripe_price_managing_director_halfyearly,
}

# Reverse lookups used by the webhook. A Stripe event carries a real price
# id; we map back to both our plan enum and our cycle slug. Using the price
# id as the lookup (rather than Stripe's raw `recurring.interval`) is
# important because a 6-monthly price is modelled as `interval=month,
# interval_count=6` — the first field alone doesn't distinguish monthly
# from half-yearly.
PRICE_TO_PLAN: dict[str, SubscriptionPlan] = {
    price_id: SubscriptionPlan[plan.upper()]
    for (plan, _cycle), price_id in PLAN_CYCLE_TO_PRICE_ID.items()
}
PRICE_TO_CYCLE: dict[str, str] = {
    price_id: cycle
    for (_plan, cycle), price_id in PLAN_CYCLE_TO_PRICE_ID.items()
}


def _period_end_ts(stripe_sub) -> int | None:
    """Read `current_period_end` tolerating both Stripe API shapes.

    - Older API versions: the field lives on the Subscription itself.
    - Newer versions (~2024+, including the 2026-03-25 "dahlia" release we
      currently see): it moved to each SubscriptionItem.

    Try item-level first, fall back to subscription-level. Bracket access
    instead of `.get()` because Stripe's StripeObject overrides __getattr__
    to do key lookups — `.get()` on it raises `AttributeError: get`.
    Returns None only if both locations are missing — caller should treat
    that as an unknown payload shape and log + skip rather than crash.
    """
    try:
        return stripe_sub['items']['data'][0]['current_period_end']
    except (KeyError, IndexError):
        pass
    try:
        return stripe_sub['current_period_end']
    except KeyError:
        return None


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

    # Resolve the (plan, cycle) slug pair to a real Stripe price ID. Pydantic's
    # Literal types on CheckoutRequest already guarantee the values are in our
    # known set, so a missing entry here would be a misconfiguration bug, not
    # a bad request — fail loudly.
    price_id = PLAN_CYCLE_TO_PRICE_ID.get((body.plan, body.cycle))
    if not price_id:
        logger.error(
            'No Stripe price configured for plan=%s cycle=%s', body.plan, body.cycle
        )
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Plan not available — please contact support',
        )

    session = stripe.checkout.Session.create(
        mode='subscription',
        customer_email=user.email,
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=f'{settings_billing.frontend_url}/app/billing?success=true',
        cancel_url=f'{settings_billing.frontend_url}/app/billing?cancelled=true',
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

    try:
        return await _dispatch_stripe_event(event, event_created, db)
    except Exception:
        # Any unexpected payload shape or downstream error lands here. We
        # log the full traceback (so we can actually fix it) and re-raise,
        # which becomes a 500 — Stripe will retry the event later. The
        # ProcessedStripeEvent row we inserted above gets rolled back with
        # the txn, so the retry sees a fresh event and dedupe doesn't bite.
        logger.exception(
            'Stripe webhook failed for event id=%s type=%s',
            event['id'], event['type'],
        )
        raise


async def _dispatch_stripe_event(event: dict, event_created: datetime, db: AsyncSession) -> dict:
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = UUID(session['metadata']['user_id'])

        # Resolve plan + cycle from the chosen price id. Using the PRICE_TO_*
        # maps (rather than Stripe's raw `recurring.interval`) correctly
        # distinguishes "every month" from "every 6 months" — both have
        # interval=month but different interval_count, which the raw field
        # alone hides.
        stripe_sub = stripe.Subscription.retrieve(session['subscription'])
        price_id = stripe_sub['items']['data'][0]['price']['id']
        period_end = _period_end_ts(stripe_sub)
        plan = PRICE_TO_PLAN.get(price_id)
        cycle = PRICE_TO_CYCLE.get(price_id)
        if plan is None or cycle is None or period_end is None:
            logger.error(
                'Unusable Stripe payload for session %s — price_id=%s plan=%s cycle=%s period_end=%s',
                session['id'], price_id, plan, cycle, period_end,
            )
            return {'received': True}

        # Create/update subscription record in your DB
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            # Create subscription
            new_sub = Subscription(
                user_id=user_id,
                plan=plan,
                is_active=True,
                stripe_customer_id=session['customer'],
                stripe_subscription_id=session['subscription'],
                billing_cycle=cycle,
                current_period_end=datetime.fromtimestamp(period_end, tz=UTC),
                last_stripe_event_at=event_created,
            )
            db.add(new_sub)
            await db.flush()  # flush sends the INSERT to DB and populates user.id, but doesn't commit yet
        else:
            # Update existing subscription
            sub.is_active = True
            sub.plan = plan
            sub.stripe_customer_id = session['customer']
            sub.stripe_subscription_id = session['subscription']
            sub.billing_cycle = cycle
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
            sub.last_stripe_event_at = event_created

    elif event['type'] == 'customer.subscription.updated':
        stripe_sub = event['data']['object']
        period_end = _period_end_ts(stripe_sub)
        if period_end is None:
            logger.warning(
                'Stripe update for sub %s has no period_end — skipping',
                stripe_sub['id'],
            )
            return {'received': True}
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

        if stripe_sub['cancel_at_period_end']:
            # User cancelled — still active until period end
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        else:
            # Could be a plan change — refresh plan + cycle from the new
            # price id so our local state mirrors what Stripe now bills.
            price_id = stripe_sub['items']['data'][0]['price']['id']
            sub.plan = PRICE_TO_PLAN.get(price_id, sub.plan)
            sub.billing_cycle = PRICE_TO_CYCLE.get(price_id, sub.billing_cycle)
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
        return_url=f'{settings_billing.frontend_url}/app/billing',
    )
    return {'portal_url': session.url}
