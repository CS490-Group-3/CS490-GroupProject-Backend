from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from services.appointment_service import AppointmentService
from services.auth_service import AuthService
from middleware import login_required, role_required, get_current_user

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')

@profile_bp.route('/upload', methods=['POST'])
@login_required()
def upload_profile_picture():
    """
    Upload or update the profile picture for the authenticated user.
    """
    try:
        user = get_current_user()
        user_id = user.get('id')
        
        if 'profile_picture' not in request.files:
            return jsonify({"error": "No profile picture provided"}), 400
        
        profile_picture = request.files['profile_picture']
        
        result, error = AuthService.upload_profile_picture(user_id, profile_picture)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Profile picture uploaded successfully",
            "profile_picture_url": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@profile_bp.route('/history', methods=['GET'])
@login_required()
def get_user_history():
    """
    Get the history of the authenticated user.
    """
    try:
        user = get_current_user()
        user_id = user.get('id')
        
        result, error = AppointmentService.get_user_history(user_id)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "history": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500