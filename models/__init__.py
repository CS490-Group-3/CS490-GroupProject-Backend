"""
Models package initialization.
Contains Pydantic models for request/response validation.
"""
from .user import (
    UserSignupRequest,
    UserLoginRequest,
    UserProfileUpdate,
    UserRoleUpdate,
    UserProfileResponse,
    UserDetailsResponse,
    AuthResponse,
    UserRole
)
from .appointment import (
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    AppointmentResponse
)

from .schedule import (
    BarberAvailabilityCreateRequest,
    BarberAvailabilityUpdateRequest,
    BarberUnavailabilityCreateRequest,
    BarberUnavailabilityUpdateRequest
)
__all__ = [
    'UserSignupRequest',
    'UserLoginRequest',
    'UserProfileUpdate',
    'UserRoleUpdate',
    'UserProfileResponse',
    'UserDetailsResponse',
    'AuthResponse',
    'UserRole',
    'AppointmentCreateRequest',
    'AppointmentUpdateRequest',
    'AppointmentResponse',
    'BarberAvailabilityCreateRequest',
    'BarberAvailabilityUpdateRequest',
    'BarberUnavailabilityCreateRequest',
    'BarberUnavailabilityUpdateRequest'
]

