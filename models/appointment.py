"""
Appointment-related Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import date, time, datetime

# Enum for Appointment Status
AppointmentStatus = Literal[
    "scheduled",
    "completed",
    "canceled",
    "no_show"
]


class AppointmentCreateRequest(BaseModel):
    """Request model for creating an appointment."""
    customer_id: str
    barber_id: str
    service_id: str
    salon_id: str
    appointment_date: date
    start_time: time
    end_time: time
    notes: Optional[str] = None


class AppointmentUpdateRequest(BaseModel):
    """Request model for updating an appointment."""
    appointment_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
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
    appointment_date: date
    start_time: time
    end_time: time
    status: AppointmentStatus
    notes: Optional[str]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    # allow ORM/db models to map directly
    model_config = ConfigDict(from_attributes=True)