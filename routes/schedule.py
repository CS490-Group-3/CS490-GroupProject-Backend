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

schedule_bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')

@schedule_bp.route('/availability/<barber_id>', methods=['GET'])
@login_required()
def get_availability(barber_id):
    """
    Get barber weekly availability.
    """
    try:
        if barber_id is None:
            return jsonify({"error": "Missing barber_id parameter"}), 400
        barber = ScheduleService.check_barber_exists(barber_id)
        if not barber:
            return jsonify({"error": "Barber not found"}), 404
        # Call schedule service to get availability
        result, error = ScheduleService.get_availability(barber_id=barber_id)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "availability": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
    
@schedule_bp.route('/availability', methods=['POST'])
@login_required()
@role_required(['barber', 'admin', 'owner'])
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
        
        id = get_current_user().get('id')
        barber_id = AuthService.get_barber_id(id)
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
                return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Availability created successfully.",
        }), 201
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@schedule_bp.route('/availability', methods=['PATCH'])
@login_required()
@role_required(['barber', 'admin', 'owner'])
def update_availability():
    """
    Update barber weekly availability.
    """
    try:
        # Validate request data
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        availabilities = json_data.get('availability')
        if not availabilities:
            return jsonify({"error": "Missing 'availability' in request body"}), 400
        
        id = get_current_user().get('id')
        barber_id = AuthService.get_barber_id(id)
        if not barber_id:
            return jsonify({"error": "Current user is not associated with a barber"}), 400
        
        for availability in availabilities:
            
            data = BarberAvailabilityUpdateRequest(**availability)
            # Call schedule service to update availability
            update={"day_of_week": data.day_of_week,
                    "start_time": data.start_time,
                    "end_time": data.end_time,
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
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
