"""
Routes for salon owner-specific features (loyalty config, payments).
"""
from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from middleware import login_required, role_required, get_current_user
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from services.loyalty_service import LoyaltyService
from services.payment_service import PaymentService
from config import supabase

owner_bp = Blueprint('owner', __name__, url_prefix='/api/owner')
owner_bp.strict_slashes = False


@owner_bp.route('/loyalty/config', methods=['GET'])
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/owner_loyalty_config_get.yml")
def get_loyalty_config():
    """
    Get loyalty program configuration for the owner's salon.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        role = user.get('role')
        
        # Get owner's salon
        salon_response = supabase.table("salons")\
            .select("id")\
            .eq("owner_id", user_id)\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon_id = salon_response.data["id"]
        
        # Get loyalty program
        program, error = LoyaltyService.get_loyalty_program(salon_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Return defaults if no program exists
        if not program:
            return jsonify({
                "pointsPerDollar": 1.0,
                "pointThreshold": 100,
                "rewardDiscount": 10,
                "is_active": False
            }), 200
        
        return jsonify({
            "pointsPerDollar": float(program.get("points_per_dollar", 1.0)),
            "pointThreshold": program.get("min_points_for_redemption", 100),
            "rewardDiscount": program.get("discount", 10),
            "is_active": program.get("is_active", True)
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@owner_bp.route('/loyalty/config', methods=['POST', 'PUT'])
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/owner_loyalty_config_update.yml")
def update_loyalty_config():
    """
    Create or update loyalty program configuration.
    Request body:
    {
        "pointsPerDollar": 1.0,
        "pointThreshold": 100,
        "rewardDiscount": 10
    }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        role = user.get('role')
        
        # Get owner's salon
        salon_response = supabase.table("salons")\
            .select("id")\
            .eq("owner_id", user_id)\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon_id = salon_response.data["id"]
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        # Map frontend field names to backend
        points_per_dollar = data.get('pointsPerDollar', 1.0)
        discount = data.get('rewardDiscount', 10)
        min_points = data.get('pointThreshold', 100)
        
        # Create or update program
        program, error = LoyaltyService.create_or_update_loyalty_program(
            salon_id=salon_id,
            points_per_dollar=points_per_dollar,
            discount=discount,
            min_points_for_redemption=min_points,
            is_active=True
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "success": True,
            "message": "Loyalty program settings updated successfully",
            "config": {
                "pointsPerDollar": float(program.get("points_per_dollar", 1.0)),
                "pointThreshold": program.get("min_points_for_redemption", 100),
                "rewardDiscount": program.get("discount", 10)
            }
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@owner_bp.route('/payments', methods=['GET'])
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/owner_payments.yml")
def get_owner_payments():
    """
    Get payment history for the owner's salon.
    Query params: start_date, end_date
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        role = user.get('role')
        
        # Get owner's salon
        salon_response = supabase.table("salons")\
            .select("id")\
            .eq("owner_id", user_id)\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon_id = salon_response.data["id"]
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        payments, error = PaymentService.get_salon_payments(
            salon_id=salon_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify(payments), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@owner_bp.route('/revenue', methods=['GET'])
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/owner_revenue.yml")
def get_revenue_analytics():
    """
    Get comprehensive revenue analytics for the owner's salon.
    Query params: start_date (optional), end_date (optional)
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        
        # Get owner's salon
        salon_response = supabase.table("salons")\
            .select("id")\
            .eq("owner_id", user_id)\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon_id = salon_response.data["id"]
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        analytics, error = PaymentService.get_salon_revenue_analytics(
            salon_id=salon_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify(analytics), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

