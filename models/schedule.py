"""
Barber availability Pydantic models.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import time, datetime
from uuid import UUID

class BarberAvailabilityCreateRequest(BaseModel):
    """Request model for creating barber weekly availability."""
    barber_id: str
    day_of_week: int = Field(ge=0, le=6, description="0=Sunday ... 6=Saturday")
    start_time: time
    end_time: time
    is_active: Optional[bool] = True


class BarberAvailabilityUpdateRequest(BaseModel):
    """Request model for updating availability entry."""
    id: Optional[UUID]= None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None


class BarberAvailabilityResponse(BaseModel):
    """Response model for barber weekly availability."""
    id: str
    barber_id: str
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

"""
Barber unavailability Pydantic models.
"""

class BarberUnavailabilityCreateRequest(BaseModel):
    """Request model for one-off barber unavailability (vacation, sick, etc.)."""
    barber_id: str
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = Field(None, max_length=255)


class BarberUnavailabilityUpdateRequest(BaseModel):
    """Request model for updating unavailability entry."""
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=255)


class BarberUnavailabilityResponse(BaseModel):
    """Response model for barber unavailability events."""
    id: str
    barber_id: str
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
