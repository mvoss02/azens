"""add parsing_status + parsing_error to cvs

Revision ID: e5f6a7b8c9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-19 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Same enum-then-backfill pattern as feedback_status (c4d5e6f7a8b9).
    cv_parsing_status_enum = sa.Enum(
        'PENDING', 'PARSED', 'FAILED', name='cvparsingstatus'
    )
    cv_parsing_status_enum.create(op.get_bind(), checkfirst=True)

    # parsing_status: add nullable first, backfill, then tighten.
    op.add_column(
        'cvs',
        sa.Column('parsing_status', cv_parsing_status_enum, nullable=True),
    )
    # parsing_error: freeform diagnostic text shown to the user on retry.
    op.add_column(
        'cvs',
        sa.Column('parsing_error', sa.Text(), nullable=True),
    )

    # Backfill: rows with parsed_text are already done (from the lazy
    # session-start parsing path). Everything else is marked pending so the
    # next session-start triggers the inline safety-net parse.
    #
    # The `::cvparsingstatus` cast is required for UPDATEs — PG auto-casts
    # string literals only in comparisons, not assignments.
    op.execute(
        """
        UPDATE cvs SET parsing_status = (CASE
            WHEN parsed_text IS NOT NULL THEN 'PARSED'
            ELSE 'PENDING'
        END)::cvparsingstatus
        """
    )

    op.alter_column('cvs', 'parsing_status', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cvs', 'parsing_error')
    op.drop_column('cvs', 'parsing_status')
    sa.Enum(name='cvparsingstatus').drop(op.get_bind(), checkfirst=True)
