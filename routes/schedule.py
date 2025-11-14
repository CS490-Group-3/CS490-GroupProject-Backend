from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from models.schedule import (
    BarberAvailabilityCreateRequest, 
    BarberAvailabilityUpdateRequest,
    BarberUnavailabilityCreateRequest,
    BarberUnavailabilityUpdateRequest
)
from services.auth_service import AuthService
from services.schedule_service import ScheduleService
from middleware import login_required, role_required, get_current_user
from flasgger.utils import swag_from
from datetime import time
schedule_bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')

@schedule_bp.route('/availability', methods=['GET'])
@login_required()
@swag_from("../docs/schedule_get_availability.yml")
def get_availability():
    """
    Get barber weekly availability.
    """
    try:
        id = get_current_user().get('sub')
        print("Current user ID:", id)
        barber_id, error = AuthService.get_barber_id(id)
        print("Barber ID:", barber_id)
        if barber_id is None:
            return jsonify({"error": "Missing barber_id parameter"}), 400
        barber = ScheduleService.check_barber_exists(barber_id)
        print("Barber exists:", barber)
        if not barber:
            return jsonify({"error": "Barber not found"}), 404
        # Call schedule service to get availability
        result, error = ScheduleService.get_availability(barber_id=barber_id)
        
        #availability is not set up yet if error is returned
        if error:
            return jsonify({"error1": error}), 400
        
        return jsonify({
            "availability": result
        }), 200
        
    except Exception as e:
        return jsonify({"error2": str(e)}), 500
    
    
    
@schedule_bp.route('/availability', methods=['POST'])
@login_required()
@role_required(['barber', 'admin', 'salon_owner'])
@swag_from("../docs/schedule_create_availability.yml")
def create_availability():
    """
    Create barber weekly availability.
    """
    try:
        # Validate request data
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        availabilities = json_data.get('availability')
        if not availabilities:
            return jsonify({"error": "Missing 'availability' in request body"}), 400
        
        id = get_current_user().get('sub')
        barber_id, error = AuthService.get_barber_id(id)
        if not barber_id:
            return jsonify({"error": "Current user is not associated with a barber"}), 400
        
        for availability in availabilities:
            
            data = BarberAvailabilityCreateRequest(**availability)
            # Call schedule service to create availability
            result, error = ScheduleService.create_availability(
                barber_id=barber_id,
                day_of_week=data.day_of_week,
                start_time=data.start_time,
                end_time=data.end_time,
                is_active=data.is_active
            )
            
            if error:
                return jsonify({"error1": error}), 400
        
        return jsonify({
            "message": "Availability created successfully.",
        }), 201
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@schedule_bp.route('/availability', methods=['PATCH'])
@login_required()
@role_required(['barber', 'admin', 'salon_owner'])
@swag_from("../docs/schedule_update_availability.yml")
def update_availability():
    """
    Update barber weekly availability.
    """
    try:
        # Validate request data
        json_data = request.get_json()
        print("Received JSON data for update_availability:", json_data)
        if not json_data:
            return jsonify({"error1": "Invalid JSON body"}), 400
        
        availabilities = json_data.get('availability')
        if not availabilities:
            return jsonify({"error": "Missing 'availability' in request body"}), 400
        
        id = get_current_user().get('sub')
        barber_id = AuthService.get_barber_id(id)
        if not barber_id:
            return jsonify({"error": "Current user is not associated with a barber"}), 400
        
        for availability in availabilities:
            
            data = BarberAvailabilityUpdateRequest(**availability)
            # Call schedule service to update availability
            if isinstance(data.start_time, time):
                start_time = data.start_time.strftime("%H:%M:%S")
            if isinstance(data.end_time, time):
                end_time = data.end_time.strftime("%H:%M:%S")
            update={"day_of_week": data.day_of_week,
                    "start_time": start_time,
                    "end_time": end_time,
                    "is_active": data.is_active}
            result, error = ScheduleService.update_availability(
                availability_id=data.id,
                update_data=update
            )
            
            if error:
                return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Availability updated successfully.",
        }), 201
        
    except ValidationError as e:
        return jsonify({"error2": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error3": str(e)}), 500
