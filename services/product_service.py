from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
import json
from models.products import ProductCreateRequest, ProductResponse, ProductUpdateRequest, ProductCategoryCreateRequest, ProductCategoryUpdateRequest
class ProductService:
    @staticmethod
    def get_product(
        product_id: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get a product by its ID.

        Args:
            product_id: ID of the product to retrieve

        Returns:
            Tuple containing the product dict or None, and an error message or None
        """
        try:
            response = supabase.table("products").select("*").eq("id", product_id).single().execute()
            data = response.data
            if not data:
                return None, "Product not found"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
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
            if not response.data:
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
        include_inactive: bool = False
    ) -> Tuple[Optional[list], Optional[str]]:
        """
        List products globally or for a specific salon.

        Args:
            salon_id: Optional ID of the salon to filter products
            category_id: Optional ID of the product category to filter products
            include_inactive: If True, includes inactive products (for salon owners)
        Returns:
            Tuple containing a list of products or None, and an error message or None
        """
        try:
            query = supabase.table("products").select("*, product_categories(*)").eq("salon_id", salon_id)
            
            # Only filter by is_active if include_inactive is False (customer view)
            if not include_inactive:
                query = query.eq("is_active", True)

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
    @staticmethod
    def update_product(
        product_id: str,
        data: ProductUpdateRequest
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update an existing product.

        Args:
            product_id: ID of the product to update
            data: Dictionary of fields to update

        Returns:
            Tuple containing the updated product dict or None, and an error message or None
        """
        try:
            response = supabase.table("products").update(data.dict(exclude_unset=True)).eq("id", product_id).execute()
            data = response.data or []
            if not data:
                return None, "Failed to update product"

            updated_product = data[0] if data[0] else None
            return updated_product, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
#----- Category Service -----#
    @staticmethod
    def list_product_categories() -> Tuple[Optional[list], Optional[str]]:
        """
        List all product categories.

        Returns:
            Tuple containing a list of product categories or None, and an error message or None
        """
        try:
            response = supabase.table("product_categories").select("*").execute()
            data = response.data or []
            if not data:
                return None, "Product categories not found"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_category(category_id: str) -> Tuple[Optional[list], Optional[str]]:
        """
        Get a product category by its ID.

        Args:
            category_id: ID of the product category to retrieve

        Returns:
            Tuple containing a list with the category dict or None, and an error message or None
        """
        try:
            response = supabase.table("product_categories").select("*").eq("id", category_id).execute()
            data = response.data or []
            if not data:
                return None, "Product category not found"

            return data, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def create_product_category(
        data: ProductCategoryCreateRequest
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a new product category.

        Args:
            name: Name of the category
            description: Optional description of the category
            parent_category_id: Optional ID of the parent category

        Returns:
            Tuple containing the created category dict or None, and an error message or None
        """
        try:
            check_response = supabase.table("product_categories").select("*").ilike("name", data.name).execute()
            if check_response.data:
                return None, "Product category with this name already exists"
            response = supabase.table("product_categories").insert(data.dict()).execute()
            if not response.data:
                return None, "Failed to create product category"

            created_category = response.data[0] if response.data else None
            return created_category, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def update_product_category(
        category_id: str,
        data: ProductCategoryUpdateRequest
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update an existing product category.

        Args:
            category_id: ID of the category to update
            data: Dictionary of fields to update

        Returns:
            Tuple containing the updated category dict or None, and an error message or None
        """
        try:
            # Check if category exists
            existing = supabase.table("product_categories").select("*").eq("id", category_id).execute()
            if not existing.data:
                return None, "Product category not found"
            
            # If name is being updated, check for duplicates (excluding current category)
            if data.name:
                check_response = supabase.table("product_categories").select("*").ilike("name", data.name).neq("id", category_id).execute()
                if check_response.data:
                    return None, "Product category with this name already exists"
            
            # Update the category
            update_dict = data.dict(exclude_unset=True, exclude={"id"})
            if not update_dict:
                return None, "No fields to update"
            
            response = supabase.table("product_categories").update(update_dict).eq("id", category_id).execute()
            if not response.data:
                return None, "Failed to update product category"

            updated_category = response.data[0] if response.data else None
            return updated_category, None
        except AuthApiError as auth_error:
            return None, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return None, str(e)
    @staticmethod
    def delete_product_category(
        category_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Delete a product category.

        Args:
            category_id: ID of the category to delete

        Returns:
            Tuple containing success boolean and an error message or None
        """
        try:
            # Check if category exists
            existing = supabase.table("product_categories").select("*").eq("id", category_id).execute()
            if not existing.data:
                return False, "Product category not found"
            
            # Check if any products are using this category
            products_check = supabase.table("products").select("id").eq("category_id", category_id).limit(1).execute()
            if products_check.data and len(products_check.data) > 0:
                return False, "Cannot delete category: products are still using this category"
            
            # Check if any categories have this as parent
            children_check = supabase.table("product_categories").select("id").eq("parent_category_id", category_id).limit(1).execute()
            if children_check.data and len(children_check.data) > 0:
                return False, "Cannot delete category: it has child categories. Please delete or reassign child categories first"
            
            # Delete the category
            response = supabase.table("product_categories").delete().eq("id", category_id).execute()
            return True, None
        except AuthApiError as auth_error:
            return False, f"Authentication error: {str(auth_error)}"
        except Exception as e:
            return False, str(e)