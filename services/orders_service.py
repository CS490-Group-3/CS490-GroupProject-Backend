from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
import json
from models.orders import OrderCreateRequest, OrderResponse, OrderUpdateRequest
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
    