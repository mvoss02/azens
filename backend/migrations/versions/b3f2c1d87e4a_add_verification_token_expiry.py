"""add verification_token_expires column

Revision ID: b3f2c1d87e4a
Revises: a1e7c4d90b12
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f2c1d87e4a'
down_revision: Union[str, Sequence[str], None] = 'a1e7c4d90b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users',
    sa.Column('verification_token_expires', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'verification_token_expires')
