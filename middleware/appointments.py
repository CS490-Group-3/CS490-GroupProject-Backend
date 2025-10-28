"""
Appointments middleware and utilities using Supabase.
Provides helper functions for salon ownership filtering
and decorators for protecting appointment-based routes.
"""

from functools import wraps
from flask import jsonify
from middleware.auth import login_required, role_required, get_current_user
from config import supabase  
from services.appointment_service import AppointmentService

def get_owned_salons():
    """
    Fetch salons owned by the authenticated user from Supabase.

    Returns:
        List of salon dicts or empty list
    """
    user = get_current_user()
    if not user:
        return []

    owner_id = user.get("sub")
    if not owner_id:
        return []

    response = supabase.table("salons").select("*").eq("owner_id", owner_id).execute()

    if response.data:
        return response.data
    
    return []
