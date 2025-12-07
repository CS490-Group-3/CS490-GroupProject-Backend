from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
import json
from models.orders import OrderCreateRequest, OrderResponse, OrderUpdateRequest
from models.products import ProductUpdateRequest
from services.product_service import ProductService 
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
            data = response.data
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
            if not response.data:
                print("Order creation response data is empty:", response)
                return None, "Failed to create order"

            created_order = response.data[0] if response.data else None
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
            response = supabase.table("orders").select("*").eq("user_id", user_id).eq("order_status", "cart")
        
            response = response.eq("salon_id", salon_id).execute()
            
            data = response.data
            print("Active cart query response data:", response)
            if not data:
                return None, "No active cart found for this salon"

            return data[0], None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_all_active_carts(user_id: str) -> Tuple[Optional[list], Optional[str]]:
        """
        Get all active carts (orders with status 'cart') for a user.

        Args:
            user_id: ID of the user

        Returns:
            Tuple containing a list of active cart order dicts or None, and an error message or None
        """
        try:
            response = supabase.table("orders").select("*").eq("user_id", user_id).eq("order_status", "cart").execute()
            data = response.data
            print("All active carts query response data:", response)
            if not data:
                return None, "No active carts found"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_cart_items(order_id: str) -> Tuple[Optional[list], Optional[str]]:
        """
        Get items in a specific cart (order).

        Args:
            order_id: ID of the order (cart)

        Returns:
            Tuple containing a list of order item dicts or None, and an error message or None
        """
        try:
            response = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
            data = response.data
            print("Cart items query response data:", response)
            if not data:
                return None, "No items found in this cart"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def add_item_to_cart(
        user_id: str,
        order_id: str,
        product_id: str,
        quantity: int
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Add an item to a user's cart.

        Args:
            user_id: ID of the user
            order_id: ID of the order (cart)
            product_id: ID of the product to add
            quantity: Quantity of the product to add

        Returns:
            Tuple containing the created order item dict or None, and an error message or None
        """
        try:
            item_data = {
                "order_id": order_id,
                "product_id": product_id,
                "quantity": quantity
            }
            product_data, error = ProductService.get_product(product_id)
            if error:
                return None, error
            order_data, error = OrdersService.get_order_details(order_id)
            if error:
                return None, error
            
            if product_data.get("salon_id") != order_data.get("salon_id"):
                return None, "Product does not belong to the same salon as the order"
            if product_data.get("stock_quantity", 0) < quantity:
                return None, "Insufficient product stock"
            if order_data.get("order_status") != "cart":
                return None, "Cannot add items to a non-cart order"
            item_data["unit_price"] = product_data.get("price")
            response = supabase.table("order_items").insert(item_data).execute()
            if not response.data:
                print("Add item to cart response data is empty:", response)
                return None, "Failed to add item to cart"

            created_item = response.data[0] if response.data else None
            return created_item, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:

            return None, str(e)
    @staticmethod
    def update_cart_item(
        order_id: str,
        item_id: str,
        item_update: Dict
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update an item in the cart.

        Args:
            item_id: ID of the order item to update
            item_update: Dictionary containing fields to update (quantity, unit_price)

        Returns:
            Tuple containing the updated order item dict or None, and an error message or None
        """
        try:
            order_data =OrdersService.get_order_details(order_id)
            if order_data.get("order_status") != "cart":
                return None, "Cannot update item in a non-cart order"
            update_data = {}
            if "quantity" in item_update:
                update_data["quantity"] = item_update["quantity"]
            if "unit_price" in item_update:
                update_data["unit_price"] = item_update["unit_price"]

            response = supabase.table("order_items").update(update_data).eq("id", item_id).execute()
            if not response.data:
                print("Update cart item response data is empty:", response)
                return None, "Failed to update cart item"

            updated_item = response.data[0] if response.data else None
            return updated_item, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def remove_cart_item(
        order_id: str,
        item_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Remove an item from the cart.

        Args:
            item_id: ID of the order item to remove

        Returns:
            Tuple containing a boolean indicating success, and an error message or None
        """
        try:
            order_data = OrdersService.get_order_details(order_id)
            if order_data.get("order_status") != "cart":
                return False, "Cannot remove item from a non-cart order"
            response = supabase.table("order_items").delete().eq("id", item_id).execute()
            if response.status_code != 200:
                print("Remove cart item response indicates failure:", response)
                return False, "Failed to remove cart item"

            return True, None
        except AuthApiError as auth_error:
            return False, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return False, str(e)
    @staticmethod
    def list_orders(
        user_id: str
    ) -> Tuple[Optional[list], Optional[str]]:
        """
        List all orders for a user.

        Args:
            user_id: ID of the user
        Returns:
            Tuple containing a list of order dicts or None, and an error message or None
        """
        try:
            response = supabase.table("orders").select("*").eq("user_id", user_id).execute()
            data = response.data
            if not data:
                return None, "No orders found for this user"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def checkout_cart(
        user_id: str,
        order_id: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Checkout the cart, changing its status from 'cart' to 'checked_out'.

        Args:
            user_id: ID of the user
            order_id: ID of the order (cart)

        Returns:
            Tuple containing the checked out order dict or None, and an error message or None
        """
        try:
            order_data, error = OrdersService.get_order_details(order_id)
            if error:
                return None, error
            if order_data.get("order_status") != "cart":
                return None, "Only carts can be checked out"
            items, error = OrdersService.get_cart_items(order_id)
            if error:
                return None, error
            if not items:
                return None, "Cannot checkout an empty cart"
            
            for item in items:
                product_data, error = ProductService.get_product(item.get("product_id"))
                if error:
                    return None, error
                if product_data.get("stock_quantity", 0) < item.get("quantity", 0):
                    return None, f"Insufficient stock for product ID {item.get('product_id')} {item.get('name','')}"
                new_stock = product_data.get("stock_quantity") - item.get("quantity")
                _, error = ProductService.update_product(item.get("product_id"), ProductUpdateRequest(stock_quantity=new_stock))
                if error:
                    return None, error
                
            update_data = {
                "order_status": "pending"
            }
            response = supabase.table("orders").update(update_data).eq("id", order_id).execute()
            if not response.data:
                print("Checkout cart response data is empty:", response)
                return None, "Failed to checkout cart"

            checked_out_order = response.data[0] if response.data else None
            return checked_out_order, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def cancel_order(user_id: str,
        order_id: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Cancel an order, changing its status to 'canceled'.

        Args:
            user_id: ID of the user
            order_id: ID of the order to cancel
            
        Returns:
            Tuple containing the canceled order dict or None, and an error message or None
        """
        try:
            order_data, error = OrdersService.get_order_details(order_id)
            if error:
                return None, error
            if order_data.get("order_status") not in ["pending", "confirmed", "processing"]:
                return None, "Only pending or checked out orders can be canceled"
            items, error = OrdersService.get_cart_items(order_id)
            if error:
                return None, error
            
            for item in items:
                product_data, error = ProductService.get_product(item.get("product_id"))
                if error:
                    return None, error
                new_stock = product_data.get("stock_quantity") + item.get("quantity")
                _, error = ProductService.update_product(item.get("product_id"), ProductUpdateRequest(stock_quantity=new_stock))
                if error:
                    return None, error
            
            update_data = {
                "order_status": "cancelled"
            }
            response = supabase.table("orders").update(update_data).eq("id", order_id).execute()
            if not response.data:
                print("Cancel order response data is empty:", response)
                return None, "Failed to cancel order"

            canceled_order = response.data[0] if response.data else None
            return canceled_order, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def update_order_status(
        order_id: str,
        new_status: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update the status of an order.

        Args:
            order_id: ID of the order to update
            new_status: New status to set for the order

        Returns:
            Tuple containing the updated order dict or None, and an error message or None
        """
        try:
            if new_status not in ["confirmed", "processing", "shipped", "delivered"]:
                return None, "Invalid order status"
            order_data, error = OrdersService.get_order_details(order_id)
            if error:
                return None, error
    
            if order_data.get("order_status") == "delivered":
                return None, "Cannot update a delivered order"
            elif order_data.get("order_status") == "shipped" and new_status in ["cart", "confirmed", "processing"]:
                return None, "Cannot revert a shipped order to an earlier status"
            elif order_data.get("order_status") == "cart":
                return None, "Only pending carts can be updated via this method"
            elif order_data.get("order_status") == "cancelled":
                return None, "Cannot update a canceled order"
            
            response = supabase.table("orders").update({"order_status": new_status}).eq("id", order_id).execute()
            if not response.data:
                print("Update order status response data is empty:", response)
                return None, "Failed to update order status"

            updated_order = response.data[0] if response.data else None
            return updated_order, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    
    