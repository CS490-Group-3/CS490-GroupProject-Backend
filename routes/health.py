"""
Health check and system status routes.
"""
from flask import Blueprint, jsonify
from config import supabase

health_bp = Blueprint('health', __name__)

""" Home endpoint - API information. """
@health_bp.route('/', methods=['GET'])
def home():
    
    return jsonify({
        "message": "Salonica: Salon Booking Platform API",
        "version": "1.0.0",
        "status": "running"
    }), 200

""" Health check endpoint - verifies Flask app and Supabase connection. """
@health_bp.route('/health', methods=['GET'])
def health_check():
    try:
        response = supabase.table('user_details').select("count", count="exact").limit(0).execute()

        return jsonify({
            "status": "healthy",
            "flask": "running",
            "supabase": "connected",
            "database": "accessible"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "flask": "running",
            "supabase": "error",
            "error": str(e)
        }), 500

