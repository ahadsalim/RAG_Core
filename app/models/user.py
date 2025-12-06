"""
User Models for Core System
User profiles and conversation history management
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import String, Text, Integer, JSON, ForeignKey, Index, Enum as SQLEnum, Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


# NOTE: UserTier removed - subscription management is handled by Users system
# RAG Core only stores user reference and usage statistics


class UserProfile(BaseModel):
    """User profile in Core system."""
    
    __tablename__ = "user_profiles"
    
    # External user ID from Users system
    external_user_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    
    # User information
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Usage statistics (for analytics only, not for limit enforcement)
    # NOTE: Subscription limits are enforced by Users system
    total_query_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # User preferences
    preferences: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    
    # Language and locale
    language: Mapped[str] = mapped_column(String(10), default="fa")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tehran")
    
    # Feature flags
    voice_search_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    image_search_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    streaming_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Statistics
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_feedback_given: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    __table_args__ = (
        Index("idx_user_external_id", "external_user_id"),
        Index("idx_user_email", "email"),
    )
    
    def increment_query_count(self):
        """Increment query counter for statistics."""
        self.total_query_count += 1
        self.last_active_at = datetime.utcnow()


class Conversation(BaseModel):
    """User conversation (chat session)."""
    
    __tablename__ = "conversations"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False
    )
    
    title: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    
    # Conversation metadata
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Context and settings for this conversation
    context: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    
    # Model settings for this conversation
    llm_model: Mapped[Optional[str]] = mapped_column(String(100))
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    
    # Archive status (for cleanup tasks)
    is_archived: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped["UserProfile"] = relationship(
        "UserProfile",
        back_populates="conversations"
    )
    
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="dynamic"
    )
    
    __table_args__ = (
        Index("idx_conversation_user", "user_id"),
        Index("idx_conversation_last_message", "last_message_at"),
    )
    
    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to the conversation."""
        self.message_count += 1
        self.last_message_at = datetime.utcnow()
        return Message(
            conversation_id=self.id,
            role=role,
            content=content,
            **kwargs
        )


class MessageRole(enum.Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Individual message in a conversation."""
    
    __tablename__ = "messages"
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole),
        nullable=False
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Retrieved context (for assistant messages)
    retrieved_chunks: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB)
    sources: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    
    # User feedback
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    
    # Model information (for tracking)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    model_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    
    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )
    
    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
        Index("idx_message_role", "role"),
        Index("idx_message_created", "created_at"),
    )


class QueryCache(BaseModel):
    """Cache for frequently asked queries."""
    
    __tablename__ = "query_cache"
    
    # Query information
    query_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )
    
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_embedding: Mapped[Optional[List[float]]] = mapped_column(JSONB)
    
    # Response
    response: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    
    # Metadata
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Model information
    model_used: Mapped[str] = mapped_column(String(100))
    
    # TTL
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    __table_args__ = (
        Index("idx_cache_hash", "query_hash"),
        Index("idx_cache_expires", "expires_at"),
        Index("idx_cache_hit_count", "hit_count"),
    )
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at
    
    def increment_hit(self):
        """Increment hit counter."""
        self.hit_count += 1
        self.last_hit_at = datetime.utcnow()


class MemoryCategory(str, enum.Enum):
    """Categories for user long-term memory items."""
    PERSONAL_INFO = "personal_info"      # سن، شغل، سطح دانش
    PREFERENCE = "preference"            # ترجیحات و سلیقه‌ها
    GOAL = "goal"                        # اهداف و پروژه‌ها
    INTEREST = "interest"                # علاقه‌مندی‌ها
    CONTEXT = "context"                  # زمینه کاری/تحصیلی
    BEHAVIOR = "behavior"                # سبک یادگیری، شخصیت
    OTHER = "other"


class UserMemory(BaseModel):
    """
    User Long-Term Memory - حافظه بلندمدت کاربر
    
    این جدول اطلاعات پایدار کاربر را ذخیره می‌کند که در تمام مکالمات استفاده می‌شود.
    هر کاربر می‌تواند چندین آیتم حافظه داشته باشد (5 تا 20 آیتم).
    """
    
    __tablename__ = "user_memories"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Memory content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Category for organization
    category: Mapped[MemoryCategory] = mapped_column(
        SQLEnum(MemoryCategory),
        default=MemoryCategory.OTHER,
        nullable=False
    )
    
    # Source tracking
    source_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Confidence and usage
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # For merging/updating
    version: Mapped[int] = mapped_column(Integer, default=1)
    merged_from: Mapped[Optional[List[str]]] = mapped_column(JSONB, default=list)
    
    # Soft delete (user can delete their memories)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    user: Mapped["UserProfile"] = relationship("UserProfile", backref="memories")
    
    __table_args__ = (
        Index("idx_memory_user", "user_id"),
        Index("idx_memory_category", "category"),
        Index("idx_memory_active", "is_active"),
        Index("idx_memory_user_active", "user_id", "is_active"),
    )
    
    def increment_usage(self):
        """Increment usage counter."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()


class UserFeedback(BaseModel):
    """User feedback on responses."""
    
    __tablename__ = "user_feedback"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False
    )
    
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Feedback data
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    feedback_type: Mapped[str] = mapped_column(String(50))  # accuracy, relevance, etc.
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    
    # Improvement suggestions
    suggested_response: Mapped[Optional[str]] = mapped_column(Text)
    
    # Processing status
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    __table_args__ = (
        Index("idx_feedback_user", "user_id"),
        Index("idx_feedback_message", "message_id"),
        Index("idx_feedback_processed", "processed"),
        Index("idx_feedback_rating", "rating"),
    )
