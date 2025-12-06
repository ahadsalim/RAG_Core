"""Add user_memories table for long-term user memory

Revision ID: 004
Revises: 003
Create Date: 2025-12-06

This migration adds the user_memories table for storing
persistent user information across all conversations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Check if table already exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_memories'"
    ))
    if result.fetchone():
        return  # Table already exists, skip
    
    # Create enum if not exists
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE memorycategory AS ENUM "
        "('personal_info', 'preference', 'goal', 'interest', 'context', 'behavior', 'other'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    ))
    
    # Create user_memories table using raw SQL
    conn.execute(sa.text("""
        CREATE TABLE user_memories (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            category memorycategory NOT NULL DEFAULT 'other',
            source_conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
            confidence FLOAT NOT NULL DEFAULT 1.0,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE,
            version INTEGER NOT NULL DEFAULT 1,
            merged_from JSONB DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Create indexes
    conn.execute(sa.text("CREATE INDEX idx_memory_user ON user_memories(user_id)"))
    conn.execute(sa.text("CREATE INDEX idx_memory_category ON user_memories(category)"))
    conn.execute(sa.text("CREATE INDEX idx_memory_active ON user_memories(is_active)"))
    conn.execute(sa.text("CREATE INDEX idx_memory_user_active ON user_memories(user_id, is_active)"))


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_memory_user_active', table_name='user_memories')
    op.drop_index('idx_memory_active', table_name='user_memories')
    op.drop_index('idx_memory_category', table_name='user_memories')
    op.drop_index('idx_memory_user', table_name='user_memories')
    
    # Drop table
    op.drop_table('user_memories')
    
    # Drop enum
    memory_category = postgresql.ENUM(
        'personal_info', 'preference', 'goal', 'interest', 
        'context', 'behavior', 'other',
        name='memorycategory'
    )
    memory_category.drop(op.get_bind(), checkfirst=True)
