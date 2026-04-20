"""add waitlist table

Revision ID: 676b2103145e
Revises: e5f6a7b8c9d0
Create Date: 2026-04-20 13:12:43.845642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '676b2103145e'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'waitlist',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        # Reference the existing Postgres enum created by the initial
        # migration — do NOT re-create it or other tables using the same
        # type (users.preferred_language, sessions.language) would collide.
        sa.Column(
            'language',
            postgresql.ENUM(name='language', create_type=False),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        # Composite: same email can be on multiple waitlists (case_studies,
        # and later drills/enterprise), but not the same one twice.
        sa.UniqueConstraint('email', 'source', name='uq_waitlist_email_source'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Only drop the table. The `language` enum type is shared with users
    # and sessions — dropping it here would break those tables on downgrade.
    op.drop_table('waitlist')
