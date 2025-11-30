from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user

from models.products import ProductCreateRequest, ProductResponse
from services.product_service import ProductService
from flasgger.utils import swag_from


products_bp = Blueprint("products_bp", __name__, url_prefix="/api/products")

@products_bp.route("", methods=["GET"])
@login_required()
def list_products_route():
    """
    List products globally or for a specific salon.
    {
        salon_id: UUID,
        category_id: list(UUID) (optional)
    }
    """
    try:
        data = request.get_json() or {}
        salon_id = data.get("salon_id")
        category_ids = data.get("category_id", [])
        
        if not salon_id:
            return jsonify({"error": "Missing 'salon_id'"}), 400
        products = ProductService.list_products(salon_id, category_ids)
        if products[0] is None:
            return jsonify({"message": "No products found"}), 200
        products_response = [ProductResponse.model_validate(p).model_dump() for p in products[0]]
        return jsonify({"products": products_response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@products_bp.route("/", methods=["POST"])
@login_required()
@role_required(['salon_owner'])
def create_product_route():
    """
    Create a new product for a salon.
    """
    try:
        user_id = get_current_user().get('sub')
        print("Current user ID:", user_id)
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        data = ProductCreateRequest(**json_data)
        if not data:
            return jsonify({"error": "Invalid product data"}), 400
        result, error = ProductService.create_product(data)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"message": "Product created successfully", "product": result}), 201
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
