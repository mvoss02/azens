"""add ON DELETE CASCADE to transcripts and feedback FKs

Revision ID: f1a2b3c4d5e6
Revises: aed33fe7b736
Create Date: 2026-04-28 18:30:00.000000

Why: deleting a session should automatically delete its transcripts +
feedback. Today the application code does an explicit bulk-delete in
the /session/:id DELETE endpoint, but anyone deleting a session row
directly (manual SQL, future admin script) would orphan children.
DB-level CASCADE makes the database the source of truth for this
relationship and lets us simplify the endpoint.

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'aed33fe7b736'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace plain FKs with ON DELETE CASCADE versions."""
    # transcripts.session_id → sessions.id
    op.drop_constraint(
        'transcripts_session_id_fkey', 'transcripts', type_='foreignkey'
    )
    op.create_foreign_key(
        'transcripts_session_id_fkey',
        'transcripts',
        'sessions',
        ['session_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # feedback.session_id → sessions.id
    op.drop_constraint(
        'feedback_session_id_fkey', 'feedback', type_='foreignkey'
    )
    op.create_foreign_key(
        'feedback_session_id_fkey',
        'feedback',
        'sessions',
        ['session_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Revert to plain FKs without cascade."""
    op.drop_constraint(
        'feedback_session_id_fkey', 'feedback', type_='foreignkey'
    )
    op.create_foreign_key(
        'feedback_session_id_fkey',
        'feedback',
        'sessions',
        ['session_id'],
        ['id'],
    )

    op.drop_constraint(
        'transcripts_session_id_fkey', 'transcripts', type_='foreignkey'
    )
    op.create_foreign_key(
        'transcripts_session_id_fkey',
        'transcripts',
        'sessions',
        ['session_id'],
        ['id'],
    )
