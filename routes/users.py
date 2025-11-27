"""
User routes for customer-specific endpoints.
"""
from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from services.visit_history_service import VisitHistoryService
from services.customer_image_service import CustomerImageService
from middleware import login_required, get_current_user
from middleware.error_logging import auto_log_errors

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


@users_bp.route('/me/visits', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/users_me_visits.yml")
def get_my_visits():
    """
    Get current user's complete visit history across all salons.
    Returns aggregated appointments, spend, images, and notes.
    
    Query Parameters:
        - salon_id: Optional filter by specific salon
    """
    try:
        user = get_current_user()
        customer_id = user.get('sub') or user.get('id')
        
        if not customer_id:
            return jsonify({"error": "User ID not found"}), 400
        
        # Optional salon filter
        salon_id = request.args.get('salon_id')
        
        history, error = VisitHistoryService.get_customer_visit_history(
            customer_id=customer_id,
            salon_id=salon_id
        )
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Visit history retrieved successfully",
            "history": history
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route('/me/images', methods=['POST'])
@auto_log_errors
@login_required()
@swag_from("../docs/users_upload_image.yml")
def upload_customer_image():
    """
    Upload customer images.
    Customers can upload images to their visit history.
    """
    try:
        user = get_current_user()
        customer_id = user.get('sub') or user.get('id')
        
        if not customer_id:
            return jsonify({"error": "User ID not found"}), 400
        
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files provided"}), 400
        
        salon_id = request.form.get("salon_id")  # Optional
        captions = request.form.getlist("captions") or None
        
        result = CustomerImageService.upload_images(
            user_id=customer_id,
            salon_id=salon_id,
            files=files,
            captions=captions
        )
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@users_bp.route('/me/images', methods=['GET'])
@auto_log_errors
@login_required()
@swag_from("../docs/users_list_images.yml")
def list_customer_images():
    """
    List current user's uploaded images.
    """
    try:
        user = get_current_user()
        customer_id = user.get('sub') or user.get('id')
        
        if not customer_id:
            return jsonify({"error": "User ID not found"}), 400
        
        salon_id = request.args.get('salon_id')  # Optional filter
        
        images = CustomerImageService.list_images(
            customer_id=customer_id,
            salon_id=salon_id
        )
        
        return jsonify({
            "message": "Images retrieved successfully",
            "count": len(images),
            "images": images
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route('/me/images/<image_id>', methods=['DELETE'])
@auto_log_errors
@login_required()
@swag_from("../docs/users_delete_image.yml")
def delete_customer_image(image_id):
    """
    Delete a customer image.
    """
    try:
        user = get_current_user()
        user_id = user.get('sub') or user.get('id')
        
        if not user_id:
            return jsonify({"error": "User ID not found"}), 400
        
        result = CustomerImageService.delete_image(
            user_id=user_id,
            image_id=image_id
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        status_code = 403 if "Forbidden" in str(e) else 400
        return jsonify({"error": str(e)}), status_code

