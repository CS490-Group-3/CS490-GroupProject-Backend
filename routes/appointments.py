from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from pydantic import ValidationError
from models.appointment import (
    AppointmentCreateRequest,  
    AppointmentUpdateRequest
)
from services.appointment_service import AppointmentService
from services.auth_service import AuthService
from services.notification_service import NotificationService
from middleware import login_required, role_required, get_current_user, get_owned_salons
from middleware.notify import notify

appointments_bp = Blueprint('appointments', __name__, url_prefix='/api/appointments')
appointments_bp.strict_slashes = False

# ---------- endpoints ----------

# availability helper
@appointments_bp.route("/availability", methods=["GET"])
@login_required()
@role_required(['customer', 'admin', 'salon_owner', 'barber'])
def get_availability_slots():
    salon_id = request.args.get("salon_id")
    barber_id = request.args.get("barber_id")
    service_id = request.args.get("service_id")
    date_str = request.args.get("date")
    if not all([salon_id, barber_id, service_id, date_str]):
        return jsonify({"error": "salon_id, barber_id, service_id, and date are required"}), 400
    slots, error = AppointmentService.get_available_slots(salon_id, barber_id, service_id, date_str)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"slots": slots}), 200

# list apptmts: GET / 
@appointments_bp.route('', methods=['GET'])
@appointments_bp.route('/', methods=['GET'])
@login_required()
@role_required(['customer', 'admin', 'salon_owner', 'barber'])
@swag_from("../docs/list_appointments.yml")
def list_appointments():
    """
    List past and/or present appointments for the current user.
    Accepts ?when=upcoming|past|all (default: all)
    Filters:
      ?when=upcoming|past|all
      ?status=scheduled,cancelled
      ?page=1
      ?limit=20
    Admins may also pass:
      ?salon_id=...
      ?barber_id=...
      ?customer_id=...
    """
    try:
        user = get_current_user()
        print("Current user:", user)
        user_id = user.get('sub')
        user_role = user.get('role')

        # query params
        when = (request.args.get("when") or "all").lower()
        status_param = request.args.get("status")
        status = status_param.split(",") if status_param else None
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))

        salon_id = request.args.get("salon_id")
        barber_id = request.args.get("barber_id")
        customer_id = request.args.get("customer_id")
        
        #role-based lookup
        if user_role == 'customer':
            # Fetch appointments for customer
            appointments, error = AppointmentService.get_appointments_by_customer(user_id, when, status, page, limit)
        elif user_role == 'salon_owner':
            # Fetch all appointments
            salons = get_owned_salons()
            salon_ids = [salon['id'] for salon in salons]
            appointments, error = AppointmentService.get_all_salon_appointments(salon_ids, when, status, page, limit)
        elif user_role == 'barber':
            # fetch appointments for barber
            # must first lookup barber ID with user ID
            barber_id, barber_error = AuthService.get_barber_id(user_id)
            if not barber_id:
                message = barber_error or "No barber profile found for user"
                return jsonify({"error": message}), 404
            appointments, error = AppointmentService.get_appointments_by_barber(barber_id, when, status, page, limit)
        elif user_role == "admin":
            # fetch appointments according to filters
            appointments, error = AppointmentService.get_admin_filtered(salon_id, barber_id, customer_id, when, status, page, limit)
        else:
            return jsonify({"error": "Unauthorized role"}), 403
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "when": when,
            "status_filter": status or "all",
            "page": page,
            "limit": limit,
            "count": len(appointments),
            "appointments": appointments
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# create: POST /
@appointments_bp.route("", methods=["POST"])
@appointments_bp.route("/", methods=["POST"])
@login_required()
@role_required(["customer", "salon_owner", "barber", "admin"])
@swag_from("../docs/create_appointment.yml")
def create_appointment():
    """Create a new appointment (booking)."""
    try:
        user = get_current_user()
        payload = request.get_json() or {}
        req = AppointmentCreateRequest(**payload)
        created, error = AppointmentService.create_appointment(req.model_dump(), user=user)
        if error:
            return jsonify({"error": error}), 400
        return jsonify(created), 201
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# update: PATCH /
@appointments_bp.route('', methods=['PATCH'])
@appointments_bp.route('/', methods=['PATCH'])
@login_required()
@role_required(['customer', 'admin', 'salon_owner', 'barber'])
@notify(
    recipients=["barber", "user"], 
    event_type="appointment_confirmation",
    title="Appointment Updated",
    message_template="The appointment at {salon_name} for {service_name} has been updated.",
    schedule_func=NotificationService.schedule_upcoming_appointment, 
    related_key="appointment_id"
)#notify user and barber upon update 
@swag_from("../docs/update_appointment.yml")
def update_appointment():
    """
    Generic update (respects service-size overlap checks).
    """
    try:
        json_data = request.get_json() or {}
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        appointment_id = json_data.get('id')
        if not appointment_id:
            return jsonify({"error": "Missing appointment ID"}), 400
        
        json_data.pop('id', None)
        
        user = get_current_user()
        req = AppointmentUpdateRequest(**json_data)
        
        result, error = AppointmentService.update_appointment(appointment_id, req.model_dump(exclude_unset=True), user=user)
        
        if error == "Forbidden":
            return jsonify({"error": error}), 403
        elif error:
            return jsonify({"error": error}), 400
    
        return jsonify({
            "message": "Appointment updated successfully.",
            "appointment": result
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# PATCH /<appointment_id>/cancel
@appointments_bp.route("/<appointment_id>/cancel", methods=["PATCH"])
@login_required()
@role_required(["customer", "salon_owner", "barber", "admin"])
@swag_from("../docs/cancel_appointment.yml")
def cancel_appointment(appointment_id):
    """
    Cancel an appointment.
    """
    try:
        user = get_current_user()
        reason = (request.get_json() or {}).get("reason")
        data, error = AppointmentService.cancel_appointment(appointment_id, reason=reason, user=user)
        if error == "Forbidden":
            return jsonify({"error": error}), 403
        elif error:
            return jsonify({"error": error}), 400
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# PATCH /<appointment_id>/reschedule
@appointments_bp.route("/<appointment_id>/reschedule", methods=["PATCH"])
@login_required()
@role_required(["customer", "salon_owner", "barber", "admin"])
@swag_from("../docs/reschedule_appointment.yml")
def reschedule_appointment(appointment_id):
    """
    Reschedule an appointment.
    """
    try:
        user = get_current_user()
        body = request.get_json() or {}
        new_start_at = body.get("start_at")
        new_end_at   = body.get("end_at")  # optional
        salon_id     = body.get("salon_id")
        barber_id    = body.get("barber_id")

        if not (new_start_at and salon_id and barber_id):
            return jsonify({"error": "start_at, salon_id, and barber_id are required"}), 400

        updated, error = AppointmentService.reschedule_appointment(
            appointment_id, salon_id, barber_id, new_start_at, new_end_at, user=user
        )
        if error == "Forbidden":
            return jsonify({"error": error}), 403
        elif error:
            return jsonify({"error": error}), 400
        return jsonify(updated), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# PATCH /<appointment_id>/action
# pass action: "confirm" or "deny" in the body
@appointments_bp.route("/<appointment_id>/action", methods=["PATCH"])
@login_required()
@role_required(["salon_owner", "barber", "admin"])
@notify(
    ["user"],
    event_type="General",
    title="Appointment status Updated",
    message_template="Your appointment has been updated",
    related_key="appointment_id",
)
@swag_from("../docs/confirm_or_deny.yml")
def confirm_or_deny(appointment_id):
    """
    Confirm or deny an appointment.
    """
    try:
        user = get_current_user()
        body = request.get_json() or {}
        action = body.get("action")  # "confirm" or "deny"
        reason = body.get("reason")
        updated, error = AppointmentService.confirm_or_deny(appointment_id, action, user=user, reason=reason)
        if error == "Forbidden":
            return jsonify({"error": error}), 403
        elif error:
            return jsonify({"error": error}), 400
        return jsonify(updated), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# mark appointment as completed or no show: PATCH /<appointment_id>/complete
@appointments_bp.route("/<appointment_id>/complete", methods=["PATCH"])
@login_required()
@role_required(["barber", "salon_owner", "admin"])
@swag_from("../docs/mark_completed.yml")
def mark_completed(appointment_id):
    """Mark appointment as completed or no_show."""
    user = get_current_user()
    body = request.get_json() or {}
    status = body.get("status", "completed")  # default
    data, error = AppointmentService.mark_completed_or_no_show(appointment_id, status, user=user)
    if error == "Forbidden":
        return jsonify({"error": error}), 403
    elif error:
        return jsonify({"error": error}), 400
    return jsonify(data), 200

# create/update review
@appointments_bp.route("/<appointment_id>/review", methods=["POST"])
@login_required()
@role_required(["customer"])
def create_review(appointment_id):
    user = get_current_user()
    body = request.get_json() or {}
    stars = body.get("stars")
    comment = body.get("comment", "")
    if stars is None:
        return jsonify({"error": "stars is required"}), 400
    review, error = AppointmentService.create_review(appointment_id, int(stars), comment, user=user)
    if error == "Forbidden":
        return jsonify({"error": error}), 403
    elif error:
        return jsonify({"error": error}), 400
    return jsonify(review), 201

#GET /<appointment_id>
@appointments_bp.route("/<appointment_id>", methods=["GET"])
@login_required()
@role_required(["customer", "salon_owner", "barber", "admin"])
@swag_from("../docs/get_appointment.yml")
def get_appointment(appointment_id):
    """
    Get details for a single appointment by ID.
    """
    try:
        user = get_current_user()
        row, error = AppointmentService.get_by_id(appointment_id, user=user)

        if error == "Forbidden":
            return jsonify({"error": error}), 403
        elif error:
            return jsonify({"error": error}), 404
        return jsonify(row), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



