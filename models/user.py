"""
User-related Pydantic models for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, date


# Enum for user roles
UserRole = Literal['customer', 'salon_owner', 'barber', 'admin']

class UserSignupRequest(BaseModel):
    """Request model for user signup."""
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: UserRole = Field(default='customer', description="User role")


class UserLoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    """Request model for updating user profile."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    profile_image_url: Optional[str] = None
    date_of_birth: Optional[date] = None


class UserRoleUpdate(BaseModel):
    """Request model for admin updating user role."""
    role: UserRole


class UserProfileResponse(BaseModel):
    """Response model for user profile."""
    user_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    profile_image_url: Optional[str]
    date_of_birth: Optional[date]
    role: UserRole
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserDetailsResponse(BaseModel):
    """Complete user details including auth info."""
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    profile_image_url: Optional[str]
    date_of_birth: Optional[date]
    role: UserRole
    email_confirmed_at: Optional[datetime]
    last_sign_in_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    """Response model for authentication."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    user: UserDetailsResponse

