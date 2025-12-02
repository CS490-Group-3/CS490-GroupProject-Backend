from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user

from models.orders import OrderCreateRequest, OrderResponse
from services.orders_service import OrdersService
from flasgger.utils import swag_from

order_bp = Blueprint("order_bp", __name__, url_prefix="/api/orders")

@order_bp.route("/cart", methods=["GET"])
@login_required()
def get_cart():
    """
    Retrieve the current user's cart.
    """
    try:
        user_id = get_current_user().get('sub')
        json_data = request.get_json() or {}
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        salon_id = json_data.get("salon_id")
        if not salon_id:
            return jsonify({"error": "Missing 'salon_id'"}), 400
        
        cart, error = OrdersService.get_active_cart(user_id, salon_id)
        print("Cart retrieval result:", cart, error)
        if error:
            return jsonify({"error": error}), 400
        cart_response = OrderResponse.model_validate(cart).model_dump()
        return jsonify({"cart": cart_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    