"""remove subscription fields from user_profiles

Subscription management moved to Users system.
RAG Core only tracks usage statistics.

Revision ID: 003
Revises: 002
Create Date: 2024-12-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove subscription-related columns
    # These are now managed by Users system
    op.drop_column('user_profiles', 'tier')
    op.drop_column('user_profiles', 'daily_query_limit')
    op.drop_column('user_profiles', 'daily_query_count')
    
    # Drop the tier enum type
    op.execute("DROP TYPE IF EXISTS usertier")


def downgrade() -> None:
    # Recreate the enum type
    op.execute("CREATE TYPE usertier AS ENUM ('free', 'basic', 'premium', 'enterprise')")
    
    # Recreate columns
    op.add_column('user_profiles', sa.Column('tier', sa.Enum('free', 'basic', 'premium', 'enterprise', name='usertier'), nullable=False, server_default='free'))
    op.add_column('user_profiles', sa.Column('daily_query_limit', sa.Integer(), nullable=False, server_default='50'))
    op.add_column('user_profiles', sa.Column('daily_query_count', sa.Integer(), nullable=False, server_default='0'))
