from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required
from middleware.notify import notify
from models.salon import SalonRegisterRequest
from services.salon_service import SalonService
from flasgger.utils import swag_from

salon_bp = Blueprint("salon_bp", __name__, url_prefix="/api/salons")



#-----------------------------------1. SALONS (salon owners) 

# Salon registration (requires user auth)
#@login_required(['salon_owner'])
@salon_bp.route("/apply", methods=["POST"])
@login_required()
@notify(["admins"],event_type="salon_verification",title="New Salon Application",
message_template="New salon application by {salon_name} submitted.")
@swag_from("../docs/salon_apply.yml") 
def register_salon():
    """
    Allows an authenticated salon_owner to submit a new salon application.
    """
    try:
        if request.content_type and "multipart/form-data" in request.content_type:
            form = request.form.to_dict()
            parsed = SalonRegisterRequest(**form)
            logo_file = request.files.get("logo")
            license_file = request.files.get("license")
        else:

            data = request.get_json() or {}
            parsed = SalonRegisterRequest(**data)
            logo_file = None
            license_file = None

        # Validate contact info
        if not (parsed.phone or parsed.email):
            return jsonify({"error": "At least one contact method (phone or email) is required."}), 400

        # Role check
        if g.user.get("role") != "salon_owner":
            return jsonify({"error": "Only salon owners can register a salon."}), 403

        owner_id = g.user.get("sub")  
        owner_email = g.user.get("email")

        result = SalonService.register_salon(parsed, owner_id, owner_email, logo_file, license_file)

        return jsonify(result), 201

    except ValidationError as e:
        return jsonify({"error": "Validation failed","details": [str(err) for err in e.errors()]}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500




# Salon owner appeals
#@login_required(['salon_owner'])
@salon_bp.route("/<salon_id>/appeal", methods=["PUT"])
@login_required()
@notify(["admins"],event_type="salon_verification",title="Salon Appeal submitted",
message_template="New salon appeal by {salon_name} submitted.")
@swag_from("../docs/salon_appeal.yml")
def appeal_salon(salon_id):
    try:
        user_id = g.user["sub"]
        if request.content_type and "multipart/form-data" in request.content_type:
            body = request.form.to_dict()
            updates = body.get("updates", {})
            if isinstance(updates, str):
                try:
                    updates = json.loads(updates)
                except json.JSONDecodeError:
                    updates = {}
            logo_file = request.files.get("logo")
            license_file = request.files.get("license")
        else:
            body = request.get_json() or {}
            updates = body.get("updates", {})  
            if isinstance(updates, str):
                try:
                    updates = json.loads(updates)
                except json.JSONDecodeError:
                    updates = {}
            logo_file = None
            license_file = None
        result = SalonService.appeal_salon(salon_id, user_id, updates, logo_file, license_file)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500





#----------------------------------------2. ADMIN

# Admin approval (requires admin)
@salon_bp.route("/<salon_id>/approve", methods=["PATCH"])
@login_required()
@role_required(['admin'])
@notify(["owner"],event_type="salon_verification",title="Salon Approved",
message_template="Your Salon has been approved."
)
@swag_from("../docs/salon_approve.yml")
def approve_salon(salon_id):
    try:
        approver_id = g.user["sub"]
        result = SalonService.approve_salon(salon_id, approver_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Admin rejection
@salon_bp.route("/<salon_id>/reject", methods=["PATCH"])
@login_required()
@role_required(['admin'])
@notify(["owner"],event_type="salon_verification",title="Salon Denied",
message_template="Your Salon has been Denied. Reason(s): {reason} "
)
@swag_from("../docs/salon_reject.yml")
def reject_salon(salon_id):
    try:    
        approver_id = g.user["sub"]
        reason = (request.get_json() or {}).get("reason", "No reason provided")
        result = SalonService.reject_salon(salon_id, approver_id, reason)
        return jsonify({"reason": reason, **result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




#view pending applications
@salon_bp.route("/pending", methods=["GET"])
@role_required(['admin'])
@swag_from("../docs/salon_pending.yml")
def get_pending_salons_route():
    try:

        user_role = g.user.get("role")

        if user_role != "admin":
            return jsonify({"error": "Unauthorized"}), 403
        
        data = SalonService().get_pending_salons()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




#get a salons verification history
@salon_bp.route("/<uuid:salon_id>/status-history", methods=["GET"])
@login_required()
@role_required(['admin'])
@swag_from("../docs/salon_status_history.yml")
def get_salon_status_history(salon_id):
    try:
        result = SalonService.get_status_history(salon_id) 
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

