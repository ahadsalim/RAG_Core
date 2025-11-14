"""Initial migration - Create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_profiles table
    op.create_table('user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_user_id', sa.String(length=100), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('tier', sa.Enum('FREE', 'BASIC', 'PREMIUM', 'ENTERPRISE', name='usertier'), nullable=False),
        sa.Column('daily_query_limit', sa.Integer(), nullable=False),
        sa.Column('daily_query_count', sa.Integer(), nullable=False),
        sa.Column('total_query_count', sa.Integer(), nullable=False),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('voice_search_enabled', sa.Boolean(), nullable=False),
        sa.Column('image_search_enabled', sa.Boolean(), nullable=False),
        sa.Column('streaming_enabled', sa.Boolean(), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False),
        sa.Column('total_feedback_given', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_user_id')
    )
    op.create_index('idx_user_external_id', 'user_profiles', ['external_user_id'], unique=False)
    op.create_index('idx_user_email', 'user_profiles', ['email'], unique=False)
    op.create_index('idx_user_tier', 'user_profiles', ['tier'], unique=False)
    
    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('max_tokens', sa.Integer(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conversation_user', 'conversations', ['user_id'], unique=False)
    op.create_index('idx_conversation_last_message', 'conversations', ['last_message_at'], unique=False)
    
    # Create messages table
    op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('USER', 'ASSISTANT', 'SYSTEM', name='messagerole'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tokens', sa.Integer(), nullable=False),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('retrieved_chunks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feedback_rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('model_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_message_conversation', 'messages', ['conversation_id'], unique=False)
    op.create_index('idx_message_role', 'messages', ['role'], unique=False)
    op.create_index('idx_message_created', 'messages', ['created_at'], unique=False)
    
    # Create query_cache table
    op.create_table('query_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query_hash', sa.String(length=64), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=False),
        sa.Column('last_hit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('query_hash')
    )
    op.create_index('idx_cache_hash', 'query_cache', ['query_hash'], unique=False)
    op.create_index('idx_cache_expires', 'query_cache', ['expires_at'], unique=False)
    op.create_index('idx_cache_hit_count', 'query_cache', ['hit_count'], unique=False)
    
    # Create user_feedback table
    op.create_table('user_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('feedback_type', sa.String(length=50), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('suggested_response', sa.Text(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_feedback_user', 'user_feedback', ['user_id'], unique=False)
    op.create_index('idx_feedback_message', 'user_feedback', ['message_id'], unique=False)
    op.create_index('idx_feedback_processed', 'user_feedback', ['processed'], unique=False)
    op.create_index('idx_feedback_rating', 'user_feedback', ['rating'], unique=False)


def downgrade() -> None:
    # Drop all tables and indexes
    op.drop_table('user_feedback')
    op.drop_table('query_cache')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('user_profiles')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS usertier')
    op.execute('DROP TYPE IF EXISTS messagerole')
