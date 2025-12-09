"""
Routes for loyalty program (customer-facing).
"""
from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from middleware import login_required, get_current_user
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from services.loyalty_service import LoyaltyService
from services.error_logging_service import ErrorLoggingService
from config import supabase

loyalty_bp = Blueprint('loyalty', __name__, url_prefix='/api/loyalty')
loyalty_bp.strict_slashes = False


@loyalty_bp.route('/balance', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_balance.yml")
def get_loyalty_balance():
    """
    Get loyalty point balances for the current user across all salons.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        balances, error = LoyaltyService.get_user_loyalty_balances(user_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Format for frontend (match expected structure)
        salon_balances = []
        for balance in balances:
            salon_id = balance["salon_id"]
            
            # Get transaction activity for this salon
            transactions, _ = LoyaltyService.get_loyalty_transactions(
                user_id=user_id,
                salon_id=salon_id,
                limit=20
            )
            
            activity = []
            for trans in transactions:
                # Format date from created_at if date field doesn't exist
                trans_date = trans.get("date")
                if not trans_date and trans.get("created_at"):
                    trans_date = trans.get("created_at").split("T")[0]  # Extract date part
                
                activity.append({
                    "id": trans.get("id"),
                    "type": trans.get("transaction_type"),
                    "points": trans.get("points"),
                    "description": trans.get("description"),
                    "date": trans_date,
                    "appointmentId": trans.get("appointment_id")
                })
            
            # Don't calculate pending points here - return 0 initially, will be calculated async on frontend
            salon_balances.append({
                "salon_id": salon_id,
                "salon_name": balance["salon_name"],
                "balance": balance.get("balance", 0),
                "lifetime_points_earned": balance.get("lifetime_points_earned", 0),
                "lifetime_points_redeemed": balance.get("lifetime_points_redeemed", 0),
                "pending_points": 0,  # Will be calculated async on frontend
                "activity": activity
            })
        
        return jsonify({
            "salon_balances": salon_balances
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@loyalty_bp.route('/balance/<salon_id>', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_balance_salon.yml")
def get_loyalty_balance_for_salon(salon_id):
    """
    Get loyalty point balance for the current user at a specific salon.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"balance": balance}), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@loyalty_bp.route('/transactions', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_transactions.yml")
def get_loyalty_transactions():
    """
    Get loyalty transaction history for the current user.
    Query params: salon_id (optional), limit, offset
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        salon_id = request.args.get('salon_id')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        transactions, error = LoyaltyService.get_loyalty_transactions(
            user_id=user_id,
            salon_id=salon_id,
            limit=limit,
            offset=offset
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"transactions": transactions}), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@loyalty_bp.route('/rewards', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_rewards.yml")
def get_loyalty_rewards():
    """
    Get available loyalty rewards for a salon.
    Query params: salon_id (required)
    """
    try:
        salon_id = request.args.get('salon_id')
        if not salon_id:
            return jsonify({"error": "salon_id is required"}), 400
        
        program, error = LoyaltyService.get_loyalty_program(salon_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not program or not program.get("is_active"):
            return jsonify({
                "pointThreshold": 100,
                "rewardDiscount": 10
            }), 200  # Return defaults if no program
        
        return jsonify({
            "pointThreshold": program.get("min_points_for_redemption", 100),
            "rewardDiscount": program.get("discount", 10)
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@loyalty_bp.route('/redeem', methods=['POST'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_redeem.yml")
def redeem_loyalty_points():
    """
    Redeem loyalty points for a discount (used during payment).
    This endpoint is informational - actual redemption happens during payment creation.
    Request body:
    {
        "salon_id": "uuid"
    }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        salon_id = data.get('salon_id')
        if not salon_id:
            return jsonify({"error": "salon_id is required"}), 400
        
        # Get loyalty program
        program, error = LoyaltyService.get_loyalty_program(salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not program or not program.get("is_active"):
            return jsonify({"error": "Loyalty program not available for this salon"}), 400
        
        # Get user balance
        balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not balance:
            balance, error = LoyaltyService._get_or_create_balance(user_id, salon_id)
            if error:
                return jsonify({"error": error}), 400
        
        min_points = program.get("min_points_for_redemption", 100)
        current_balance = balance.get("points_balance", 0)
        
        if current_balance < min_points:
            return jsonify({
                "error": f"Insufficient points. Need {min_points}, have {current_balance}"
            }), 400
        
        return jsonify({
            "success": True,
            "message": f"You can redeem {min_points} points for a {program.get('discount', 10)}% discount",
            "pointThreshold": min_points,
            "rewardDiscount": program.get("discount", 10),
            "currentBalance": current_balance
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@loyalty_bp.route('/potential-points', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/loyalty_potential_points.yml")
def get_potential_points():
    """
    Calculate potential loyalty points for a given amount at a salon.
    Query params: salon_id (required), amount (required)
    """
    try:
        salon_id = request.args.get('salon_id')
        amount_str = request.args.get('amount')
        
        if not salon_id:
            return jsonify({"error": "salon_id is required"}), 400
        if not amount_str:
            return jsonify({"error": "amount is required"}), 400
        
        try:
            amount = float(amount_str)
        except ValueError:
            return jsonify({"error": "amount must be a valid number"}), 400
        
        points, error = LoyaltyService.calculate_potential_points(amount, salon_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "points": points,
            "amount": amount,
            "salon_id": salon_id
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

