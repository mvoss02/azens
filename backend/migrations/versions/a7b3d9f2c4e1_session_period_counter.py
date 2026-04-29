"""add sessions_used_this_period counter to subscriptions

Revision ID: a7b3d9f2c4e1
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 22:00:00.000000

Why: tier-based monthly session cap was using SELECT COUNT(*) on the
sessions table, which lets a user delete a session to free a quota slot.
Counter on the subscription row is the source of truth for "sessions
started this billing period" — never decrements on delete, resets only
on Stripe invoice.paid for billing_reason='subscription_cycle' (i.e.
real period rollover).

Backfill: existing subscription rows initialise to 0. Pre-launch only,
test users — generous reset is acceptable. If we ever need to backfill
real production usage, a SELECT COUNT(*) per row from the current
calendar-month boundary would approximate it, but that approximation
gets worse the further from the period start we are.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b3d9f2c4e1'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default='0' makes the column safe to add as NOT NULL on a
    # populated table — existing rows get the default at the SQL level
    # without a separate UPDATE step.
    op.add_column(
        'subscriptions',
        sa.Column(
            'sessions_used_this_period',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'sessions_used_this_period')
