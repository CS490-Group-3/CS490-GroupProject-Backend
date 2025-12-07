from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user

from models.orders import OrderCreateRequest, OrderResponse, OrderUpdateRequest, OrderItemResponse, OrderItemCreateRequest, OrderItemUpdateRequest
from services.orders_service import OrdersService
from flasgger.utils import swag_from

order_bp = Blueprint("order_bp", __name__, url_prefix="/api/orders")

#-------------- Cart Routes ----#
@order_bp.route("/cart", methods=["GET"])
@login_required()
def get_cart():
    """
    Retrieve the current user's active carts.

    - If `?salon_id=<id>` is provided: returns that salon's active cart.
    - If no `salon_id` is provided: returns all active carts for the user.
    """
    try:
        user_id = get_current_user().get('sub')
        salon_id = request.args.get("salon_id")

        if salon_id:
            cart, error = OrdersService.get_active_cart(user_id, salon_id)
            if error:
                return jsonify({"error": error}), 404

            cart_response = OrderResponse.model_validate(cart).model_dump()
            return jsonify({"cart": cart_response}), 200 

        else:
            carts, error = OrdersService.get_all_active_carts(user_id)
            if error:
                return jsonify({"error": error}), 404

            carts_response = [
                OrderResponse.model_validate(c).model_dump()
                for c in carts
            ]

            return jsonify({"carts": carts_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/<order_id>", methods=["DELETE"])
@login_required()
def delete_order(order_id):
    """
    Delete an order by order ID.
    """
    try:
        success, error = OrdersService.delete_order(order_id)
        if error:
            return jsonify({"error2": error}), 400

        return jsonify({"message": "Order deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error1": str(e)}), 500
    
@order_bp.route("/cart/<order_id>/items", methods=["GET"])
@login_required()
def get_cart_items(order_id):
    """
    Retrieve items in the current user's active cart.
    """
    try:
        user_id = get_current_user().get('sub')
        if not order_id:
            return jsonify({"error": "There is no order_id"}), 400

        items, error = OrdersService.get_cart_items(order_id)
        if error:
            return jsonify({"error": error}), 404

        items_response = [
            OrderItemResponse.model_validate(item).model_dump()
            for item in items
        ]
        return jsonify({"items": items_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@order_bp.route("/cart/<order_id>/items", methods=["POST"])
@login_required()
def add_item(order_id):
    print("Add item route called for order_id:", order_id)
    try:
        user_id = get_current_user().get("sub")
        data = request.get_json()

        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)

        if not product_id:
            return jsonify({"error": "Missing product_id"}), 400

        item, error = OrdersService.add_item_to_cart(
            user_id=user_id,
            order_id=order_id,
            product_id=product_id,
            quantity=quantity
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "item": OrderItemResponse.model_validate(item).model_dump()
        }), 201
    except Exception as e:
        print("Error in add_item route:", str(e))
        return jsonify({"error": str(e)}), 500
@order_bp.route("/cart/<order_id>/items/<item_id>", methods=["GET"])
@login_required()
def get_cart_item(order_id, item_id):
    """
    Retrieve a specific item in the current user's active cart.
    """
    try:
        user_id = get_current_user().get('sub')

        item, error = OrdersService.get_cart_item(
            item_id=item_id
        )

        if error:
            return jsonify({"error": error}), 404

        return jsonify({
            "item": OrderItemResponse.model_validate(item).model_dump()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@order_bp.route("/cart/<order_id>/items/<item_id>", methods=["PATCH"])
@login_required()
def update_cart_item(order_id, item_id):
    """
    Update an item in the current user's active cart.
    Only quantity and unit_price can be updated.
    """
    try:
        user_id = get_current_user().get('sub')
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        item_update = OrderItemUpdateRequest.model_validate(data)

        updated_item, error = OrdersService.update_cart_item(
            order_id=order_id,
            item_id=item_id,
            item_update=item_update
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "item": OrderItemResponse.model_validate(updated_item).model_dump()
        }), 200
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/<order_id>/items/<item_id>", methods=["DELETE"])
@login_required()
def delete_cart_item(order_id, item_id):
    """
    Delete an item from the current user's active cart.
    """
    try:
        user_id = get_current_user().get('sub')

        success, error = OrdersService.remove_cart_item(
            order_id=order_id,
            item_id=item_id
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({"message": "Item deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/<order_id>/checkout", methods=["PATCH"])
@login_required()
def checkout_cart(order_id):
    """
    Checkout the current user's active cart.
    """
    try:
        user_id = get_current_user().get('sub')

        checked_out_order, error = OrdersService.checkout_cart(
            user_id=user_id,
            order_id=order_id
        )

        if error:
            return jsonify({"error": error}), 400

        order_response = OrderResponse.model_validate(checked_out_order).model_dump()
        return jsonify({"order": order_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@order_bp.route("/cart/<order_id>/canceled", methods=["PATCH"])
@login_required()
def cancel_cart(order_id):
    """
    Cancel the current user's pending, confirmed, or processing order.
    """
    try:
        user_id = get_current_user().get('sub')

        canceled_order, error = OrdersService.cancel_order(
            user_id=user_id,
            order_id=order_id
        )

        if error:
            return jsonify({"error": error}), 400

        order_response = OrderResponse.model_validate(canceled_order).model_dump()
        return jsonify({"order": order_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/<order_id>/status", methods=["PATCH"])
@login_required()
def update_order_status(order_id):
    """
    Update the status of an order.
    """
    try:
        user_id = get_current_user().get('sub')
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        order_update = OrderUpdateRequest.model_validate(data)
        order_status = order_update.order_status
        if not order_status:
            return jsonify({"error": "order_status is required"}), 400
        updated_order, error = OrdersService.update_order_status(
            order_id=order_id,
            new_status=order_status
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "order": OrderResponse.model_validate(updated_order).model_dump()
        }), 200
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
#-------------- Order Routes ----#
@order_bp.route("", methods=["GET"])
@login_required()
def list_orders_route():
    """
    List all orders for the current user.
    """
    try:
        user_id = get_current_user().get('sub')
        orders, error = OrdersService.list_orders(user_id)
        if error:
            return jsonify({"error": error}), 400

        orders_response = [
            OrderResponse.model_validate(order).model_dump()
            for order in orders
        ]
        return jsonify({"orders": orders_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@order_bp.route("", methods=["POST"])
@login_required()
def create_order_route():
    """
    Create a new order.
    """
    try:
        json_data = request.get_json()
        json_data["user_id"] = get_current_user().get('sub')
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400

        order_request = OrderCreateRequest.model_validate(json_data)
        created_order, error = OrdersService.create_order(order_request)
        if error:
            return jsonify({"error": error}), 500

        order_response = OrderResponse.model_validate(created_order).model_dump()
        return jsonify({"order": order_response}), 201
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_bp.route("/<order_id>", methods=["GET"])
@login_required()
def get_order(order_id):
    """
    Get order details by order ID.
    """
    try:
        order, error = OrdersService.get_order_details(order_id)
        if error:
            return jsonify({"error": error}), 404

        order_response = OrderResponse.model_validate(order).model_dump()
        return jsonify({"order": order_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


