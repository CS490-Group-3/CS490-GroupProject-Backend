from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware import login_required, role_required, get_current_user
from middleware.notify import notify
from models.services import ServiceCreateRequest, ServiceResponse
from services.salon_service import SalonService
from flasgger.utils import swag_from

services_bp = Blueprint("services_bp", __name__, url_prefix="/api/services")

@services_bp.route("/", methods=["POST"])
@login_required()
@role_required(['salon_owner'])
def create_service():
    """
    Create a new service for a salon.
    """
    try:
        user_id = get_current_user().get('sub')
        print("Current user ID:", user_id)
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        data = ServiceCreateRequest(**json_data)
        if not data:
            return jsonify({"error": "Invalid service data"}), 400
        result, error = SalonService.create_service(
            salon_id=data.salon_id,
            name=data.name,
            description=data.description,
            duration_minutes=data.duration_minutes,
            price=data.price,
            is_active=data.is_active)
        
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"message": "Service created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@services_bp.route("/<service_id>", methods=["GET"])
@login_required()
def get_service(service_id):
    """
    Get service details by ID.
    """
    try:
        result, error = SalonService.get_service(service_id)
        if error:
            return jsonify({"error": error}), 404
        service_response = ServiceResponse(**result)
        return jsonify(service_response.model_dump()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500