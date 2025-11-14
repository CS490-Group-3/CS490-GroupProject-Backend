"""
Service Pydantic models.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class ServiceCreateRequest(BaseModel):
    """Request model for creating a service."""
    salon_id: str = Field(description="ID of the salon offering the service")
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    duration_minutes: int = Field(gt=0, description="Service duration in minutes")
    price: str
    is_active: Optional[bool] = True


class ServiceUpdateRequest(BaseModel):
    """Request model for updating a service."""
    id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    price: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceResponse(BaseModel):
    """Response model for a service."""
    id: str
    salon_id: str
    name: str
    description: Optional[str]
    duration_minutes: int
    price: Optional[Decimal]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

