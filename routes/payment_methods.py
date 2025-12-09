"""
Routes for managing saved payment methods.
"""
from flask import Blueprint, request, jsonify, g
from flasgger.utils import swag_from
from middleware import login_required, get_current_user
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from services.payment_service import PaymentService
from pydantic import ValidationError

payment_methods_bp = Blueprint('payment_methods', __name__, url_prefix='/api/payment-methods')
payment_methods_bp.strict_slashes = False


@payment_methods_bp.route('', methods=['GET'])
@payment_methods_bp.route('/', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/payment_methods_list.yml")
def list_payment_methods():
    """
    Get all saved payment methods for the current user.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        methods, error = PaymentService.get_user_saved_payment_methods(user_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"payment_methods": methods}), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payment_methods_bp.route('', methods=['POST'])
@payment_methods_bp.route('/', methods=['POST'])
@auto_log_errors
@login_required()
@swag_from("../docs/payment_methods_create.yml")
def create_payment_method():
    """
    Create a new saved payment method.
    Request body:
    {
        "card_number": "4111111111111111",
        "exp_month": 12,
        "exp_year": 2025,
        "cvv": "123",
        "cardholder_name": "John Doe",
        "billing_address": {
            "line1": "123 Main St",
            "line2": "",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "country": "US"
        },
        "is_default": false
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
        
        # Validate required fields
        required_fields = ['card_number', 'exp_month', 'exp_year', 'cvv']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"}), 400
        
        saved_method, error = PaymentService.create_saved_payment_method(
            user_id=user_id,
            card_number=data['card_number'],
            exp_month=int(data['exp_month']),
            exp_year=int(data['exp_year']),
            cvv=data['cvv'],
            cardholder_name=data.get('cardholder_name'),
            billing_address=data.get('billing_address'),
            is_default=data.get('is_default', False)
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Payment method saved successfully",
            "payment_method": saved_method
        }), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payment_methods_bp.route('/<payment_method_id>/set-default', methods=['PUT'])
@auto_log_errors
@login_required()
@swag_from("../docs/payment_methods_set_default.yml")
def set_default_payment_method(payment_method_id):
    """
    Set a payment method as default.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        success, error = PaymentService.set_default_payment_method(user_id, payment_method_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not success:
            return jsonify({"error": "Failed to set default payment method"}), 400
        
        return jsonify({
            "message": "Default payment method updated successfully"
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payment_methods_bp.route('/<payment_method_id>', methods=['DELETE'])
@auto_log_errors
@login_required()
@swag_from("../docs/payment_methods_delete.yml")
def delete_payment_method(payment_method_id):
    """
    Delete a saved payment method (soft delete).
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        success, error = PaymentService.delete_saved_payment_method(user_id, payment_method_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not success:
            return jsonify({"error": "Failed to delete payment method"}), 400
        
        return jsonify({
            "message": "Payment method deleted successfully"
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

