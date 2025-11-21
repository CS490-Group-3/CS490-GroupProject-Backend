"""
User routes for customer-specific endpoints.
"""
from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from services.visit_history_service import VisitHistoryService
from middleware import login_required, get_current_user

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


@users_bp.route('/me/visits', methods=['GET'])
@login_required()
@swag_from("../docs/users_me_visits.yml")
def get_my_visits():
    """
    Get current user's complete visit history across all salons.
    Returns aggregated appointments, spend, images, and notes.
    
    Query Parameters:
        - salon_id: Optional filter by specific salon
    """
    try:
        user = get_current_user()
        customer_id = user.get('sub') or user.get('id')
        
        if not customer_id:
            return jsonify({"error": "User ID not found"}), 400
        
        # Optional salon filter
        salon_id = request.args.get('salon_id')
        
        history, error = VisitHistoryService.get_customer_visit_history(
            customer_id=customer_id,
            salon_id=salon_id
        )
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Visit history retrieved successfully",
            "history": history
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

