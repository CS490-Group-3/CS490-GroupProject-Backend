"""
Appointment-related Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

# Enum for Appointment Status
AppointmentStatus = Literal[
    "scheduled",
    "confirmed",
    "completed",
    "cancelled",
    "no_show"
]


class AppointmentCreateRequest(BaseModel):
    """Request model for creating an appointment."""
    customer_id: Optional[str] = None
    barber_id: str
    service_id: str
    salon_id: str
    start_at: datetime
    end_at: Optional[datetime] # can compute from service.duration if ommitted
    notes: Optional[str] = None


class AppointmentUpdateRequest(BaseModel):
    """Request model for updating an appointment."""
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Response model for appointment details."""
    id: str
    customer_id: str
    barber_id: str
    service_id: str
    salon_id: str
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    notes: Optional[str]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    # allow ORM/db models to map directly
    model_config = ConfigDict(from_attributes=True)