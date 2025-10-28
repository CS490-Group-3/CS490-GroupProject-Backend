"""
Routes package initialization.
Imports all blueprints for easy registration.
"""
from .health import health_bp
from .auth import auth_bp
from .salon import salon_bp

__all__ = ['health_bp', 'auth_bp', 'salon_bp']

