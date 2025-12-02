"""
Routes for managing payments.
"""
from flask import Blueprint, request, jsonify, g
from middleware import login_required, role_required, get_current_user
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error
from services.payment_service import PaymentService
from services.loyalty_service import LoyaltyService
from services.appointment_service import AppointmentService

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')
payments_bp.strict_slashes = False


@payments_bp.route('/create-with-appointment', methods=['POST'])
@auto_log_errors
@login_required()
def create_payment_with_appointment():
    """
    Create an appointment and process payment atomically.
    Appointment is only created if payment succeeds.
    
    Request body:
    {
        "appointment": {
            "barber_id": "uuid",
            "service_id": "uuid",
            "salon_id": "uuid",
            "start_at": "ISO datetime",
            "end_at": "ISO datetime",
            "notes": "optional"
        },
        "payment_method_id": "uuid" (optional - use saved method),
        OR new card details:
        {
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2025,
            "cvv": "123",
            "cardholder_name": "John Doe",
            "billing_address": {...},
            "save_payment_method": true/false
        },
        "redeem_loyalty_points": true/false
    }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        appointment_data = data.get('appointment')
        if not appointment_data:
            return jsonify({"error": "appointment data is required"}), 400
        
        # Get service to calculate amount
        from config import supabase
        service_id = appointment_data.get('service_id')
        if not service_id:
            return jsonify({"error": "service_id is required"}), 400
        
        service_response = supabase.table("services")\
            .select("id, price")\
            .eq("id", service_id)\
            .single()\
            .execute()
        
        if getattr(service_response, "error", None) or not service_response.data:
            return jsonify({"error": "Service not found"}), 404
        
        service = service_response.data
        payment_amount = float(service.get("price", 0))
        
        if payment_amount <= 0:
            return jsonify({"error": "Service must have a price"}), 400
        
        # Create appointment first (but we'll handle rollback if payment fails)
        appointment_payload = {
            "barber_id": appointment_data.get("barber_id"),
            "service_id": appointment_data.get("service_id"),
            "salon_id": appointment_data.get("salon_id"),
            "start_at": appointment_data.get("start_at"),
            "end_at": appointment_data.get("end_at"),
            "notes": appointment_data.get("notes"),
            "customer_id": user_id
        }
        
        created_appointment, error = AppointmentService.create_appointment(
            appointment_payload,
            user=user
        )
        
        if error:
            return jsonify({"error": f"Failed to create appointment: {error}"}), 400
        
        appointment_id = created_appointment.get("id")
        
        # Now process payment
        try:
            payment, error = LoyaltyService.process_appointment_payment_with_loyalty(
                user_id=user_id,
                appointment_id=appointment_id,
                payment_amount=payment_amount,
                payment_method_id=data.get('payment_method_id'),
                card_number=data.get('card_number'),
                exp_month=data.get('exp_month'),
                exp_year=data.get('exp_year'),
                cvv=data.get('cvv'),
                cardholder_name=data.get('cardholder_name'),
                billing_address=data.get('billing_address'),
                save_payment_method=data.get('save_payment_method', False),
                redeem_loyalty_points=data.get('redeem_loyalty_points', False)
            )
            
            if error:
                # Payment failed - cancel the appointment
                try:
                    AppointmentService.cancel_appointment(
                        appointment_id,
                        user=user,
                        reason="Payment failed"
                    )
                except Exception as cleanup_error:
                    # Log but don't fail - best effort cleanup
                    log_route_error(cleanup_error)
                
                return jsonify({"error": f"Payment failed: {error}"}), 400
            
            return jsonify({
                "message": "Appointment created and payment processed successfully",
                "appointment": created_appointment,
                "payment": payment
            }), 201
            
        except Exception as e:
            # Payment processing failed - try to cancel appointment
            try:
                AppointmentService.cancel_appointment(
                    appointment_id,
                    user=user,
                    reason="Payment processing error"
                )
            except Exception as cleanup_error:
                # Log but don't fail - best effort cleanup
                log_route_error(cleanup_error)
            
            log_route_error(e)
            return jsonify({"error": f"Payment processing failed: {str(e)}"}), 500
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payments_bp.route('', methods=['POST'])
@payments_bp.route('/', methods=['POST'])
@auto_log_errors
@login_required()
def create_payment():
    """
    Create a payment for an existing appointment.
    Request body:
    {
        "appointment_id": "uuid",
        "payment_method_id": "uuid" (optional - use saved method),
        OR new card details:
        {
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2025,
            "cvv": "123",
            "cardholder_name": "John Doe",
            "billing_address": {...},
            "save_payment_method": true/false
        },
        "redeem_loyalty_points": true/false
    }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        appointment_id = data.get('appointment_id')
        if not appointment_id:
            return jsonify({"error": "appointment_id is required"}), 400
        
        # Get appointment to calculate amount
        from config import supabase
        appt_response = supabase.table("appointments")\
            .select("id, customer_id, salon_id, service_id, services:service_id(price)")\
            .eq("id", appointment_id)\
            .single()\
            .execute()
        
        if getattr(appt_response, "error", None) or not appt_response.data:
            return jsonify({"error": "Appointment not found"}), 404
        
        appointment = appt_response.data
        service = appointment.get("services")
        payment_amount = float(service.get("price", 0)) if isinstance(service, dict) else 0.0
        
        if payment_amount <= 0:
            return jsonify({"error": "Invalid appointment amount"}), 400
        
        # Process payment with loyalty
        payment, error = LoyaltyService.process_appointment_payment_with_loyalty(
            user_id=user_id,
            appointment_id=appointment_id,
            payment_amount=payment_amount,
            payment_method_id=data.get('payment_method_id'),
            card_number=data.get('card_number'),
            exp_month=data.get('exp_month'),
            exp_year=data.get('exp_year'),
            cvv=data.get('cvv'),
            cardholder_name=data.get('cardholder_name'),
            billing_address=data.get('billing_address'),
            save_payment_method=data.get('save_payment_method', False),
            redeem_loyalty_points=data.get('redeem_loyalty_points', False)
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Payment processed successfully",
            "payment": payment
        }), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payments_bp.route('', methods=['GET'])
@payments_bp.route('/', methods=['GET'])
@auto_log_errors
@login_required()
def list_payments():
    """
    Get payments for the current user.
    Query params: start_date, end_date, limit, offset
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        payments, error = PaymentService.get_user_payments(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 400
        
        return jsonify({"payments": payments}), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500


@payments_bp.route('/<payment_id>', methods=['GET'])
@auto_log_errors
@login_required()
def get_payment(payment_id):
    """
    Get a single payment by ID.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user.get('sub') or user.get('id')
        if not user_id:
            return jsonify({"error": "Invalid user data"}), 400
        
        payment, error = PaymentService.get_payment(payment_id, user_id=user_id)
        
        if error:
            log_service_error(error)
            return jsonify({"error": error}), 404
        
        return jsonify({"payment": payment}), 200
        
    except Exception as e:
        log_route_error(e)
        return jsonify({"error": str(e)}), 500
