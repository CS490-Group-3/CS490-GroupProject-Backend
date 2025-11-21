"""
User-related Pydantic models for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Literal, List
from datetime import datetime, date


# Enum for user roles
UserRole = Literal['customer', 'salon_owner', 'barber', 'admin']

# Enum for age brackets
AgeBracket = Literal['18-24', '25-34', '35-44', '45-54', '55-64', '65+']

# Enum for gender
Gender = Literal['male', 'female', 'non-binary', 'prefer-not-to-say', 'other']

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
    city: Optional[str] = Field(None, max_length=100, description="User's city")
    state: Optional[str] = Field(None, max_length=50, description="User's state or province")
    age_bracket: Optional[AgeBracket] = Field(None, description="User's age bracket")
    gender: Optional[Gender] = Field(None, description="User's gender")
    preferred_services: Optional[List[str]] = Field(None, description="List of preferred service IDs or names")


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
    city: Optional[str] = None
    state: Optional[str] = None
    age_bracket: Optional[AgeBracket] = None
    gender: Optional[Gender] = None
    preferred_services: Optional[List[str]] = None
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
    city: Optional[str] = None
    state: Optional[str] = None
    age_bracket: Optional[AgeBracket] = None
    gender: Optional[Gender] = None
    preferred_services: Optional[List[str]] = None
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

