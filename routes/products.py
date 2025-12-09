from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user
from werkzeug.utils import secure_filename
from models.products import ProductCreateRequest, ProductResponse, ProductUpdateRequest, ProductCategoryCreateRequest, ProductCategoryResponse, ProductCategoryUpdateRequest
from services.product_service import ProductService
from services.salon_service import SalonService
from flasgger.utils import swag_from
from services.upload_file import StorageService


products_bp = Blueprint("products_bp", __name__, url_prefix="/api/products")

@products_bp.route("", methods=["GET"])
@login_required()
@swag_from("../docs/products_list_products.yml")
def list_products_route():
    """
    List products globally or for a specific salon.
    {
        salon_id: UUID,
        category_id: list(UUID) (optional)
        example:/api/products?salon_id=<salon_id>&category_id=<category_id1>&category_id=<category_id2>
    }
    """
    try:
        
        salon_id = request.args.get("salon_id", default=None)
        category_ids = request.args.getlist("category_id")
        print("category_ids:", category_ids)
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
@swag_from("../docs/products_create_product.yml")
def create_product_route():
    """
    Create a new product for a salon.
    """
    try:
        user_id = get_current_user().get('sub')
        print("Current user ID:", user_id)
        salon_id = SalonService.get_owned_salon(user_id)[0].get("id")
        print("Owned salon ID:", salon_id)
        if not salon_id:
            return jsonify({"error": "User does not own a salon"}), 403
        
        json_data = request.form.to_dict()
        print(json_data)
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        json_data["salon_id"] = salon_id
        file = request.files.get("file")
        if file:
            original_ext = file.filename.rsplit(".", 1)[-1]
            name = json_data.get("name", file.filename.rsplit(".", 1)[0])
            file.filename = secure_filename(f"{name}.{original_ext}")
            upload_url = StorageService.upload_file(file, salon_id, "product")
            json_data["image_url"] = upload_url['filepath']
            
        data = ProductCreateRequest(**json_data)
        if not data:
            return jsonify({"error": "Invalid product data"}), 400
        result, error = ProductService.create_product(data)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"message": "Product created successfully", "product": ProductResponse.model_validate(result).model_dump()}), 201
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@products_bp.route("/<product_id>", methods=["GET"])
@login_required()
@swag_from("../docs/products_get.yml")
def get_product_route(product_id):
    """
    Get a product by ID.
    """
    try:
        result, error = ProductService.get_product(product_id)
        if error:
            return jsonify({"error": error}), 404
        return jsonify({"product": ProductResponse.model_validate(result).model_dump()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@products_bp.route("/<product_id>", methods=["PATCH"])
@login_required()
@role_required(['salon_owner'])
@swag_from("../docs/products_update.yml")
def update_product_route(product_id):
    """
    Update a product.
    """
    try:
        user_id = get_current_user().get('sub')
        salon_id = SalonService.get_owned_salon(user_id)[0].get("id")
        print("Owned salon ID:", salon_id)
        if not salon_id:
            return jsonify({"error": "User does not own a salon"}), 403
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        print("Update data:", json_data)
        data = ProductUpdateRequest(**json_data)
        if not data:
            return jsonify({"error": "Invalid product data"}), 400
        result, error = ProductService.update_product(product_id, data)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"message": "Product updated successfully", "product": ProductResponse.model_validate(result).model_dump()}), 200
    except ValidationError as ve:
        return jsonify({"error": ve.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#---- Category Routes ----#
@products_bp.route("/categories", methods=["GET"])
@login_required()
@swag_from("../docs/products_categories_list.yml")
def list_product_categories_route():
    """
    List all product categories.
    """
    try:
        categories, error = ProductService.list_product_categories()
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"categories": categories}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route("/categories", methods=["POST"])
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/products_categories_create.yml")
def create_product_category_route():
    """
    Create a new product category.
    {
        name: str,
        description: str (optional),
        parent_category_id: str (optional)
    }
    """
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        data = ProductCategoryCreateRequest(**json_data)
        if not data:
            return jsonify({"error": "Invalid category data"}), 400
        
        category, error = ProductService.create_product_category(data)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"message": "Category created successfully", "category": category}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@products_bp.route("/categories/<category_id>", methods=["GET"])
@login_required()
@swag_from("../docs/products_categories_get.yml")
def get_product_category_route(category_id):
    """
    Get a product category by ID.
    """
    try:
        category, error = ProductService.get_category(category_id)
        if error:
            return jsonify({"error": error}), 400
        if not category:
            return jsonify({"error": "Category not found"}), 404
        return jsonify({"data": category[0]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
