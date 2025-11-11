from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from models.appointment import (
    AppointmentCreateRequest,  
    AppointmentUpdateRequest
)
from services.appointment_service import AppointmentService
from services.auth_service import AuthService
from middleware import login_required, role_required, get_current_user, get_owned_salons
from utils.response import success_response, error_response

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
        user_id = user.get('id')
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
            appointments, error = AppointmentService.get_appointments_by_barber(user_id)
        else:
            return error_response(message="Unauthorized role", status_code=403, code="forbidden")
        
        if error:
            return error_response(message=error, status_code=400, code="list_failed")
        
        return success_response(
            data={"appointments": [appointment.dict() for appointment in appointments]},
            status_code=200
        )
        
    except Exception as e:
        return error_response(message="Internal server error", status_code=500, code="internal_error")

@appointments_bp.route('/', methods=['PATCH'])
@login_required()
@role_required(['customer', 'admin', 'owner', 'barber'])
def update_appointment():
    """
    Update an existing appointment.
    """
    try:
        json_data = request.get_json()
        if not json_data:
            return error_response(message="Invalid JSON body", status_code=400, code="validation_error")
        
        appointment_id = json_data.get('id')
        if not appointment_id:
            return error_response(message="Missing appointment ID", status_code=400, code="validation_error")
        
        data = AppointmentUpdateRequest(**json_data)
        
        update_data = data.dict(exclude_unset=True)
        update_data.pop('id', None)  # Remove id from update data if present
        
        result, error = AppointmentService.update_appointment(appointment_id, update_data)
        
        if error:
            return error_response(message=error, status_code=400, code="update_failed")
        
        return success_response(
            message="Appointment updated successfully.",
            data={"appointment": result.dict()},
            status_code=200
        )
        
    except ValidationError as e:
        return error_response(message="Validation failed", status_code=400, code="validation_error", details=e.errors())
    except Exception:
        return error_response(message="Internal server error", status_code=500, code="internal_error")

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
            return error_response(message="Invalid status value", status_code=400, code="validation_error")
        user = get_current_user()
        role = user.get('role')
        
        if role == 'customer' and status not in ['canceled']:
            return error_response(message="Customers can only cancel appointments.", status_code=403, code="forbidden")
        
        update_data = {"status": status}
        
        result, error = AppointmentService.update_appointment(id, update_data)
        
        if error:
            return error_response(message=error, status_code=400, code="status_update_failed")
        
        return success_response(
            message="Appointment status updated successfully.",
            data={"appointment": result.dict()},
            status_code=200
        )
        
    except Exception:
        return error_response(message="Internal server error", status_code=500, code="internal_error")
