from flask import Blueprint, request, jsonify, g, json
from pydantic import ValidationError
from middleware.auth import login_required, role_required, get_current_user
from middleware.notify import notify
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from middleware.error_logging import auto_log_errors
from models.salon import SalonRegisterRequest
from services.salon_service import SalonService
from services.promotion_service import PromotionService
from services.visit_history_service import VisitHistoryService
from services.auth_service import AuthService
from services.schedule_service import ScheduleService
from config import supabase
from flasgger.utils import swag_from
from datetime import time

salon_bp = Blueprint("salon_bp", __name__, url_prefix="/api/salons")
salon_bp.strict_slashes = False

@salon_bp.route("", methods=["GET"], strict_slashes=False)
@salon_bp.route("/", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_list.yml")
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
            log_service_error(error)
            return jsonify({"error": error}), 400
        return jsonify({"salons": data}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_detail.yml")
def get_salon_detail(salon_id):
    """
    Detailed info for a single salon.
    """
    data, error = SalonService.get_salon_detail(salon_id)
    if error:
        log_service_error(error)
        return jsonify({"error": error}), 404
    return jsonify(data), 200


@salon_bp.route("/<salon_id>/reviews", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_reviews.yml")
def get_salon_reviews(salon_id):
    try:
        limit = int(request.args.get("limit", 6))
        data, error = SalonService.list_reviews(salon_id, limit=limit)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        return jsonify({"reviews": data}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/", methods=["GET"])
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


@salon_bp.route("/<salon_id>", methods=["GET"])
@login_required()
def get_salon_detail(salon_id):
    """
    Detailed info for a single salon.
    """
    data, error = SalonService.get_salon_detail(salon_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(data), 200


@salon_bp.route("/<salon_id>/reviews", methods=["GET"])
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
#@role_required(['salon_owner'])
@salon_bp.route("/apply", methods=["POST"], strict_slashes=False)
@auto_log_errors
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
    except ValueError as e:
        print(f"[register_salon] ValueError: {e}")
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




# Salon owner appeals
#@role_required(['salon_owner'])
@salon_bp.route("/<salon_id>/appeal", methods=["PUT"], strict_slashes=False)
@auto_log_errors
@login_required()
@notify(["admins"],event_type="salon_verification",title="Salon Appeal submitted",
message_template="New salon appeal by {salon_name} submitted.")
@swag_from("../docs/salon_appeal.yml")
def appeal_salon(salon_id):
    try:
        user_id = g.user["sub"]
        if request.content_type and "multipart/form-data" in request.content_type:
            # Extract form fields directly (same structure as register_salon)
            form = request.form.to_dict()
            updates = {
                k: v for k, v in form.items() 
                if k in ["name", "description", "address", "city", "state", "zip_code", "phone", "email", "timezone"]
            }
            logo_file = request.files.get("logo")
            license_file = request.files.get("license")
        else:
            # JSON body - accept fields directly or nested in "updates"
            body = request.get_json() or {}
            if "updates" in body:
                updates = body["updates"]
            else:
                # Allow fields at top level for consistency
                updates = {
                    k: v for k, v in body.items() 
                    if k in ["name", "description", "address", "city", "state", "zip_code", "phone", "email", "timezone"]
                }
            logo_file = None
            license_file = None
        result = SalonService.appeal_salon(salon_id, user_id, updates, logo_file, license_file)
        # appeal_salon returns either a dict or a tuple (dict, status_code)
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1] if len(result) > 1 else 200
        return jsonify(result), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>/application", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner'])
@swag_from("../docs/salon_update_pending.yml")
def update_pending_application(salon_id):
    """
    Update a pending salon application (owner only).
    """
    try:
        user = get_current_user()
        owner_id = user.get("sub")

        if request.content_type and "multipart/form-data" in request.content_type:
            body = request.form.to_dict()
            logo_file = request.files.get("logo")
            license_file = request.files.get("license")
        else:
            body = request.get_json() or {}
            logo_file = None
            license_file = None

        updates = body.copy()

        result, status_code = SalonService.update_pending_salon(
            salon_id,
            owner_id,
            updates=updates,
            logo_file=logo_file,
            license_file=license_file,
        )
        return jsonify(result), status_code
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500



@salon_bp.route('/<uuid:salon_id>/promotions', methods=['POST'])
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_promotions.yml")
def create_promotional_offer(salon_id):
    """
    Create a promotional offer for a salon (owner or admin).
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    try:
        result = PromotionService.create_offer(salon_id, data)
        return jsonify(result), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




#----------------------------------------2. ADMIN

# Admin approval (requires admin)
@salon_bp.route("/<salon_id>/approve", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
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
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


# Admin rejection
@salon_bp.route("/<salon_id>/reject", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
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
        log_route_error(e)
        return jsonify({"error": str(e)}), 500




#view pending applications
@salon_bp.route("/pending", methods=["GET"], strict_slashes=False)
@auto_log_errors
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
        log_route_error(e)
        return jsonify({"error": str(e)}), 500




#get a salons verification history
@salon_bp.route("/<uuid:salon_id>/status-history", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['admin'])
@swag_from("../docs/salon_status_history.yml")
def get_salon_status_history(salon_id):
    try:
        result = SalonService.get_status_history(salon_id) 
        return jsonify(result), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/mine", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_mine.yml")
def get_my_salon():
    """
    Fetch the current owner's salon (single).
    """
    try:
        user = get_current_user()
        owner_id = user.get("sub")
        if not owner_id:
            return jsonify({"error": "User ID missing"}), 400

        salon, error = SalonService.get_owned_salon(owner_id)
        if error:
            return jsonify({"error": error}), 500
        return jsonify({"salon": salon}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/hours", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_hours_get.yml")
def get_salon_hours(salon_id):
    """
    Get weekly hours for a salon (owner/admin only).
    """
    try:
        user = get_current_user()
        role = user.get("role")
        user_id = user.get("sub")

        salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
        if getattr(salon_resp, "error", None) or not salon_resp.data:
            return jsonify({"error": "Salon not found"}), 404

        if role == "salon_owner" and str(salon_resp.data.get("owner_id")) != str(user_id):
            return jsonify({"error": "Forbidden: You don't own this salon"}), 403

        hours, error = SalonService.get_salon_hours(salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        return jsonify({"hours": hours}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>/hours", methods=["PUT"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_hours_update.yml")
def update_salon_hours(salon_id):
    """
    Create or replace weekly hours for a salon.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")

        salon_resp = supabase.table("salons").select("owner_id,name").eq("id", salon_id).single().execute()
        if getattr(salon_resp, "error", None) or not salon_resp.data:
            return jsonify({"error": "Salon not found"}), 404

        owner_id = salon_resp.data.get("owner_id")
        if role == "salon_owner" and str(owner_id) != str(user_id):
            return jsonify({"error": "Forbidden: You don't own this salon"}), 403

        body = request.get_json() or {}
        hours = body.get("hours")
        if hours is None:
            return jsonify({"error": "Missing 'hours' in request body"}), 400

        result, error = SalonService.upsert_salon_hours(salon_id, hours)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400

        return jsonify({"message": "Salon hours saved", "hours": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/hours/<int:day_of_week>", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_hours_patch.yml")
def update_salon_hour_day(salon_id, day_of_week):
    """
    Update or create hours for a single day.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")

        salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
        if getattr(salon_resp, "error", None) or not salon_resp.data:
            return jsonify({"error": "Salon not found"}), 404
        if role == "salon_owner" and str(salon_resp.data.get("owner_id")) != str(user_id):
            return jsonify({"error": "Forbidden: You don't own this salon"}), 403

        body = request.get_json() or {}
        result, error = SalonService.upsert_salon_hour_day(salon_id, day_of_week, body)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        return jsonify({"message": "Salon day hours saved", "hours": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>/hours/<int:day_of_week>", methods=["DELETE"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_hours_delete.yml")
def delete_salon_hour_day(salon_id, day_of_week):
    """
    Delete hours for a single day.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")

        salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
        if getattr(salon_resp, "error", None) or not salon_resp.data:
            return jsonify({"error": "Salon not found"}), 404
        if role == "salon_owner" and str(salon_resp.data.get("owner_id")) != str(user_id):
            return jsonify({"error": "Forbidden: You don't own this salon"}), 403

        _, error = SalonService.delete_salon_hour_day(salon_id, day_of_week)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        return jsonify({"message": "Salon day hours deleted"}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

# ---------------------------------------3. GET SALON DATA
# Get all services for a salon
@salon_bp.route("/<salon_id>/services", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_services.yml")
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
        if isinstance(result, tuple):
            services, error = result
            if error:
                return jsonify({"error": error}), 404
            return jsonify({"services": services}), 200
        # If result is not a tuple, it's the services list directly
        return jsonify({"services": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
    
@salon_bp.route("/<salon_id>/employees", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_employees.yml")
def get_salon_employees(salon_id):
    """
    Get all service providers (barbers) for a salon.
    """
    try:
        employees, error = SalonService.get_salon_employees(salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 404
        return jsonify({"employees": employees}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
    
@salon_bp.route("/<salon_id>/tags", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@swag_from("../docs/salon_tags.yml")
def get_salon_tags(salon_id):
    """
    Get all unique service tags for a salon.
    """
    try:
        result, error = SalonService.get_salon_tags(salon_id)
        if error:
            log_service_error(error)
            return jsonify({"error1": error}), 404
        return jsonify({"tags": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/customers/<customer_id>/history", methods=["GET"])
@auto_log_errors
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
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
#---------------------------------------4. SALON EMPLOYEES (service providers/barbers)

# Search 'barbers' to be added to salon
@salon_bp.route("/provider/search", methods=["GET"])
@auto_log_errors
@login_required()
@role_required(['admin', 'salon_owner'])
@swag_from("../docs/salon_provider_search.yml")
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
            log_service_error(error)
            return jsonify({"error": error}), 404
        return jsonify({"providers": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error3": str(e)}), 500

# Add service provider to salon
@salon_bp.route("/provider", methods=["POST"])
@auto_log_errors
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
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

#---------------------------------------5. BARBER SERVICES (assign services to barbers)

@salon_bp.route("/<salon_id>/barbers/<barber_id>/services", methods=["POST"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_barber_service_add.yml")
def add_service_to_barber(salon_id, barber_id):
    """
    Add a service to a barber.
    Validates salon ownership, barber belongs to salon, and service belongs to salon.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        service_id = json_data.get('service_id')
        if not service_id:
            return jsonify({"error": "Missing required field: service_id"}), 400
        
        result, error = SalonService.add_service_to_barber(salon_id, barber_id, service_id, user_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>/barbers/<barber_id>/services/<service_id>", methods=["DELETE"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_barber_service_remove.yml")
def remove_service_from_barber(salon_id, barber_id, service_id):
    """
    Remove a service from a barber.
    Validates salon ownership, barber belongs to salon, and service belongs to salon.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        result, error = SalonService.remove_service_from_barber(salon_id, barber_id, service_id, user_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@salon_bp.route("/<salon_id>/barbers/<barber_id>/services", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'barber', 'admin'])
@swag_from("../docs/salon_barber_services_list.yml")
def get_barber_services(salon_id, barber_id):
    """
    Get all services assigned to a barber.
    Validates salon ownership (for salon_owner) or barber belongs to salon (for barber).
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        user_role = user.get("role")
        
        # For salon_owner, verify ownership
        if user_role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        # For barber, verify they belong to this salon and are viewing their own services
        elif user_role == "barber":
            barber_id_from_user, _ = AuthService.get_barber_id(user_id)
            if not barber_id_from_user:
                return jsonify({"error": "Barber profile not found"}), 404
            
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id_from_user).single().execute()
            if not barber_resp.data:
                return jsonify({"error": "Barber not found"}), 404
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return jsonify({"error": "Forbidden: You don't belong to this salon"}), 403
            
            # Verify the requested barber_id matches the authenticated barber
            if str(barber_id_from_user) != str(barber_id):
                return jsonify({"error": "Forbidden: You can only view your own services"}), 403
        
        # For salon_owner, use user_id as owner_id. For admin/barber, pass None (no ownership check needed)
        owner_id = user_id if user_role == "salon_owner" else None
        
        services, error = SalonService.get_barber_services(salon_id, barber_id, owner_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"services": services}), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

#---------------------------------------6. SALON MANAGEMENT (verified salons)

@salon_bp.route("/<salon_id>", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_update.yml")
def update_verified_salon(salon_id):
    """
    Update a verified salon's details.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        if request.content_type and "multipart/form-data" in request.content_type:
            body = request.form.to_dict()
            logo_file = request.files.get("logo")
        else:
            body = request.get_json() or {}
            logo_file = None
        
        updates = body.copy()
        
        result, error = SalonService.update_verified_salon(
            salon_id,
            user_id,
            updates=updates,
            logo_file=logo_file
        )
        
        if error:
            log_service_error(error, severity='medium' if "Forbidden" in error else 'high')
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify(result), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/employees/<barber_id>", methods=["DELETE"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_employee_remove.yml")
def remove_employee(salon_id, barber_id):
    """
    Remove an employee (barber) from a salon.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        result, error = SalonService.remove_employee(salon_id, barber_id, user_id)
        
        if error:
            log_service_error(error, severity='medium' if "Forbidden" in error else 'high')
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify(result), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/customers", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_customers.yml")
def get_salon_customers(salon_id):
    """
    Get all customers for a salon, sorted by visit count.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        customers, error = SalonService.get_salon_customers(salon_id, user_id)
        
        if error:
            log_service_error(error, severity='medium' if "Forbidden" in error else 'high')
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify({"customers": customers}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/employees/<barber_id>", methods=["PATCH"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_employee_update.yml")
def update_employee(salon_id, barber_id):
    """
    Update an employee's (barber's) information (bio, years_experience, is_active).
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
        
        json_data = request.get_json() or {}
        result, error = SalonService.update_employee(salon_id, barber_id, user_id, json_data)
        
        if error:
            log_service_error(error, severity='medium' if "Forbidden" in error else 'high')
            status_code = 403 if "Forbidden" in error else 404
            return jsonify({"error": error}), status_code
        
        return jsonify(result), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/employees/<barber_id>/availability", methods=["GET"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_employee_availability_get.yml")
def get_employee_availability(salon_id, barber_id):
    """
    Get a barber's availability. Salon owners can view their employees' schedules.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return jsonify({"error": "Barber not found"}), 404
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return jsonify({"error": "Barber does not belong to this salon"}), 403
        
        result, error = ScheduleService.get_availability(barber_id=barber_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"availability": result}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500

@salon_bp.route("/<salon_id>/employees/<barber_id>/availability", methods=["POST", "PATCH"], strict_slashes=False)
@auto_log_errors
@login_required()
@role_required(['salon_owner', 'admin'])
@swag_from("../docs/salon_employee_availability_set.yml")
def set_employee_availability(salon_id, barber_id):
    """
    Set or update a barber's availability. Salon owners can set their employees' schedules.
    Availability must be within salon hours.
    """
    try:
        user = get_current_user()
        user_id = user.get("sub")
        role = user.get("role")
        
        # Verify salon ownership for salon_owner
        if role == "salon_owner":
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return jsonify({"error": "Salon not found"}), 404
            
            if str(salon_resp.data.get("owner_id")) != str(user_id):
                return jsonify({"error": "Forbidden: You don't own this salon"}), 403
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return jsonify({"error": "Barber not found"}), 404
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return jsonify({"error": "Barber does not belong to this salon"}), 403
        
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        availabilities = json_data.get('availability')
        if not availabilities:
            return jsonify({"error": "Missing 'availability' in request body"}), 400
        
        from models.schedule import BarberAvailabilityCreateRequest, BarberAvailabilityUpdateRequest
        
        if request.method == "POST":
            # Create new availability
            for availability in availabilities:
                data = BarberAvailabilityCreateRequest(**availability)
                result, error = ScheduleService.create_availability(
                    barber_id=barber_id,
                    day_of_week=data.day_of_week,
                    start_time=data.start_time,
                    end_time=data.end_time,
                    is_active=data.is_active
                )
                if error:
                    return jsonify({"error": error}), 400
            return jsonify({"message": "Availability created successfully"}), 201
        else:
            # Update existing availability
            for availability in availabilities:
                data = BarberAvailabilityUpdateRequest(**availability)
                if isinstance(data.start_time, time):
                    start_time = data.start_time.strftime("%H:%M:%S")
                else:
                    start_time = data.start_time
                if isinstance(data.end_time, time):
                    end_time = data.end_time.strftime("%H:%M:%S")
                else:
                    end_time = data.end_time
                update = {
                    "day_of_week": data.day_of_week,
                    "start_time": start_time,
                    "end_time": end_time,
                    "is_active": data.is_active
                }
                result, error = ScheduleService.update_availability(
                    availability_id=data.id,
                    update_data=update
                )
                if error:
                    return jsonify({"error": error}), 400
            return jsonify({"message": "Availability updated successfully"}), 200
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
