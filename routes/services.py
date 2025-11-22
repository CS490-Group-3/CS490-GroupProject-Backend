from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from middleware import login_required, role_required, get_current_user
from models.services import ServiceCreateRequest, ServiceResponse
from services.salon_service import SalonService
from flasgger.utils import swag_from
from config import supabase

services_bp = Blueprint("services_bp", __name__, url_prefix="/api/services")
services_bp.strict_slashes = False

@services_bp.route("", methods=["GET"], strict_slashes=False)
@services_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required()
def list_services_route():
    """
    List services globally or for a specific salon.
    """
    try:
        salon_id = request.args.get("salon_id")
        unique = request.args.get("unique")
        query = supabase.table("services").select("id,salon_id,name,description,duration_minutes,price,is_active")
        if salon_id:
            query = query.eq("salon_id", salon_id)
        response = query.execute()
        rows = response.data or []
        if unique == "name":
            names = sorted({row.get("name") for row in rows if row.get("name")})
            return jsonify({"services": names}), 200
        return jsonify({"services": rows}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@services_bp.route("/", methods=["POST"], strict_slashes=False)
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
    
@services_bp.route("/<service_id>", methods=["GET"], strict_slashes=False)
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

@services_bp.route("/<service_id>", methods=["PATCH"], strict_slashes=False)
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/service_update.yml")
def update_service(service_id):
    """
    Update a service.
    """
    try:
        user_id = get_current_user().get('sub')
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        salon_id = json_data.get('salon_id')
        if not salon_id:
            return jsonify({"error": "Missing salon_id"}), 400
        
        updates = {k: v for k, v in json_data.items() if k != 'salon_id'}
        result, error = SalonService.update_service(service_id, salon_id, user_id, updates)
        
        if error:
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@services_bp.route("/<service_id>", methods=["DELETE"], strict_slashes=False)
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/service_delete.yml")
def delete_service(service_id):
    """
    Delete a service.
    """
    try:
        user_id = get_current_user().get('sub')
        salon_id = request.args.get('salon_id')
        if not salon_id:
            return jsonify({"error": "Missing salon_id query parameter"}), 400
        
        result, error = SalonService.delete_service(service_id, salon_id, user_id)
        
        if error:
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
