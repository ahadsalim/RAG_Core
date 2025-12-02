"""add is_archived and archived_at to conversations

Revision ID: 002_archive_fields
Revises: 001_initial_migration
Create Date: 2024-12-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_archived column with default value
    op.add_column(
        'conversations',
        sa.Column('is_archived', sa.Boolean(), nullable=True, default=False)
    )
    
    # Add archived_at column
    op.add_column(
        'conversations',
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Set default value for existing rows
    op.execute("UPDATE conversations SET is_archived = FALSE WHERE is_archived IS NULL")


def downgrade() -> None:
    op.drop_column('conversations', 'archived_at')
    op.drop_column('conversations', 'is_archived')
