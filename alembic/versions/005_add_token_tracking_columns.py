"""add token tracking columns to user_profiles

Add total_input_tokens and total_output_tokens columns for detailed token usage tracking.

Revision ID: 005
Revises: 004
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add token tracking columns to user_profiles
    op.add_column('user_profiles', sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user_profiles', sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove token tracking columns
    op.drop_column('user_profiles', 'total_output_tokens')
    op.drop_column('user_profiles', 'total_input_tokens')
