from flask import Blueprint, request, jsonify, g
from pydantic import ValidationError
from middleware.auth import login_required
from models.salon import SalonRegisterRequest
from services.salon_service import SalonService

salon_bp = Blueprint("salon_bp", __name__, url_prefix="/api/salon")



#-----------------------------------1. SALONS (salon owners) 


# Salon registration (requires user auth)
@salon_bp.route("/register", methods=["POST"])
@login_required()
def register_salon():
    """
    Allows an authenticated salon_owner to submit a new salon application.
    """
    try:
        data = request.get_json() or {}
        parsed = SalonRegisterRequest(**data)

        # Validate contact info
        if not (parsed.phone or parsed.email):
            return jsonify({"error": "At least one contact method (phone or email) is required."}), 400

        # Role check
        if g.user.get("role") != "salon_owner":
            return jsonify({"error": "Only salon owners can register a salon."}), 403

        # Authenticated user info
        owner_id = g.user.get("sub")  # JWT subject (user ID)
        owner_email = g.user.get("email")

        # Call service layer (using Pydantic model)
        result = SalonService.register_salon(parsed, owner_id, owner_email)

        return jsonify({"message": "Salon registered successfully", "salon": result}), 201

    except ValidationError as e:
        return jsonify({
            "error": "Validation failed",
            "details": [str(err) for err in e.errors()]
        }), 400

    except Exception as e:
        print("Error in register_salon:", e)
        return jsonify({"error": str(e)}), 500




# Salon owner appeals
@salon_bp.route("/<salon_id>/appeal", methods=["PUT"])
@login_required()
def appeal_salon(salon_id):
    try:
        user_id = g.user["sub"]
        result = SalonService.appeal_salon(salon_id, user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500





#----------------------------------------2. ADMIN

# Admin approval (requires admin)
@salon_bp.route("/<salon_id>/approve", methods=["PUT"])
@login_required()
def approve_salon(salon_id):
    try:
        user_role = g.user.get("role")
        approver_id = g.user["sub"]

        if user_role != "admin":
            return jsonify({"error": "Unauthorized"}), 403

        result = SalonService.approve_salon(salon_id, approver_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Admin rejection
@salon_bp.route("/<salon_id>/reject", methods=["PUT"])
@login_required()
def reject_salon(salon_id):
    try:    
        user_role = g.user.get("role")
        approver_id = g.user["sub"]

        if user_role != "admin":
            return jsonify({"error": "Unauthorized"}), 403

        reason = (request.get_json() or {}).get("reason", "No reason provided")
        result = SalonService.reject_salon(salon_id, approver_id, reason)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



