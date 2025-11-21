from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user
from middleware.notify import notify
from models.salon import SalonRegisterRequest
from services.salon_service import SalonService
from services.visit_history_service import VisitHistoryService
from config import supabase
from flasgger.utils import swag_from

salon_bp = Blueprint("salon_bp", __name__, url_prefix="/api/salons")
salon_bp.strict_slashes = False

@salon_bp.route("", methods=["GET"], strict_slashes=False)
@salon_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required()
def list_salons():
    """
    Public list of verified salons with optional filters.
    """
    try:
        services_param = request.args.get("services")
        service_filters = services_param.split(",") if services_param else []
        data, error = SalonService.list_salons(
            search=request.args.get("q"),
            location=request.args.get("location"),
            service_names=service_filters,
            sort=request.args.get("sort", "top"),
        )
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"salons": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>", methods=["GET"], strict_slashes=False)
@login_required()
def get_salon_detail(salon_id):
    """
    Detailed info for a single salon.
    """
    data, error = SalonService.get_salon_detail(salon_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(data), 200


@salon_bp.route("/<salon_id>/reviews", methods=["GET"], strict_slashes=False)
@login_required()
def get_salon_reviews(salon_id):
    try:
        limit = int(request.args.get("limit", 6))
        data, error = SalonService.list_reviews(salon_id, limit=limit)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"reviews": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#-----------------------------------1. SALONS (salon owners) 

# Salon registration (requires user auth)
#@login_required(['salon_owner'])
@salon_bp.route("/apply", methods=["POST"], strict_slashes=False)
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
@salon_bp.route("/<salon_id>/appeal", methods=["PUT"], strict_slashes=False)
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
@salon_bp.route("/<salon_id>/approve", methods=["PATCH"], strict_slashes=False)
@login_required()
@role_required(['admin'])
@notify(["salon_owner"],event_type="salon_verification",title="Salon Approved",
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
@salon_bp.route("/<salon_id>/reject", methods=["PATCH"], strict_slashes=False)
@login_required()
@role_required(['admin'])
@notify(["salon_owner"],event_type="salon_verification",title="Salon Denied",
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
@salon_bp.route("/pending", methods=["GET"], strict_slashes=False)
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
@salon_bp.route("/<uuid:salon_id>/status-history", methods=["GET"], strict_slashes=False)
@login_required()
@role_required(['admin'])
@swag_from("../docs/salon_status_history.yml")
def get_salon_status_history(salon_id):
    try:
        result = SalonService.get_status_history(salon_id) 
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------3. GET SALON DATA
# Get all services for a salon
@salon_bp.route("/<salon_id>/services", methods=["GET"], strict_slashes=False)
@login_required()
def get_salon_services(salon_id):
    """
    Get all services for a salon.
    """
    try:
        """
        {
            "search": "haircut",
            "filters": {
                "is_active": true, 
                "price_range": [20, 100],
                "tags": ["haircut", "shaving"]
                "duration_range": [30, 60]
        }   }
        """
        try:
            json_data = request.get_json() or {}
        except:
            json_data = {}
        if not json_data.get("filters"):
            json_data["filters"] = {}
        if not json_data.get("search"):
            json_data["search"] = ""
        result = SalonService.get_salon_services(salon_id, json_data)
        if result[0] is None:
            return jsonify({"error": result[1]}), 404
        return jsonify({"services": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@salon_bp.route("/<salon_id>/employees", methods=["GET"], strict_slashes=False)
@login_required()
def get_salon_employees(salon_id):
    """
    Get all service providers (barbers) for a salon.
    """
    try:
        employees, error = SalonService.get_salon_employees(salon_id)
        if error:
            return jsonify({"error": error}), 404
        return jsonify({"employees": employees}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@salon_bp.route("/<salon_id>/tags", methods=["GET"], strict_slashes=False)
@login_required()
def get_salon_tags(salon_id):
    """
    Get all unique service tags for a salon.
    """
    try:
        result, error = SalonService.get_salon_tags(salon_id)
        if error:
            return jsonify({"error1": error}), 404
        return jsonify({"tags": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/customers/<customer_id>/history", methods=["GET"])
@login_required()
@role_required(['salon_owner', 'barber', 'admin'], verify_with_supabase=True)
@swag_from("../docs/salon_customer_history.yml")
def get_salon_customer_history(salon_id: str, customer_id: str):
    """
    Get customer visit history at a specific salon.
    Available to salon owners, barbers, and admins.
    Returns aggregated appointments, spend, images, and notes for the customer at this salon.
    """
    try:
        user = get_current_user()
        user_role = user.get('role')
        user_id = user.get('sub') or user.get('id')
        
        # Verify salon ownership/access for salon_owner and barber
        if user_role == 'salon_owner':
            from middleware.appointments import get_owned_salons
            salons = get_owned_salons()
            owned_salon_ids = [s['id'] for s in salons] if salons else []
            if salon_id not in owned_salon_ids:
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        elif user_role == 'barber':
            # Verify barber belongs to this salon
            from services.auth_service import AuthService
            barber_id, _ = AuthService.get_barber_id(user_id)
            if barber_id:
                barber_response = supabase.table('barbers')\
                    .select('salon_id')\
                    .eq('id', barber_id)\
                    .single()\
                    .execute()
                if barber_response.data and str(barber_response.data.get('salon_id')) != str(salon_id):
                    return jsonify({"error": "Forbidden: You don't work at this salon"}), 403
        
        # Get customer history at this salon
        history, error = VisitHistoryService.get_salon_customer_history(
            salon_id=salon_id,
            customer_id=customer_id
        )
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Customer history retrieved successfully",
            "history": history
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
#---------------------------------------4. SALON EMPLOYEES (service providers/barbers)

# Search 'barbers' to be added to salon
@salon_bp.route("/provider/search", methods=["GET"])
@login_required()
@role_required(['admin', 'salon_owner'])
def search_for_employee():
    """
    Search for service providers (barbers) to add to a salon by email.
    /provider/search?email=whatever
    """
    try:
        query = request.args.get("email", "")
        if not query:
            return jsonify({"error": "Missing search query parameter 'email'"}), 400
        print("Searching for providers with email containing:", query)
        result, error = SalonService.salon_owner_employee_search(query)
        if error:
            return jsonify({"error": error}), 404
        return jsonify({"providers": result}), 200
    except Exception as e:
        return jsonify({"error3": str(e)}), 500

# Add service provider to salon
@salon_bp.route("/provider", methods=["POST"])
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_add_provider.yml")
def add_service_provider():
    """
    Add a new service provider to a salon.
    """
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        salon_id = json_data.get('salon_id')
        user_id = json_data.get('user_id')
        
        
        if not salon_id or not user_id:
            return jsonify({"error": "Missing required fields"}), 400
        bio = json_data.get('bio', '')
        years_experience = json_data.get('years_experience', 0)
        is_active = json_data.get('is_active', True)
        result, error = SalonService.add_service_provider(salon_id, user_id, bio, years_experience, is_active)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
