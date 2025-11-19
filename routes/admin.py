"""
Admin routes for administrative functions.
Requires admin role authentication.
"""
from flask import Blueprint, request, jsonify
from flasgger.utils import swag_from
from services.demographics_service import DemographicsService
from middleware import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/demographics', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_demographics.yml")
def get_demographics():
    """
    Get aggregated demographic data for all users.
    Returns statistics for visualization and segmentation.
    
    Query Parameters:
        - segment: Optional filter by segment (city, state, age_bracket, gender, role)
        - value: Value for the segment filter
    
    Returns:
        Aggregated demographic data including:
        - Total users
        - Distribution by location (cities, states)
        - Distribution by age bracket
        - Distribution by gender
        - Distribution by role
        - Preferred services analysis
        - Top cities, states, and services
    """
    try:
        # Check if filtering by segment
        segment = request.args.get('segment')
        value = request.args.get('value')
        
        if segment and value:
            # Get filtered demographics
            filters = {}
            if segment == 'city':
                filters['city'] = value
            elif segment == 'state':
                filters['state'] = value
            elif segment == 'age_bracket':
                filters['age_bracket'] = value
            elif segment == 'gender':
                filters['gender'] = value
            elif segment == 'role':
                filters['role'] = value
            
            users, error = DemographicsService.get_demographics_by_segment(**filters)
            
            if error:
                return jsonify({"error": error}), 500
            
            return jsonify({
                "message": "Demographics retrieved successfully",
                "segment": segment,
                "value": value,
                "count": len(users),
                "users": users
            }), 200
        else:
            # Get full aggregated demographics
            demographics, error = DemographicsService.get_demographics_aggregation()
            
            if error:
                return jsonify({"error": error}), 500
            
            return jsonify({
                "message": "Demographics retrieved successfully",
                "demographics": demographics
            }), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


