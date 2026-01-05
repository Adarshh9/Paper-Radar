"""
Pydantic schemas for User API requests and responses.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Authentication schemas
class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded token data."""
    user_id: Optional[UUID] = None


# User schemas
class UserResponse(BaseModel):
    """User profile response."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    """User preferences update request."""
    interested_categories: Optional[List[str]] = None
    paper_maturity: Optional[str] = Field(
        None, 
        pattern="^(all|preprint_only|with_implementation|published_only)$"
    )
    update_frequency: Optional[str] = Field(
        None,
        pattern="^(daily|realtime)$"
    )


class UserPreferencesResponse(BaseModel):
    """User preferences response."""
    interested_categories: List[str] = []
    paper_maturity: str = "all"
    update_frequency: str = "daily"
    
    class Config:
        from_attributes = True


# Interaction schemas
class InteractionCreate(BaseModel):
    """Create user interaction request."""
    paper_id: UUID
    interaction_type: str = Field(
        ..., 
        pattern="^(view|save|read_summary|compare|unsave)$"
    )
    metadata: Optional[dict] = None


class InteractionResponse(BaseModel):
    """Interaction response."""
    id: UUID
    paper_id: UUID
    interaction_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True
