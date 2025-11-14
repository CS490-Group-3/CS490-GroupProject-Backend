from flask import Blueprint, request, jsonify
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

@appointments_bp.route('/', methods=['GET'])
@login_required()
@role_required(['customer', 'admin', 'owner', 'barber'])
def list_appointments():
    """
    List appointments for the current user.
    """
    try:
        user = get_current_user()
        print("Current user:", user)
        user_id = user.get('sub')
        user_role = user.get('role')
        
        if user_role == 'customer':
            # Fetch appointments for customer
            appointments, error = AppointmentService.get_appointments_by_customer(user_id)
        elif user_role in ['owner']:
            # Fetch all appointments
            salons = get_owned_salons()
            salon_ids = [salon['id'] for salon in salons]
            
            appointments, error = AppointmentService.get_all_salon_appointments(salon_ids)
        elif user_role == 'barber':
            # Fetch appointments for barber
            print("Fetching appointments for barber with user_id:", user_id)
            barber_id = AuthService.get_barber_id(user_id)
            print("Barber ID:", barber_id)
            if barber_id is None:
                return jsonify({"error": "Barber profile not found"}), 404
            appointments, error = AppointmentService.get_appointments_by_barber(barber_id)
        else:
            return jsonify({"error": "Unauthorized role"}), 403
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "appointments": [appointment.dict() for appointment in appointments]
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@appointments_bp.route('/', methods=['PATCH'])
@login_required()
@role_required(['customer', 'admin', 'owner', 'barber'])
@notify(
    recipients=["barber", "user"], 
    event_type="appointment_confirmation",
    title="Appointment Updated",
    message_template="The appointment at {salon_name} for {service_name} has been updated.",
    schedule_func=NotificationService.schedule_upcoming_appointment, 
    related_key="appointment_id"
)#notify user and barber upon update 
def update_appointment():
    """
    Update an existing appointment.
    """
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        appointment_id = json_data.get('id')
        if not appointment_id:
            return jsonify({"error": "Missing appointment ID"}), 400
        
        data = AppointmentUpdateRequest(**json_data)
        
        update_data = data.dict(exclude_unset=True)
        update_data.pop('id', None)  # Remove id from update data if present
        
        result, error = AppointmentService.update_appointment(appointment_id, update_data)
        
    

        if error:
            return jsonify({"error": error}), 400
    
        return jsonify({
            "message": "Appointment updated successfully.",
            "appointment": result.dict()
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@appointments_bp.route('/<id>/<status>', methods=['PATCH'])
@login_required()
@role_required(['customer', 'admin', 'owner', 'barber'])
def change_appointment_status(id, status):
    """
    Change the status of an appointment.
    """
    try:
        valid_statuses = ['scheduled', 'completed', 'canceled', 'no_show']
        if status not in valid_statuses:
            return jsonify({"error": "Invalid status value"}), 400
        user = get_current_user()
        role = user.get('role')
        
        if role == 'customer' and status not in ['canceled']:
            return jsonify({"error": "Customers can only cancel appointments."}), 403
        
        update_data = {"status": status}
        
        result, error = AppointmentService.update_appointment(id, update_data)
        
        if error:
            return jsonify({"error": error}), 400


        return jsonify({
            "message": "Appointment status updated successfully.",
            "appointment": result.dict()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@appointments_bp.route('/<appointment_id>/approve', methods=['PATCH'])
@login_required()
@role_required(['barber'])
@notify(
    ["user"],
    event_type="appointment_confirmation",
    title="Appointment Approved",
    message_template="Your appointment has been approved by your barber.",
    related_key="appointment_id",
)
def approve_appointment(appointment_id):
    user = get_current_user()
    user_id = user.get("sub")
    result, error = AppointmentService.approve_appointment(appointment_id,user_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Appointment approved."}), 200


@appointments_bp.route('/<appointment_id>/deny', methods=['PATCH'])
@login_required()
@role_required(['barber'])
@notify(
    ["user"],
    event_type="appointment_cancellation",
    title="Appointment Denied",
    message_template="Your appointment was declined by your barber.",
    related_key="appointment_id",
)
def deny_appointment(appointment_id):
    user = get_current_user()
    user_id = user.get("sub")
    result, error = AppointmentService.deny_appointment(appointment_id, user_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Appointment denied."}), 200

