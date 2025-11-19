"""
Routes package initialization.
Imports all blueprints for easy registration.
"""
from .health import health_bp
from .auth import auth_bp
from .appointments import appointments_bp
from .schedule import schedule_bp
from .salon import salon_bp
from .upload import upload_bp
from .services import services_bp
from .admin import admin_bp
from .users import users_bp
__all__ = ['health_bp', 'auth_bp', 'appointments_bp', 'schedule_bp', 'salon_bp', 'upload_bp', 'services_bp', 'admin_bp', 'users_bp']

