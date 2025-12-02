from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
import json
from models.orders import OrderCreateRequest, OrderResponse, OrderUpdateRequest 
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
            response = supabase.table("orders").select("*").eq("user_id", user_id).eq("salon_id", salon_id).eq("order_status", "cart").execute()
            data = response.data
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
    
    
    