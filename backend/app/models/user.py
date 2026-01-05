"""
User model and related tables.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User accounts."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
    interactions = relationship("UserInteraction", back_populates="user")


class UserPreferences(Base):
    """User preferences for paper discovery."""
    
    __tablename__ = "user_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    
    interested_categories = Column(ARRAY(String), default=[], nullable=False)
    paper_maturity = Column(
        String(20), 
        default="all",
        nullable=False
    )  # "all", "preprint_only", "with_implementation", "published_only"
    update_frequency = Column(
        String(20), 
        default="daily",
        nullable=False
    )  # "daily", "realtime"
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="preferences")


class UserInteraction(Base):
    """User interactions with papers for recommendations."""
    
    __tablename__ = "user_interactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), index=True)
    
    interaction_type = Column(
        String(20), 
        nullable=False
    )  # "view", "save", "read_summary", "compare"
    interaction_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="interactions")
    
    # Composite index for efficient queries
    __table_args__ = (
        Index("ix_user_interactions_user_type_date", "user_id", "interaction_type", "created_at"),
    )
