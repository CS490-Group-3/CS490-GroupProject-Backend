from pydantic import BaseModel, EmailStr, model_validator, Field
from typing import Optional, List
from datetime import datetime


class SalonHourEntry(BaseModel):
    """
    A single day's hours during salon registration.
    """
    day_of_week: int = Field(ge=0, le=6, description="0 = Sunday ... 6 = Saturday")
    open_time: Optional[str] = Field(None, description="HH:MM or HH:MM:SS (24h)")
    close_time: Optional[str] = Field(None, description="HH:MM or HH:MM:SS (24h)")
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_times(self):
        if not self.is_closed:
            if not self.open_time or not self.close_time:
                raise ValueError("open_time and close_time are required when is_closed is false")
        return self


class SalonRegisterRequest(BaseModel):
    """
    Input validation for salon registration endpoint.
    """

    name: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=255, description="Street address")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(min_length=2, max_length=2, description="State code (e.g. NJ)")
    zip_code: Optional[str] = Field(pattern=r"^\d{5}$", description="5-digit ZIP code")
    phone: Optional[str] = Field(None,pattern=r"^\d{10}$",description="US phone number (10 digits, no separators)")
    email: Optional[EmailStr] = None
    description: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = None
    license_url: Optional[str] = Field(None, description="Public URL to uploaded license")
    timezone: Optional[str] = "America/New_York"
    hours: List[SalonHourEntry]

    @model_validator(mode="before")
    def at_least_one_contact(cls, values):
        """
        Ensure at least one contact method (phone or email) is provided.
        """
        phone = values.get("phone")
        email = values.get("email")
        if not (phone or email):
            raise ValueError("At least one contact method (phone or email) is required.")
        return values

