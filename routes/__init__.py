"""
Routes package initialization.
Imports all blueprints for easy registration.
"""
from .health import health_bp

__all__ = ['health_bp']

