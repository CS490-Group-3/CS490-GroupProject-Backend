from config import supabase
from typing import Dict, Optional, Tuple, List
from gotrue.errors import AuthApiError
import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from models.orders import OrderCreateRequest, OrderResponse, OrderUpdateRequest, OrderItemCreateRequest, OrderItemUpdateRequest
from services.error_logging_service import ErrorLoggingService
from services.audit_logging_service import AuditLoggingService
class OrdersService:
    @staticmethod
    def get_order_details(
        order_id: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get an order by its ID.

        Args:
            order_id: ID of the order to retrieve

        Returns:
            Tuple containing the order dict or None, and an error message or None
        """
        try:
            response = supabase.table("orders").select("*").eq("id", order_id).single().execute()
            if response is None:
                return None, "Database error: No response from database"
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            data = response.data if hasattr(response, "data") else None
            if not data:
                return None, "Order not found"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def create_order(
        data: OrderCreateRequest
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a new order.

        Args:
            user_id: ID of the user placing the order
            salon_id: ID of the salon
            total_amount: Total amount of the order as a string
            status: Status of the order
            notes: Optional notes for the order

        Returns:
            Tuple containing the created order dict or None, and an error message or None
        """
        try:
            response = supabase.table("orders").insert(data.dict()).execute()
            if response is None:
                return None, "Database error: No response from database"
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            if not response.data or len(response.data) == 0:
                print("Order creation response data is empty:", response)
                return None, "Failed to create order"

            created_order = response.data[0]
            return created_order, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_active_cart(user_id: str, salon_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get the active cart (order with status 'cart') for a user in a specific salon.

        Args:
            user_id: ID of the user
            salon_id: ID of the salon

        Returns:
            Tuple containing the active cart order dict or None, and an error message or None
        """
        try:
            response = supabase.table("orders").select("*").eq("user_id", user_id).eq("salon_id", salon_id).eq("order_status", "cart").execute()
            if response is None:
                return None, "Database error: No response from database"
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            data = response.data if hasattr(response, "data") else None
            print("Active cart query response data:", response)
            if not data:
                print("No active cart found, creating a new one.")
                cart,error = OrdersService.create_order(OrderCreateRequest(
                    user_id=user_id, salon_id=salon_id))
                print("New cart creation result:", cart, error)
                if error:
                    return None, error
                return cart, None

            return data[0], None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def get_cart_with_items(user_id: str, salon_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get the active cart with all order items.
        
        Args:
            user_id: ID of the user
            salon_id: ID of the salon
            
        Returns:
            Tuple containing the cart dict with items or None, and an error message or None
        """
        try:
            # Get cart
            cart, error = OrdersService.get_active_cart(user_id, salon_id)
            if error:
                return None, error
            
            # Get order items
            items_response = supabase.table("order_items")\
                .select("*, products:product_id(id, name, price, image_url, description)")\
                .eq("order_id", cart["id"])\
                .execute()
            
            if items_response is None:
                items = []
            elif getattr(items_response, "error", None):
                items = []
            else:
                items = items_response.data if items_response.data else []
            
            # Calculate totals
            subtotal = sum(float(item.get("subtotal", 0)) for item in items)
            tax = subtotal * 0.08  # 8% tax (configurable)
            shipping = 0.0  # Free shipping for now
            total = subtotal + tax + shipping
            
            # Update cart totals
            cart["items"] = items
            cart["subtotal"] = subtotal
            cart["tax"] = tax
            cart["shipping_cost"] = shipping
            cart["total_amount"] = total
            
            return cart, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, str(e)
    
    @staticmethod
    def add_item_to_cart(
        user_id: str,
        salon_id: str,
        product_id: str,
        quantity: int
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Add a product to the cart (or update quantity if already exists).
        
        Args:
            user_id: ID of the user
            salon_id: ID of the salon
            product_id: ID of the product
            quantity: Quantity to add
            
        Returns:
            Tuple containing the order item dict or None, and an error message or None
        """
        try:
            # Verify product exists and belongs to salon
            product_response = supabase.table("products")\
                .select("id, price, stock_quantity, is_active")\
                .eq("id", product_id)\
                .eq("salon_id", salon_id)\
                .single()\
                .execute()
            
            if product_response is None:
                return None, "Database error: No response from database"
            
            if getattr(product_response, "error", None) or not getattr(product_response, "data", None):
                return None, "Product not found or does not belong to this salon"
            
            product = product_response.data
            
            if not product.get("is_active", True):
                return None, "Product is not available"
            
            # Check stock
            stock = product.get("stock_quantity")
            if stock is not None and stock < quantity:
                return None, f"Insufficient stock. Available: {stock}"
            
            # Get or create cart
            cart, error = OrdersService.get_active_cart(user_id, salon_id)
            if error:
                return None, error
            
            order_id = cart["id"]
            unit_price = float(product["price"])
            
            # Check if item already exists in cart
            existing_item_response = supabase.table("order_items")\
                .select("*")\
                .eq("order_id", order_id)\
                .eq("product_id", product_id)\
                .maybe_single()\
                .execute()
            
            if existing_item_response and getattr(existing_item_response, "data", None):
                # Update quantity
                existing_item = existing_item_response.data
                new_quantity = existing_item.get("quantity", 0) + quantity
                
                # Check stock again with new total
                if stock is not None and stock < new_quantity:
                    return None, f"Insufficient stock. Available: {stock}"
                
                new_subtotal = unit_price * new_quantity
                
                update_response = supabase.table("order_items")\
                    .update({
                        "quantity": new_quantity,
                        "subtotal": new_subtotal
                    })\
                    .eq("id", existing_item["id"])\
                    .execute()
                
                # Check if response is None
                if update_response is None:
                    return None, "Database error: No response from database"
                
                # Check for errors
                if getattr(update_response, "error", None):
                    return None, update_response.error.message
                
                # Get updated item from response
                updated_item = existing_item  # Fallback to existing item
                if update_response.data and len(update_response.data) > 0:
                    updated_item = update_response.data[0]
                
                return updated_item, None
            else:
                # Create new item
                subtotal = unit_price * quantity
                
                item_data = {
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                    "subtotal": subtotal
                }
                
                insert_response = supabase.table("order_items")\
                    .insert(item_data)\
                    .execute()
                
                # Check if response is None
                if insert_response is None:
                    return None, "Database error: No response from database"
                
                # Check for errors
                if getattr(insert_response, "error", None):
                    return None, insert_response.error.message
                
                # Get created item from response
                created_item = None
                if insert_response.data and len(insert_response.data) > 0:
                    created_item = insert_response.data[0]
                
                # Fallback: fetch the inserted row if insert didn't return data
                if created_item is None:
                    fetch_response = supabase.table("order_items")\
                        .select("*")\
                        .eq("order_id", order_id)\
                        .eq("product_id", product_id)\
                        .order("created_at", desc=True)\
                        .limit(1)\
                        .maybe_single()\
                        .execute()
                    
                    if fetch_response and getattr(fetch_response, "data", None):
                        created_item = fetch_response.data
                    
                    if created_item is None:
                        return None, "Failed to add item to cart: No data returned"
                
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='order_items',
                    record_id=created_item["id"],
                    action='INSERT',
                    new_values=item_data,
                    changed_by=user_id
                )
                
                return created_item, None
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, str(e)
    
    @staticmethod
    def update_cart_item_quantity(
        user_id: str,
        order_id: str,
        item_id: str,
        quantity: int
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update the quantity of a cart item.
        
        Args:
            user_id: ID of the user (for verification)
            order_id: ID of the order
            item_id: ID of the order item
            quantity: New quantity
            
        Returns:
            Tuple containing the updated order item dict or None, and an error message or None
        """
        try:
            if quantity <= 0:
                return None, "Quantity must be greater than 0"
            
            # Verify order belongs to user
            order_response = supabase.table("orders")\
                .select("id, user_id, order_status")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            if order_response is None:
                return None, "Database error: No response from database"
            
            if getattr(order_response, "error", None) or not getattr(order_response, "data", None):
                return None, "Order not found"
            
            order = order_response.data
            if order["user_id"] != user_id:
                return None, "Order does not belong to user"
            
            if order["order_status"] != "cart":
                return None, "Can only update items in cart"
            
            # Get item
            item_response = supabase.table("order_items")\
                .select("*, products:product_id(id, price, stock_quantity)")\
                .eq("id", item_id)\
                .eq("order_id", order_id)\
                .single()\
                .execute()
            
            if item_response is None:
                return None, "Database error: No response from database"
            
            if getattr(item_response, "error", None) or not getattr(item_response, "data", None):
                return None, "Order item not found"
            
            item = item_response.data
            product = item.get("products")
            
            # Check stock
            if isinstance(product, dict):
                stock = product.get("stock_quantity")
                if stock is not None and stock < quantity:
                    return None, f"Insufficient stock. Available: {stock}"
            
            # Update quantity and subtotal
            unit_price = float(item.get("unit_price", 0))
            new_subtotal = unit_price * quantity
            
            update_response = supabase.table("order_items")\
                .update({
                    "quantity": quantity,
                    "subtotal": new_subtotal
                })\
                .eq("id", item_id)\
                .execute()
            
            if update_response is None:
                return None, "Database error: No response from database"
            
            if getattr(update_response, "error", None):
                return None, update_response.error.message
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='order_items',
                record_id=item_id,
                action='UPDATE',
                old_values={"quantity": item.get("quantity"), "subtotal": item.get("subtotal")},
                new_values={"quantity": quantity, "subtotal": new_subtotal},
                changed_by=user_id
            )
            
            updated_item = item  # Fallback to original item
            if update_response.data and len(update_response.data) > 0:
                updated_item = update_response.data[0]
            
            return updated_item, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, str(e)
    
    @staticmethod
    def remove_item_from_cart(
        user_id: str,
        order_id: str,
        item_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Remove an item from the cart.
        
        Args:
            user_id: ID of the user (for verification)
            order_id: ID of the order
            item_id: ID of the order item
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify order belongs to user
            order_response = supabase.table("orders")\
                .select("id, user_id, order_status")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            if order_response is None:
                return False, "Database error: No response from database"
            
            if getattr(order_response, "error", None) or not getattr(order_response, "data", None):
                return False, "Order not found"
            
            order = order_response.data
            if order["user_id"] != user_id:
                return False, "Order does not belong to user"
            
            if order["order_status"] != "cart":
                return False, "Can only remove items from cart"
            
            # Get item for audit log
            item_response = supabase.table("order_items")\
                .select("*")\
                .eq("id", item_id)\
                .eq("order_id", order_id)\
                .single()\
                .execute()
            
            if item_response is None:
                return False, "Database error: No response from database"
            
            if getattr(item_response, "error", None) or not getattr(item_response, "data", None):
                return False, "Order item not found"
            
            old_item = item_response.data
            
            # Delete item
            delete_response = supabase.table("order_items")\
                .delete()\
                .eq("id", item_id)\
                .eq("order_id", order_id)\
                .execute()
            
            if delete_response is None:
                return False, "Database error: No response from database"
            
            if getattr(delete_response, "error", None):
                return False, delete_response.error.message
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='order_items',
                record_id=item_id,
                action='DELETE',
                old_values=old_item,
                changed_by=user_id
            )
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return False, str(e)
    
    @staticmethod
    def calculate_order_totals(order_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Calculate and update order totals based on items.
        
        Args:
            order_id: ID of the order
            
        Returns:
            Tuple containing totals dict or None, and an error message or None
        """
        try:
            # Get all items
            items_response = supabase.table("order_items")\
                .select("subtotal")\
                .eq("order_id", order_id)\
                .execute()
            
            if items_response is None:
                items = []
            elif getattr(items_response, "error", None):
                items = []
            else:
                items = items_response.data if items_response.data else []
            
            # Calculate totals
            subtotal = sum(float(item.get("subtotal", 0)) for item in items)
            tax = subtotal * 0.08  # 8% tax
            shipping = 0.0  # Free shipping
            total = subtotal + tax + shipping
            
            # Update order
            update_response = supabase.table("orders")\
                .update({
                    "subtotal": subtotal,
                    "tax": tax,
                    "shipping_cost": shipping,
                    "total_amount": total
                })\
                .eq("id", order_id)\
                .execute()
            
            if update_response is None:
                return None, "Database error: No response from database"
            
            if getattr(update_response, "error", None):
                return None, update_response.error.message
            
            return {
                "subtotal": subtotal,
                "tax": tax,
                "shipping_cost": shipping,
                "total_amount": total
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, str(e)
    
    @staticmethod
    def update_order_status(
        order_id: str,
        status: str,
        shipping_address: Optional[str] = None,
        delivery_method: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update order status (e.g., from 'cart' to 'pending' during checkout).
        
        Args:
            order_id: ID of the order
            status: New status
            shipping_address: Optional shipping address (string)
            delivery_method: Optional delivery method ("pickup" or "delivery")
            
        Returns:
            Tuple containing the updated order dict or None, and an error message or None
        """
        try:
            # First, get the current order to check if we're transitioning from "cart"
            current_order_resp = supabase.table("orders")\
                .select("order_status")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            current_status = None
            if current_order_resp and not getattr(current_order_resp, "error", None) and hasattr(current_order_resp, "data") and current_order_resp.data:
                current_status = current_order_resp.data.get("order_status")
            
            update_data = {"order_status": status}
            if shipping_address:
                update_data["shipping_address"] = shipping_address
            # Store delivery method in notes field for pickup orders
            if delivery_method == "pickup":
                update_data["notes"] = "PICKUP ORDER"
            
            # If transitioning from "cart" to a non-cart status, update created_at to reflect actual order placement time
            if current_status == "cart" and status != "cart":
                update_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            response = supabase.table("orders")\
                .update(update_data)\
                .eq("id", order_id)\
                .execute()
            
            if response is None:
                return None, "Database error: No response from database"
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            # Supabase update returns data by default
            updated_order = None
            if hasattr(response, "data") and response.data and len(response.data) > 0:
                updated_order = response.data[0]
            else:
                # If no data returned, fetch the order again to verify update
                order_resp = supabase.table("orders")\
                    .select("*")\
                    .eq("id", order_id)\
                    .single()\
                    .execute()
                if order_resp and not getattr(order_resp, "error", None) and hasattr(order_resp, "data") and order_resp.data:
                    updated_order = order_resp.data
                else:
                    return None, "Failed to update order: Order not found after update"
            
            # Verify the status was actually updated
            if updated_order.get("order_status") != status:
                return None, f"Failed to update order status: Expected {status}, got {updated_order.get('order_status')}"
            
            return updated_order, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, str(e)
    
    @staticmethod
    def get_customer_orders(
        user_id: str,
        salon_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        sort_order: str = "desc"
    ) -> Tuple[List[Dict], Optional[str], int]:
        """
        Get all orders for a customer (excluding cart status).
        
        Args:
            user_id: Customer user ID
            salon_id: Optional salon ID to filter by
            status: Optional status filter
            page: Page number (1-indexed)
            limit: Number of results per page
            sort_order: Sort order ("asc" or "desc")
            
        Returns:
            Tuple of (list of orders with items, error_message, total_count)
        """
        try:
            query = supabase.table("orders")\
                .select("*, order_items(*, products(*)), salons:salon_id(id, name, address, city, state)")\
                .eq("user_id", user_id)\
                .neq("order_status", "cart")\
                .order("created_at", desc=True)
            
            if salon_id:
                query = query.eq("salon_id", salon_id)
            
            if status:
                query = query.eq("order_status", status)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            orders = response.data or []
            
            # Get payment IDs for all orders to fetch loyalty transactions
            order_ids = [order.get("id") for order in orders if order.get("id")]
            payments_map = {}
            payments_info = {}
            loyalty_transactions_map = {}
            
            if order_ids:
                try:
                        # Get payments for these orders
                    payments_response = supabase.table("payments")\
                        .select("id, order_id, amount")\
                        .in_("order_id", order_ids)\
                        .eq("payment_status", "completed")\
                        .execute()
                    
                    if payments_response and not getattr(payments_response, "error", None):
                        payments = payments_response.data or []
                        # Map order_id -> payment_id and store payment info
                        for payment in payments:
                            order_id = payment.get("order_id")
                            payment_id = payment.get("id")
                            if order_id and payment_id:
                                payments_map[order_id] = payment_id
                                payments_info[order_id] = payment
                        
                        # Get loyalty transactions for these payments
                        payment_ids = [p.get("id") for p in payments if p.get("id")]
                        if payment_ids:
                            loyalty_response = supabase.table("loyalty_transactions")\
                                .select("id, payment_id, transaction_type, points, description, created_at")\
                                .in_("payment_id", payment_ids)\
                                .execute()
                            
                            if loyalty_response and not getattr(loyalty_response, "error", None):
                                transactions = loyalty_response.data or []
                                # Map payment_id -> list of transactions
                                for trans in transactions:
                                    payment_id = trans.get("payment_id")
                                    if payment_id:
                                        if payment_id not in loyalty_transactions_map:
                                            loyalty_transactions_map[payment_id] = []
                                        loyalty_transactions_map[payment_id].append(trans)
                except Exception as e:
                    ErrorLoggingService.log_exception(e, severity='low')
                    # Continue without loyalty info if fetch fails
            
            # Format orders
            formatted_orders = []
            for order in orders:
                order_id = order.get("id")
                payment_id = payments_map.get(order_id)
                loyalty_transactions = loyalty_transactions_map.get(payment_id, []) if payment_id else []
                
                # Calculate points earned and redeemed
                points_earned = 0
                points_redeemed = 0
                for trans in loyalty_transactions:
                    points = trans.get("points", 0)
                    trans_type = trans.get("transaction_type", "")
                    if trans_type == "earned" and points > 0:
                        points_earned += points
                    elif trans_type == "redeemed" and points < 0:
                        points_redeemed += abs(points)
                
                # Calculate pending points for orders not yet delivered
                points_pending = 0
                if order.get("order_status") not in ["delivered", "cancelled"] and payment_id:
                    try:
                        from services.loyalty_service import LoyaltyService
                        salon_id = order.get("salon_id")
                        # Get actual payment amount (may have discounts)
                        payment_info = payments_info.get(order_id)
                        if payment_info:
                            payment_amount = float(payment_info.get("amount", 0))
                        else:
                            payment_amount = float(order.get("total_amount", 0))
                        if salon_id and payment_amount > 0:
                            points_pending, _ = LoyaltyService.calculate_potential_points(payment_amount, salon_id)
                    except Exception:
                        pass
                
                formatted_order = {
                    **order,
                    "items": order.get("order_items", []),
                    "salon": order.get("salons"),
                    "loyalty_points_earned": points_earned,
                    "loyalty_points_redeemed": points_redeemed,
                    "loyalty_points_pending": points_pending,
                    "loyalty_transactions": loyalty_transactions
                }
                formatted_orders.append(formatted_order)
            
            # Sort by created_at descending (most recent first)
            formatted_orders.sort(
                key=lambda x: x.get("created_at", ""), 
                reverse=(sort_order.lower() == "desc")
            )
            
            # Get total count for pagination (before applying offset/limit)
            count_query = supabase.table("orders")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .neq("order_status", "cart")
            
            if salon_id:
                count_query = count_query.eq("salon_id", salon_id)
            
            if status:
                count_query = count_query.eq("order_status", status)
            
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else len(formatted_orders)
            
            # Apply pagination
            offset = (page - 1) * limit
            paginated_orders = formatted_orders[offset:offset + limit]
            
            return paginated_orders, None, total_count
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], str(e), 0
    
    @staticmethod
    def cancel_order(
        order_id: str,
        user_id: str,
        reason: Optional[str] = None,
        is_owner: bool = False
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Cancel an order (customer or owner, pending or confirmed status).
        Refunds payment and removes loyalty points earned.
        
        Args:
            order_id: Order ID
            user_id: User ID (must be the order owner or salon owner)
            reason: Cancellation reason (required for owner cancellations)
            is_owner: Whether the cancellation is being done by the salon owner
            
        Returns:
            Tuple of (updated_order_dict, error_message)
        """
        try:
            # Get order
            order, error = OrdersService.get_order_details(order_id)
            if error:
                return None, error
            
            # Verify ownership
            if order["user_id"] != user_id:
                return None, "Order does not belong to user"
            
            # Check if order can be cancelled
            current_status = order.get("order_status")
            if current_status not in ["pending", "confirmed"]:
                return None, f"Cannot cancel order with status: {current_status}. Only pending or confirmed orders can be cancelled."
            
            if current_status == "cancelled":
                return None, "Order is already cancelled"
            
            # Find payment for this order
            try:
                payment_response = supabase.table("payments")\
                    .select("id, payment_status, loyalty_points_used, user_id, salon_id")\
                    .eq("order_id", order_id)\
                    .eq("payment_status", "completed")\
                    .maybe_single()\
                    .execute()
                
                payment = None
                if payment_response:
                    if getattr(payment_response, "error", None):
                        ErrorLoggingService.log_exception(
                            Exception(f"Error querying payment for order {order_id}: {payment_response.error.message}"),
                            severity='medium'
                        )
                        # Continue without payment - order might not have payment yet
                    elif hasattr(payment_response, "data") and payment_response.data:
                        payment = payment_response.data
            except Exception as e:
                ErrorLoggingService.log_exception(e, severity='medium')
                # Continue without payment - order might not have payment yet
                payment = None
            
            # Refund payment if exists
            if payment:
                from services.payment_service import PaymentService
                refund_success, refund_error = PaymentService.refund_payment(
                    payment["id"], 
                    reason=f"Order cancelled: {reason or 'No reason provided'}"
                )
                if not refund_success and refund_error:
                    ErrorLoggingService.log_exception(
                        Exception(f"Failed to refund payment {payment['id']}: {refund_error}"),
                        severity='high'
                    )
            
            # Remove loyalty points earned from this order
            if payment:
                # Find loyalty transactions for this payment
                loyalty_trans_response = supabase.table("loyalty_transactions")\
                    .select("id, points, transaction_type")\
                    .eq("payment_id", payment["id"])\
                    .eq("transaction_type", "earned")\
                    .execute()
                
                if loyalty_trans_response and not getattr(loyalty_trans_response, "error", None) and hasattr(loyalty_trans_response, "data") and loyalty_trans_response.data:
                    for trans in loyalty_trans_response.data:
                        points_earned = trans.get("points", 0)
                        if points_earned > 0:
                            # Deduct points from balance
                            from services.loyalty_service import LoyaltyService
                            balance, balance_error = LoyaltyService.get_user_loyalty_balance(
                                user_id, 
                                payment.get("salon_id")
                            )
                            
                            if balance and not balance_error:
                                current_balance = balance.get("points_balance", 0)
                                new_balance = max(0, current_balance - points_earned)
                                
                                # Update balance
                                balance_update_response = supabase.table("loyalty_balances")\
                                    .update({
                                        "points_balance": new_balance,
                                        "lifetime_points_earned": max(0, balance.get("lifetime_points_earned", 0) - points_earned),
                                        "updated_at": datetime.now(timezone.utc).isoformat()
                                    })\
                                    .eq("id", balance["id"])\
                                    .execute()
                                
                                if getattr(balance_update_response, "error", None):
                                    ErrorLoggingService.log_exception(
                                        Exception(f"Failed to update loyalty balance: {balance_update_response.error.message}"),
                                        severity='high'
                                    )
                                    # Continue with transaction creation even if balance update fails
                                
                                # Create reversal transaction
                                trans_insert_response = supabase.table("loyalty_transactions")\
                                    .insert({
                                        "id": str(uuid.uuid4()),
                                        "user_id": user_id,
                                        "salon_id": payment.get("salon_id"),
                                        "transaction_type": "expired",
                                        "points": -points_earned,
                                        "payment_id": payment["id"],
                                        "balance_after": new_balance,
                                        "description": f"Points removed due to order cancellation"
                                    })\
                                    .execute()
                                
                                if getattr(trans_insert_response, "error", None):
                                    ErrorLoggingService.log_exception(
                                        Exception(f"Failed to create loyalty transaction: {trans_insert_response.error.message}"),
                                        severity='high'
                                    )
                                    # Continue with order cancellation even if transaction creation fails
            
            # Update order status to cancelled
            updated_order, error = OrdersService.update_order_status(
                order_id,
                "cancelled",
                None,
                None
            )
            
            if error:
                ErrorLoggingService.log_exception(
                    Exception(f"Failed to update order status to cancelled: {error}"),
                    severity='high'
                )
                return None, error
            
            if not updated_order:
                ErrorLoggingService.log_exception(
                    Exception(f"Order status update returned no data for order_id: {order_id}"),
                    severity='high'
                )
                return None, "Failed to update order status: No order data returned"
            
            # Verify the order status was actually updated
            if updated_order.get("order_status") != "cancelled":
                ErrorLoggingService.log_exception(
                    Exception(f"Order status verification failed: expected 'cancelled', got '{updated_order.get('order_status')}'"),
                    severity='high'
                )
                return None, f"Order status update failed: expected 'cancelled', got '{updated_order.get('order_status')}'"
            
            return updated_order, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    
    @staticmethod
    def get_salon_orders(
        salon_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], Optional[str], int]:
        """
        Get all orders for a salon (for owners).
        
        Args:
            salon_id: Salon ID
            status: Optional status filter
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            Tuple of (list of orders with items and customer info, error_message)
        """
        try:
            # Get total count first (before pagination)
            count_query = supabase.table("orders")\
                .select("id", count="exact")\
                .eq("salon_id", salon_id)\
                .neq("order_status", "cart")
            
            if status:
                count_query = count_query.eq("order_status", status)
            
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else 0
            
            # Get paginated data
            query = supabase.table("orders")\
                .select("*, order_items(*, products(*))")\
                .eq("salon_id", salon_id)\
                .neq("order_status", "cart")\
                .order("created_at", desc=True)\
                .range(offset, offset + limit - 1)
            
            if status:
                query = query.eq("order_status", status)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            orders = response.data or []
            
            # Get unique user IDs and fetch customer info separately
            user_ids = list(set([order.get("user_id") for order in orders if order.get("user_id")]))
            customers = {}
            
            if user_ids:
                try:
                    # Use user_details view which has all the info we need
                    cust_resp = supabase.table("user_details")\
                        .select("id, first_name, last_name, email")\
                        .in_("id", user_ids)\
                        .execute()
                    
                    if cust_resp.data:
                        for row in cust_resp.data:
                            customers[row.get("id")] = {
                                "id": row.get("id"),
                                "first_name": row.get("first_name"),
                                "last_name": row.get("last_name"),
                                "email": row.get("email")
                            }
                except Exception as e:
                    ErrorLoggingService.log_exception(e, severity='low')
                    # Continue without customer info if fetch fails
            
            # Format orders
            formatted_orders = []
            for order in orders:
                user_id = order.get("user_id")
                formatted_order = {
                    **order,
                    "items": order.get("order_items", []),
                    "customer": customers.get(user_id) if user_id else None
                }
                formatted_orders.append(formatted_order)
            
            # Get total count for pagination (before applying offset/limit)
            count_query = supabase.table("orders")\
                .select("id", count="exact")\
                .eq("salon_id", salon_id)\
                .neq("order_status", "cart")
            
            if status:
                count_query = count_query.eq("order_status", status)
            
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else len(formatted_orders)
            
            return formatted_orders, None, total_count
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], str(e), 0
    
    