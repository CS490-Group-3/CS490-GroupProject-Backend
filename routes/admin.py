"""
Admin routes for administrative functions.
Requires admin role authentication.
"""
from flask import Blueprint, request, jsonify, Response
from flasgger.utils import swag_from
from services.demographics_service import DemographicsService
from services.analytics_service import AnalyticsService
from services.export_service import ExportService
from middleware import role_required
from datetime import datetime, date
from typing import Optional
import os
import jwt

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


@admin_bp.route('/metrics/engagement', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_engagement.yml")
def get_engagement_metrics():
    """
    Get engagement metrics for a date range.
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        metrics, error = AnalyticsService.get_engagement_metrics(start_date, end_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Engagement metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/appointments', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_appointments.yml")
def get_appointment_metrics():
    """
    Get appointment metrics for a date range.
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        metrics, error = AnalyticsService.get_appointment_metrics(start_date, end_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Appointment metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/revenue', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_revenue.yml")
def get_revenue_metrics():
    """
    Get revenue metrics for a date range.
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        metrics, error = AnalyticsService.get_revenue_metrics(start_date, end_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Revenue metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/loyalty', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_loyalty.yml")
def get_loyalty_metrics():
    """
    Get loyalty program metrics for a date range.
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        metrics, error = AnalyticsService.get_loyalty_metrics(start_date, end_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Loyalty metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/retention', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_retention.yml")
def get_retention_metrics():
    """
    Get customer retention metrics for a date range.
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        metrics, error = AnalyticsService.get_retention_metrics(start_date, end_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Retention metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/platform', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_metrics_platform.yml")
def get_platform_metrics():
    """
    Get current platform metrics snapshot.
    """
    try:
        metrics, error = AnalyticsService.get_platform_metrics()
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Platform metrics retrieved successfully",
            "metrics": metrics
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/daily-statistics/calculate', methods=['POST'])
@swag_from("../docs/admin_calculate_daily_stats.yml")
def calculate_daily_statistics():
    """
    Calculate and store daily statistics for a specific date.
    Can be called by scheduled jobs (cron) or manually.
    
    Authentication:
        - Admin role required (via Authorization header)
        - OR cron secret token (via X-Cron-Secret header)
    
    Body (optional):
        - date: Date to calculate for (YYYY-MM-DD), defaults to yesterday
    """
    try:
        # Check for cron secret token (for scheduled jobs)
        cron_secret = request.headers.get('X-Cron-Secret')
        cron_secret_env = os.getenv('CRON_SECRET')
        
        # If cron secret is provided and matches, allow access
        if cron_secret and cron_secret_env and cron_secret == cron_secret_env:
            # Authenticated via cron secret, proceed
            pass
        elif cron_secret and not cron_secret_env:
            # Cron secret provided but CRON_SECRET env var not set
            return jsonify({
                "error": "Configuration error: CRON_SECRET environment variable not set"
            }), 500
        elif cron_secret and cron_secret_env and cron_secret != cron_secret_env:
            # Cron secret provided but doesn't match
            return jsonify({
                "error": "Unauthorized: Invalid cron secret"
            }), 401
        else:
            # No cron secret provided, require admin authentication
            # Manually verify JWT token and check admin role
            try:
                from middleware.auth import verify_jwt_token
                auth_header = request.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    return jsonify({"error": "Unauthorized: Missing or invalid Authorization header"}), 401
                
                token = auth_header.split(' ')[1]
                decoded = verify_jwt_token(token)
                
                # Get user role from database
                from config import supabase
                user_id = decoded.get('sub')
                user_response = supabase.table('user_details')\
                    .select('role')\
                    .eq('id', user_id)\
                    .single()\
                    .execute()
                
                if not user_response.data:
                    return jsonify({"error": "Unauthorized: User not found"}), 401
                
                user_role = user_response.data.get('role')
                if user_role != 'admin':
                    return jsonify({"error": "Forbidden: Admin role required"}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Unauthorized: Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Unauthorized: Invalid token"}), 401
            except Exception as e:
                return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
        
        # Get JSON data, but don't fail if body is empty
        # Use silent=True to return None instead of raising an error on empty/invalid JSON
        data = request.get_json(silent=True) or {}
        date_str = data.get('date')
        
        target_date = None
        if date_str:
            target_date = datetime.fromisoformat(date_str).date()
        
        stats, error = AnalyticsService.calculate_daily_statistics(target_date)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "message": "Daily statistics calculated successfully",
            "statistics": stats
        }), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/<metrics_type>/export/csv', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_export_csv.yml")
def export_metrics_csv(metrics_type: str):
    """
    Export metrics to CSV format.
    
    Path Parameters:
        - metrics_type: Type of metrics (engagement, appointments, revenue, loyalty, retention, demographics, platform)
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD) - required for date-range metrics
        - end_date: End date (YYYY-MM-DD) - required for date-range metrics
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Get metrics data
        if metrics_type == 'demographics':
            metrics, error = DemographicsService.get_demographics_aggregation()
        elif metrics_type == 'platform':
            metrics, error = AnalyticsService.get_platform_metrics()
        else:
            if not start_date_str or not end_date_str:
                return jsonify({"error": "start_date and end_date are required"}), 400
            
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            
            if metrics_type == 'engagement':
                metrics, error = AnalyticsService.get_engagement_metrics(start_date, end_date)
            elif metrics_type == 'appointments':
                metrics, error = AnalyticsService.get_appointment_metrics(start_date, end_date)
            elif metrics_type == 'revenue':
                metrics, error = AnalyticsService.get_revenue_metrics(start_date, end_date)
            elif metrics_type == 'loyalty':
                metrics, error = AnalyticsService.get_loyalty_metrics(start_date, end_date)
            elif metrics_type == 'retention':
                metrics, error = AnalyticsService.get_retention_metrics(start_date, end_date)
            else:
                return jsonify({"error": f"Unknown metrics type: {metrics_type}"}), 400
        
        if error:
            return jsonify({"error": error}), 500
        
        # Export to CSV
        csv_string, filename = ExportService.export_metrics_to_csv(metrics_type, metrics)
        
        return Response(
            csv_string,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/metrics/<metrics_type>/export/pdf', methods=['GET'])
@role_required(['admin'], verify_with_supabase=True)
@swag_from("../docs/admin_export_pdf.yml")
def export_metrics_pdf(metrics_type: str):
    """
    Export metrics to PDF format.
    
    Path Parameters:
        - metrics_type: Type of metrics (engagement, appointments, revenue, loyalty, retention, demographics, platform)
    
    Query Parameters:
        - start_date: Start date (YYYY-MM-DD) - required for date-range metrics
        - end_date: End date (YYYY-MM-DD) - required for date-range metrics
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Get metrics data
        if metrics_type == 'demographics':
            metrics, error = DemographicsService.get_demographics_aggregation()
        elif metrics_type == 'platform':
            metrics, error = AnalyticsService.get_platform_metrics()
        else:
            if not start_date_str or not end_date_str:
                return jsonify({"error": "start_date and end_date are required"}), 400
            
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            
            if metrics_type == 'engagement':
                metrics, error = AnalyticsService.get_engagement_metrics(start_date, end_date)
            elif metrics_type == 'appointments':
                metrics, error = AnalyticsService.get_appointment_metrics(start_date, end_date)
            elif metrics_type == 'revenue':
                metrics, error = AnalyticsService.get_revenue_metrics(start_date, end_date)
            elif metrics_type == 'loyalty':
                metrics, error = AnalyticsService.get_loyalty_metrics(start_date, end_date)
            elif metrics_type == 'retention':
                metrics, error = AnalyticsService.get_retention_metrics(start_date, end_date)
            else:
                return jsonify({"error": f"Unknown metrics type: {metrics_type}"}), 400
        
        if error:
            return jsonify({"error": error}), 500
        
        # Export to PDF
        pdf_bytes, filename = ExportService.export_to_pdf(metrics, metrics_type)
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


