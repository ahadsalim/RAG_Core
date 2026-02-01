"""Initial schema - consolidated migration

This migration creates all tables with the current schema.
Consolidates all previous migrations (001-006) into a single clean migration.

Revision ID: 001
Revises: 
Create Date: 2026-02-01

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
        sa.Column('total_query_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='fa'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='Asia/Tehran'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_feedback_given', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_user_id')
    )
    op.create_index('idx_user_external_id', 'user_profiles', ['external_user_id'], unique=False)
    op.create_index('idx_user_email', 'user_profiles', ['email'], unique=False)
    
    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='4096'),
        sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
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
        sa.Column('tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('retrieved_chunks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feedback_rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('model_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
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
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_hit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
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
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_feedback_user', 'user_feedback', ['user_id'], unique=False)
    op.create_index('idx_feedback_message', 'user_feedback', ['message_id'], unique=False)
    op.create_index('idx_feedback_processed', 'user_feedback', ['processed'], unique=False)
    op.create_index('idx_feedback_rating', 'user_feedback', ['rating'], unique=False)
    
    # Create user_memories table
    op.create_table('user_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.Enum('PERSONAL_INFO', 'PREFERENCE', 'GOAL', 'INTEREST', 'CONTEXT', 'BEHAVIOR', 'OTHER', name='memorycategory'), nullable=False, server_default='OTHER'),
        sa.Column('source_conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('merged_from', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memory_user', 'user_memories', ['user_id'], unique=False)
    op.create_index('idx_memory_category', 'user_memories', ['category'], unique=False)
    op.create_index('idx_memory_active', 'user_memories', ['is_active'], unique=False)
    op.create_index('idx_memory_user_active', 'user_memories', ['user_id', 'is_active'], unique=False)


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('user_memories')
    op.drop_table('user_feedback')
    op.drop_table('query_cache')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('user_profiles')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS memorycategory')
    op.execute('DROP TYPE IF EXISTS messagerole')
