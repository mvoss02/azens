"""stripe webhook idempotency

Revision ID: a1e7c4d90b12
Revises: ffa8853a89ba
Create Date: 2026-04-18 23:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1e7c4d90b12'
down_revision: Union[str, Sequence[str], None] = 'ffa8853a89ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'processed_stripe_events',
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=255), nullable=False),
        sa.Column(
            'processed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.add_column(
        'subscriptions',
        sa.Column('last_stripe_event_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subscriptions', 'last_stripe_event_at')
    op.drop_table('processed_stripe_events')
