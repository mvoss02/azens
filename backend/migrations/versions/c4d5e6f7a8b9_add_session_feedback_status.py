"""add feedback_status to session

Revision ID: c4d5e6f7a8b9
Revises: b3f2c1d87e4a
Create Date: 2026-04-19 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3f2c1d87e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    feedback_status_enum = sa.Enum(
        'PENDING', 'GENERATED', 'FAILED', 'SKIPPED', name='feedbackstatus'
    )
    feedback_status_enum.create(op.get_bind(), checkfirst=True)

    # Add the column nullable so the backfill below can run before we tighten
    # the constraint. SQLAlchemy stores Enum values as the member NAME (upper
    # case), so 'PENDING' — not 'pending' — is the correct literal.
    op.add_column(
        'sessions',
        sa.Column(
            'feedback_status',
            feedback_status_enum,
            nullable=True,
        ),
    )

    # Backfill: sessions that already have a feedback row → GENERATED.
    # Sessions that have ended (COMPLETED / ERROR) without feedback → SKIPPED,
    # because they're not going to retroactively produce one. Everything else
    # (PENDING / ACTIVE) → PENDING. All captured in a single UPDATE.
    #
    # The `::feedbackstatus` cast is required: PostgreSQL auto-casts string
    # literals to enum types for COMPARISONS (like the `status IN (…)` below),
    # but NOT for ASSIGNMENTS. Without the cast, PG rejects the UPDATE with
    # "column is of type feedbackstatus but expression is of type text."
    op.execute(
        """
        UPDATE sessions SET feedback_status = (CASE
            WHEN EXISTS (
                SELECT 1 FROM feedback WHERE feedback.session_id = sessions.id
            ) THEN 'GENERATED'
            WHEN status IN ('COMPLETED', 'ERROR') THEN 'SKIPPED'
            ELSE 'PENDING'
        END)::feedbackstatus
        """
    )

    # Now tighten to NOT NULL — every row has a value.
    op.alter_column('sessions', 'feedback_status', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sessions', 'feedback_status')
    sa.Enum(name='feedbackstatus').drop(op.get_bind(), checkfirst=True)
