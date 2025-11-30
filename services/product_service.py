from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
import json
import model.products
from models.products import ProductCreateRequest, ProductResponse
class ProductService:
    @staticmethod
    def create_product(
        data: ProductCreateRequest
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a new product for a salon.

        Args:
            salon_id: ID of the salon offering the product
            category_id: Optional ID of the product category
            name: Name of the product
            description: Optional description of the product
            price: Price of the product as a string
            stock_quantity: Optional stock quantity
            image_url: Optional URL of the product image
            is_active: Whether the product is active

        Returns:
            Tuple containing the created product dict or None, and an error message or None
        """
        try:
            
            response = supabase.table("products").insert(data.dict()).execute()
            if not response or response.error:
                return None, "Failed to create product"

            created_product = response.data[0] if response.data else None
            return created_product, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def list_products(
        salon_id: Optional[str] = None,
        category_ids: Optional[list] = None,
    ) -> Tuple[Optional[list], Optional[str]]:
        """
        List products globally or for a specific salon.

        Args:
            salon_id: Optional ID of the salon to filter products
            category_id: Optional ID of the product category to filter products
            is_active: Optional filter for active/inactive products
        Returns:
            Tuple containing a list of products or None, and an error message or None
        """
        try:
            query = supabase.table("products").select("*, product_categories(*)").eq("salon_id", salon_id).eq("is_active", True)

            response= query.execute()
            data = response.data or []
            print(data)
            if not data:
                return None, "Products not found"
            
            if category_ids and len(category_ids) > 0:
                filtered = [
                    p for p in data
                    if p["category_id"] in category_ids
                    or (p.get("product_categories") and p["product_categories"].get("parent_category_id") in category_ids)
                ]
                return filtered, None if filtered else None, "Products not found"
            return data, None

        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)