from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from config import supabase

from models.orders import OrderCreateRequest, OrderResponse, OrderItemCreateRequest
from services.orders_service import OrdersService
from flasgger.utils import swag_from

order_bp = Blueprint("order_bp", __name__, url_prefix="/api/orders")

@order_bp.route("/cart", methods=["GET"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_cart.yml")
def get_cart():
    """
    Retrieve the current user's cart with items.
    Query params: salon_id (required)
    """
    try:
        user_id = get_current_user().get('sub')
        salon_id = request.args.get("salon_id")
        if not salon_id:
            return jsonify({"error": "Missing 'salon_id' query parameter"}), 400
        
        cart, error = OrdersService.get_cart_with_items(user_id, salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Use model_validate with extra='allow' to include items field
        cart_response = OrderResponse.model_validate(cart, strict=False).model_dump()
        return jsonify({"cart": cart_response}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/items", methods=["POST"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_cart_add_item.yml")
def add_item_to_cart():
    """
    Add a product to the cart.
    """
    try:
        user_id = get_current_user().get('sub')
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        salon_id = json_data.get("salon_id")
        product_id = json_data.get("product_id")
        quantity = json_data.get("quantity", 1)
        
        if not salon_id:
            return jsonify({"error": "Missing 'salon_id'"}), 400
        if not product_id:
            return jsonify({"error": "Missing 'product_id'"}), 400
        if quantity < 1:
            return jsonify({"error": "Quantity must be at least 1"}), 400
        
        item, error = OrdersService.add_item_to_cart(user_id, salon_id, product_id, quantity)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not item:
            log_service_error("Item returned None from add_item_to_cart")
            return jsonify({"error": "Failed to add item to cart"}), 500
        
        # Recalculate totals
        cart, _ = OrdersService.get_active_cart(user_id, salon_id)
        if cart:
            OrdersService.calculate_order_totals(cart["id"])
        
        return jsonify({"item": item, "message": "Item added to cart"}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/items/<item_id>", methods=["PATCH"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_cart_update_item.yml")
def update_cart_item(item_id):
    """
    Update the quantity of a cart item.
    """
    try:
        user_id = get_current_user().get('sub')
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        order_id = json_data.get("order_id")
        quantity = json_data.get("quantity")
        
        if not order_id:
            return jsonify({"error": "Missing 'order_id'"}), 400
        if quantity is None or quantity < 1:
            return jsonify({"error": "Quantity must be at least 1"}), 400
        
        item, error = OrdersService.update_cart_item_quantity(user_id, order_id, item_id, quantity)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Recalculate totals
        OrdersService.calculate_order_totals(order_id)
        
        return jsonify({"item": item, "message": "Item updated"}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/cart/items/<item_id>", methods=["DELETE"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_cart_remove_item.yml")
def remove_cart_item(item_id):
    """
    Remove an item from the cart.
    """
    try:
        user_id = get_current_user().get('sub')
        order_id = request.args.get("order_id")
        if not order_id:
            return jsonify({"error": "Missing 'order_id' query parameter"}), 400
        
        success, error = OrdersService.remove_item_from_cart(user_id, order_id, item_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        if not success:
            return jsonify({"error": "Failed to remove item"}), 400
        
        # Recalculate totals
        OrdersService.calculate_order_totals(order_id)
        
        return jsonify({"message": "Item removed from cart"}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/checkout", methods=["POST"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_checkout.yml")
def checkout():
    """
    Checkout and process payment for an order.
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        order_id = json_data.get("order_id")
        shipping_address_data = json_data.get("shipping_address")
        delivery_method = json_data.get("delivery_method", "delivery")
        
        if not order_id:
            return jsonify({"error": "Missing 'order_id'"}), 400
        
        # Format shipping address - convert structured object to string if provided
        shipping_address = None
        if delivery_method == "delivery" and shipping_address_data:
            if isinstance(shipping_address_data, dict):
                # Format structured address as string
                parts = [shipping_address_data.get("line1", "")]
                if shipping_address_data.get("line2"):
                    parts.append(shipping_address_data.get("line2"))
                parts.append(f"{shipping_address_data.get('city', '')}, {shipping_address_data.get('state', '')} {shipping_address_data.get('zip', '')}")
                shipping_address = ", ".join([p for p in parts if p])
            elif isinstance(shipping_address_data, str):
                shipping_address = shipping_address_data
        elif delivery_method == "pickup":
            shipping_address = "PICKUP"
        
        # Get order with items to calculate total
        order, error = OrdersService.get_order_details(order_id)
        if error:
            return jsonify({"error": error}), 404
        
        if order["user_id"] != user_id:
            return jsonify({"error": "Order does not belong to user"}), 403
        
        if order["order_status"] != "cart":
            return jsonify({"error": "Order is not in cart status"}), 400
        
        # Get cart with items to get accurate total
        cart, error = OrdersService.get_cart_with_items(user_id, order["salon_id"])
        if error:
            return jsonify({"error": error}), 400
        
        if not cart.get("items") or len(cart["items"]) == 0:
            return jsonify({"error": "Cart is empty"}), 400
        
        payment_amount = float(cart.get("total_amount", 0))
        
        if payment_amount <= 0:
            return jsonify({"error": "Invalid order amount"}), 400
        
        # Update order status to pending and add shipping address
        updated_order_pending, error_pending = OrdersService.update_order_status(order_id, "pending", shipping_address, delivery_method)
        if error_pending:
            log_service_error(error_pending)
            return jsonify({"error": f"Failed to update order status: {error_pending}"}), 400
        
        # Process payment with loyalty and promotions
        from services.loyalty_service import LoyaltyService
        payment, error = LoyaltyService.process_order_payment_with_loyalty(
            user_id=user_id,
            order_id=order_id,
            payment_amount=payment_amount,
            payment_method_id=json_data.get('payment_method_id'),
            card_number=json_data.get('card_number'),
            exp_month=json_data.get('exp_month'),
            exp_year=json_data.get('exp_year'),
            cvv=json_data.get('cvv'),
            cardholder_name=json_data.get('cardholder_name'),
            billing_address=json_data.get('billing_address'),
            save_payment_method=json_data.get('save_payment_method', False),
            redeem_loyalty_points=json_data.get('redeem_loyalty_points', False),
            promotion_id=json_data.get('promotion_id')
        )
        
        if error:
            # Revert order status if payment fails
            OrdersService.update_order_status(order_id, "cart", None, None)
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Update order status to confirmed after successful payment
        updated_order_confirmed, error_confirmed = OrdersService.update_order_status(order_id, "confirmed", shipping_address, delivery_method)
        if error_confirmed:
            log_service_error(error_confirmed)
            return jsonify({"error": f"Failed to confirm order: {error_confirmed}"}), 400
        
        # Get updated order
        updated_order, _ = OrdersService.get_order_details(order_id)
        
        return jsonify({
            "message": "Order placed successfully",
            "order": updated_order,
            "payment": payment
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("", methods=["GET"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_list.yml")
def list_orders():
    """
    Get all orders for the current user (customer).
    Query params: salon_id (optional), status (optional), page (optional), limit (optional), sort (optional)
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        salon_id = request.args.get('salon_id')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        sort_order = request.args.get('sort', 'desc')
        
        orders, error, total_count = OrdersService.get_customer_orders(
            user_id, salon_id, status, page, limit, sort_order
        )
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "orders": orders,
            "total_count": total_count,
            "page": page,
            "limit": limit
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/salon/<salon_id>", methods=["GET"])
@auto_log_errors
@login_required()
@role_required(['owner', 'salon_owner'])
@swag_from("../docs/orders_salon.yml")
def get_salon_orders(salon_id):
    """
    Get all orders for a salon (owner only).
    Query params: status (optional), limit, offset
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        # Verify salon ownership
        salon_response = supabase.table("salons")\
            .select("id, owner_id")\
            .eq("id", salon_id)\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon = salon_response.data
        if salon["owner_id"] != user_id:
            return jsonify({"error": "Unauthorized: You don't own this salon"}), 403
        
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        orders, error, total_count = OrdersService.get_salon_orders(salon_id, status, limit, offset)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "orders": orders,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/<order_id>/status", methods=["PATCH"])
@auto_log_errors
@login_required()
@role_required(['owner', 'salon_owner'])
@swag_from("../docs/orders_update_status.yml")
def update_order_status_route(order_id):
    """
    Update order status (owner only).
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        new_status = json_data.get("status")
        if not new_status:
            return jsonify({"error": "Missing 'status' field"}), 400
        
        # Get order to verify ownership
        order, error = OrdersService.get_order_details(order_id)
        if error:
            return jsonify({"error": error}), 404
        
        # Verify salon ownership
        salon_response = supabase.table("salons")\
            .select("id, owner_id")\
            .eq("id", order["salon_id"])\
            .single()\
            .execute()
        
        if getattr(salon_response, "error", None) or not salon_response.data:
            return jsonify({"error": "Salon not found"}), 404
        
        salon = salon_response.data
        if salon["owner_id"] != user_id:
            return jsonify({"error": "Unauthorized: You don't own this salon"}), 403
        
        # Prevent status changes for cancelled orders
        if order.get("order_status") == "cancelled":
            return jsonify({"error": "Cannot change status of a cancelled order"}), 400
        
        # Update status
        updated_order, error = OrdersService.update_order_status(
            order_id, 
            new_status, 
            None, 
            None
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        # Award loyalty points when order is marked as delivered
        if new_status == "delivered":
            from services.loyalty_service import LoyaltyService
            LoyaltyService.award_points_for_delivered_order(order_id)
        
        return jsonify({"order": updated_order, "message": "Order status updated"}), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/<order_id>/cancel", methods=["PATCH"])
@auto_log_errors
@login_required()
@swag_from("../docs/orders_cancel.yml")
def cancel_order(order_id):
    """
    Cancel an order (customer only, pending or confirmed status).
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        json_data = request.get_json() or {}
        reason = json_data.get("reason")
        
        updated_order, error = OrdersService.cancel_order(order_id, user_id, reason, is_owner=False)
        
        if error:
            log_service_error(error)
            if "does not belong" in error or "Cannot cancel" in error:
                return jsonify({"error": error}), 400
            return jsonify({"error": error}), 400
        
        if not updated_order:
            log_service_error("Order cancellation returned no order data")
            return jsonify({"error": "Failed to cancel order: No order data returned"}), 500
        
        return jsonify({
            "order": updated_order,
            "message": "Order cancelled successfully. Payment refunded and loyalty points removed."
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@order_bp.route("/<order_id>/cancel-owner", methods=["PATCH"])
@auto_log_errors
@login_required()
@role_required(['owner', 'salon_owner'])
@swag_from("../docs/orders_cancel_owner.yml")
def cancel_order_owner(order_id):
    """
    Cancel an order (owner only, requires reason).
    """
    try:
        user = get_current_user()
        user_id = user.get('sub')
        
        json_data = request.get_json() or {}
        reason = json_data.get("reason")
        
        if not reason:
            return jsonify({"error": "Cancellation reason is required"}), 400
        
        updated_order, error = OrdersService.cancel_order(order_id, user_id, reason, is_owner=True)
        
        if error:
            log_service_error(error)
            if "does not belong" in error or "Cannot cancel" in error or "Unauthorized" in error:
                return jsonify({"error": error}), 400
            return jsonify({"error": error}), 400
        
        if not updated_order:
            log_service_error("Order cancellation returned no order data")
            return jsonify({"error": "Failed to cancel order: No order data returned"}), 500
        
        return jsonify({
            "order": updated_order,
            "message": "Order cancelled successfully. Payment refunded and loyalty points removed."
        }), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
     