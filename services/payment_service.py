"""
Payment service for handling payments, saved payment methods, and payment validation.
"""
from config import supabase
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from services.payment_validation_service import PaymentValidationService
from services.audit_logging_service import AuditLoggingService
from services.error_logging_service import ErrorLoggingService
import uuid


class PaymentService:
    """Service for managing payments and saved payment methods."""
    
    @staticmethod
    def create_saved_payment_method(
        user_id: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        cardholder_name: Optional[str] = None,
        billing_address: Optional[Dict] = None,
        is_default: bool = False
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a saved payment method for a user.
        
        Args:
            user_id: User ID
            card_number: Card number (will be validated)
            exp_month: Expiration month (1-12)
            exp_year: Expiration year (4 digits)
            cvv: CVV code
            cardholder_name: Cardholder name
            billing_address: Billing address dict
            is_default: Whether this should be the default payment method
        
        Returns:
            Tuple of (saved_method_dict, error_message)
        """
        try:
            # Validate card information
            is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
                card_number=card_number,
                exp_month=exp_month,
                exp_year=exp_year,
                cvv=cvv,
                cardholder_name=cardholder_name
            )
            
            if not is_valid:
                return None, error
            
            # If setting as default, unset other defaults first
            if is_default:
                supabase.table("saved_payment_methods")\
                    .update({"is_default": False})\
                    .eq("user_id", user_id)\
                    .eq("is_active", True)\
                    .execute()
            
            # Prepare saved payment method data
            saved_method_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "payment_method_type": "card",
                "provider": "internal",
                "is_default": is_default,
                "card_last4": card_info["last4"],
                "card_brand": card_info["brand"],
                "card_exp_month": exp_month,
                "card_exp_year": exp_year,
                "billing_name": cardholder_name,
                "is_active": True
            }
            
            # Add billing address if provided
            if billing_address:
                saved_method_data.update({
                    "billing_address_line1": billing_address.get("line1"),
                    "billing_address_line2": billing_address.get("line2"),
                    "billing_city": billing_address.get("city"),
                    "billing_state": billing_address.get("state"),
                    "billing_zip": billing_address.get("zip"),
                    "billing_country": billing_address.get("country", "US")
                })
            
            # Insert saved payment method
            response = supabase.table("saved_payment_methods")\
                .insert(saved_method_data)\
                .execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            created_method = response.data[0]
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='saved_payment_methods',
                record_id=created_method["id"],
                action='INSERT',
                new_values=saved_method_data,
                changed_by=user_id
            )
            
            return created_method, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to create saved payment method: {str(e)}"
    
    @staticmethod
    def get_user_saved_payment_methods(user_id: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Get all active saved payment methods for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Tuple of (list of saved methods, error_message)
        """
        try:
            response = supabase.table("saved_payment_methods")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .order("is_default", desc=True)\
                .order("created_at", desc=False)\
                .execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            return response.data or [], None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get saved payment methods: {str(e)}"
    
    @staticmethod
    def set_default_payment_method(user_id: str, payment_method_id: str) -> Tuple[bool, Optional[str]]:
        """
        Set a payment method as default for a user.
        
        Args:
            user_id: User ID
            payment_method_id: Payment method ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify payment method belongs to user
            check_response = supabase.table("saved_payment_methods")\
                .select("id, user_id")\
                .eq("id", payment_method_id)\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .single()\
                .execute()
            
            if getattr(check_response, "error", None) or not check_response.data:
                return False, "Payment method not found or does not belong to user"
            
            # Unset all other defaults
            supabase.table("saved_payment_methods")\
                .update({"is_default": False})\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .neq("id", payment_method_id)\
                .execute()
            
            # Set this one as default
            response = supabase.table("saved_payment_methods")\
                .update({"is_default": True})\
                .eq("id", payment_method_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if getattr(response, "error", None):
                return False, response.error.message
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='saved_payment_methods',
                record_id=payment_method_id,
                action='UPDATE',
                new_values={"is_default": True},
                changed_by=user_id
            )
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return False, f"Failed to set default payment method: {str(e)}"
    
    @staticmethod
    def delete_saved_payment_method(user_id: str, payment_method_id: str) -> Tuple[bool, Optional[str]]:
        """
        Soft delete a saved payment method.
        
        Args:
            user_id: User ID
            payment_method_id: Payment method ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify payment method belongs to user
            check_response = supabase.table("saved_payment_methods")\
                .select("id, user_id, is_default")\
                .eq("id", payment_method_id)\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .single()\
                .execute()
            
            if getattr(check_response, "error", None) or not check_response.data:
                return False, "Payment method not found or does not belong to user"
            
            method_data = check_response.data
            was_default = method_data.get("is_default", False)
            
            # Soft delete
            response = supabase.table("saved_payment_methods")\
                .update({
                    "is_active": False,
                    "is_default": False,
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                })\
                .eq("id", payment_method_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if getattr(response, "error", None):
                return False, response.error.message
            
            # If it was default, set another one as default if available
            if was_default:
                other_methods = supabase.table("saved_payment_methods")\
                    .select("id")\
                    .eq("user_id", user_id)\
                    .eq("is_active", True)\
                    .limit(1)\
                    .execute()
                
                if other_methods.data:
                    supabase.table("saved_payment_methods")\
                        .update({"is_default": True})\
                        .eq("id", other_methods.data[0]["id"])\
                        .execute()
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='saved_payment_methods',
                record_id=payment_method_id,
                action='DELETE',
                old_values=method_data,
                changed_by=user_id
            )
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return False, f"Failed to delete payment method: {str(e)}"
    
    @staticmethod
    def create_payment(
        user_id: str,
        appointment_id: str,
        amount: float,
        payment_method_id: Optional[str] = None,
        card_number: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        cvv: Optional[str] = None,
        cardholder_name: Optional[str] = None,
        billing_address: Optional[Dict] = None,
        save_payment_method: bool = False,
        loyalty_points_used: int = 0,
        discount_applied: float = 0.0
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a payment for an appointment.
        
        Args:
            user_id: User ID (customer)
            appointment_id: Appointment ID
            amount: Payment amount (after discounts)
            payment_method_id: Optional saved payment method ID
            card_number: Optional new card number (if not using saved method)
            exp_month: Optional expiration month
            exp_year: Optional expiration year
            cvv: Optional CVV
            cardholder_name: Optional cardholder name
            billing_address: Optional billing address
            save_payment_method: Whether to save the new card
            loyalty_points_used: Points used for discount
            discount_applied: Discount amount applied
        
        Returns:
            Tuple of (payment_dict, error_message)
        """
        try:
            # Get appointment to verify it exists and get salon_id
            appt_response = supabase.table("appointments")\
                .select("id, customer_id, salon_id, service_id, status")\
                .eq("id", appointment_id)\
                .single()\
                .execute()
            
            if getattr(appt_response, "error", None) or not appt_response.data:
                return None, "Appointment not found"
            
            appointment = appt_response.data
            
            # Verify appointment belongs to user
            if appointment["customer_id"] != user_id:
                return None, "Appointment does not belong to user"
            
            salon_id = appointment["salon_id"]
            saved_method_id = None
            
            # Handle payment method
            if payment_method_id:
                # Using saved payment method
                method_response = supabase.table("saved_payment_methods")\
                    .select("id, user_id, is_active")\
                    .eq("id", payment_method_id)\
                    .eq("user_id", user_id)\
                    .eq("is_active", True)\
                    .single()\
                    .execute()
                
                if getattr(method_response, "error", None) or not method_response.data:
                    return None, "Saved payment method not found or inactive"
                
                saved_method_id = payment_method_id
                
            elif card_number:
                # Using new card - validate it
                is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
                    card_number=card_number,
                    exp_month=exp_month,
                    exp_year=exp_year,
                    cvv=cvv,
                    cardholder_name=cardholder_name
                )
                
                if not is_valid:
                    return None, error
                
                # Save payment method if requested
                if save_payment_method:
                    saved_method, error = PaymentService.create_saved_payment_method(
                        user_id=user_id,
                        card_number=card_number,
                        exp_month=exp_month,
                        exp_year=exp_year,
                        cvv=cvv,
                        cardholder_name=cardholder_name,
                        billing_address=billing_address,
                        is_default=False  # Don't auto-set as default
                    )
                    
                    if error:
                        return None, f"Failed to save payment method: {error}"
                    
                    saved_method_id = saved_method["id"]
            else:
                return None, "Either payment_method_id or card details must be provided"
            
            # Calculate subtotal (amount before discount)
            subtotal = amount + discount_applied
            
            # Create payment record
            # payment_method enum values: credit_card, debit_card, loyalty_points, mixed
            # payment_status enum values: pending, completed, failed, refunded
            payment_data = {
                "id": str(uuid.uuid4()),
                "appointment_id": appointment_id,
                "user_id": user_id,
                "salon_id": salon_id,
                "amount": amount,
                "payment_method": "credit_card",  # Valid enum values: credit_card, debit_card, loyalty_points, mixed
                "payment_status": "completed",  # Valid enum values: pending, completed, failed, refunded
                "payment_method_id": saved_method_id,
                "loyalty_points_used": loyalty_points_used,
                "discount_applied": discount_applied,
                "subtotal": subtotal
            }
            
            response = supabase.table("payments")\
                .insert(payment_data)\
                .execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            created_payment = response.data[0]
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='payments',
                record_id=created_payment["id"],
                action='INSERT',
                new_values=payment_data,
                changed_by=user_id
            )
            
            return created_payment, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to create payment: {str(e)}"
    
    @staticmethod
    def create_order_payment(
        user_id: str,
        order_id: str,
        amount: float,
        payment_method_id: Optional[str] = None,
        card_number: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        cvv: Optional[str] = None,
        cardholder_name: Optional[str] = None,
        billing_address: Optional[Dict] = None,
        save_payment_method: bool = False,
        loyalty_points_used: int = 0,
        discount_applied: float = 0.0
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a payment for an order.
        
        Args:
            user_id: User ID (customer)
            order_id: Order ID
            amount: Payment amount (after discounts)
            payment_method_id: Optional saved payment method ID
            card_number: Optional new card number (if not using saved method)
            exp_month: Optional expiration month
            exp_year: Optional expiration year
            cvv: Optional CVV
            cardholder_name: Optional cardholder name
            billing_address: Optional billing address
            save_payment_method: Whether to save the new card
            loyalty_points_used: Points used for discount
            discount_applied: Discount amount applied
        
        Returns:
            Tuple of (payment_dict, error_message)
        """
        try:
            # Get order to verify it exists and get salon_id
            order_response = supabase.table("orders")\
                .select("id, user_id, salon_id, order_status")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            if getattr(order_response, "error", None) or not order_response.data:
                return None, "Order not found"
            
            order = order_response.data
            
            # Verify order belongs to user
            if order["user_id"] != user_id:
                return None, "Order does not belong to user"
            
            # Verify order is in a valid state for payment
            if order["order_status"] not in ["cart", "pending"]:
                return None, f"Cannot pay for order with status: {order['order_status']}"
            
            salon_id = order["salon_id"]
            saved_method_id = None
            
            # Handle payment method
            if payment_method_id:
                # Using saved payment method
                method_response = supabase.table("saved_payment_methods")\
                    .select("id, user_id, is_active")\
                    .eq("id", payment_method_id)\
                    .eq("user_id", user_id)\
                    .eq("is_active", True)\
                    .single()\
                    .execute()
                
                if getattr(method_response, "error", None) or not method_response.data:
                    return None, "Saved payment method not found or inactive"
                
                saved_method_id = payment_method_id
                
            elif card_number:
                # Using new card - validate it
                is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
                    card_number=card_number,
                    exp_month=exp_month,
                    exp_year=exp_year,
                    cvv=cvv,
                    cardholder_name=cardholder_name
                )
                
                if not is_valid:
                    return None, error
                
                # Save payment method if requested
                if save_payment_method:
                    saved_method, error = PaymentService.create_saved_payment_method(
                        user_id=user_id,
                        card_number=card_number,
                        exp_month=exp_month,
                        exp_year=exp_year,
                        cvv=cvv,
                        cardholder_name=cardholder_name,
                        billing_address=billing_address,
                        is_default=False  # Don't auto-set as default
                    )
                    
                    if error:
                        return None, f"Failed to save payment method: {error}"
                    
                    saved_method_id = saved_method["id"]
            else:
                return None, "Either payment_method_id or card details must be provided"
            
            # Calculate subtotal (amount before discount)
            subtotal = amount + discount_applied
            
            # Create payment record
            # payment_method enum values: credit_card, debit_card, loyalty_points, mixed
            # payment_status enum values: pending, completed, failed, refunded
            payment_data = {
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "user_id": user_id,
                "salon_id": salon_id,
                "amount": amount,
                "payment_method": "credit_card",  # Valid enum values: credit_card, debit_card, loyalty_points, mixed
                "payment_status": "completed",  # Valid enum values: pending, completed, failed, refunded
                "payment_method_id": saved_method_id,
                "loyalty_points_used": loyalty_points_used,
                "discount_applied": discount_applied,
                "subtotal": subtotal
            }
            
            response = supabase.table("payments")\
                .insert(payment_data)\
                .execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            created_payment = response.data[0]
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='payments',
                record_id=created_payment["id"],
                action='INSERT',
                new_values=payment_data,
                changed_by=user_id
            )
            
            return created_payment, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to create payment: {str(e)}"
    
    @staticmethod
    def refund_payment(payment_id: str, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Refund a payment by setting its status to "refunded".
        
        Args:
            payment_id: Payment ID to refund
            reason: Optional reason for refund
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get payment
            response = supabase.table("payments")\
                .select("id, payment_status, appointment_id, order_id")\
                .eq("id", payment_id)\
                .single()\
                .execute()
            
            if getattr(response, "error", None):
                ErrorLoggingService.log_exception(
                    Exception(f"Failed to fetch payment {payment_id}: {response.error.message}"),
                    severity='high'
                )
                return False, f"Payment not found: {response.error.message}"
            
            if not response.data:
                return False, "Payment not found"
            
            payment = response.data
            
            # Check if already refunded
            if payment.get("payment_status") == "refunded":
                return True, None  # Already refunded
            
            # Only refund completed payments
            if payment.get("payment_status") != "completed":
                return False, f"Cannot refund payment with status: {payment.get('payment_status')}"
            
            # Update payment status to refunded
            update_response = supabase.table("payments")\
                .update({
                    "payment_status": "refunded",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })\
                .eq("id", payment_id)\
                .execute()
            
            if getattr(update_response, "error", None):
                return False, update_response.error.message
            
            # Verify the update succeeded - check if data was returned or fetch to confirm
            if hasattr(update_response, "data") and update_response.data and len(update_response.data) > 0:
                updated_payment = update_response.data[0]
                if updated_payment.get("payment_status") != "refunded":
                    return False, f"Payment status update failed: expected 'refunded', got '{updated_payment.get('payment_status')}'"
            else:
                # If no data returned, fetch to verify
                verify_response = supabase.table("payments")\
                    .select("id, payment_status")\
                    .eq("id", payment_id)\
                    .single()\
                    .execute()
                
                if getattr(verify_response, "error", None):
                    return False, f"Failed to verify payment update: {verify_response.error.message}"
                
                if not verify_response.data:
                    return False, "Payment not found after update"
                
                if verify_response.data.get("payment_status") != "refunded":
                    return False, f"Payment status update failed: expected 'refunded', got '{verify_response.data.get('payment_status')}'"
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='payments',
                record_id=payment_id,
                action='UPDATE',
                old_values={'payment_status': 'completed'},
                new_values={'payment_status': 'refunded'},
                changed_by=None  # System action
            )
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to refund payment: {str(e)}"
    
    @staticmethod
    def get_user_payments(
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get payments for a user.
        
        Args:
            user_id: User ID
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            Tuple of (list of payments, error_message)
        """
        try:
            query = supabase.table("payments")\
                .select("*, appointments:appointment_id(id, start_at, services:service_id(name))")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .range(offset, offset + limit - 1)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            payments = response.data or []
            
            # Format payments for frontend
            formatted_payments = []
            for payment in payments:
                appointment = payment.get("appointments")
                service = appointment.get("services") if isinstance(appointment, dict) else None
                
                formatted_payments.append({
                    "id": payment.get("id"),
                    "date": payment.get("created_at"),
                    "amount": float(payment.get("amount", 0)),
                    "status": payment.get("payment_status"),
                    "paymentMethod": payment.get("payment_method"),
                    "appointment_id": payment.get("appointment_id"),
                    "service": service.get("name") if isinstance(service, dict) else None,
                    "discount_applied": float(payment.get("discount_applied", 0)),
                    "loyalty_points_used": payment.get("loyalty_points_used", 0)
                })
            
            return formatted_payments, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get payments: {str(e)}"
    
    @staticmethod
    def get_salon_payments(
        salon_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get payments for a salon (for salon owners).
        
        Args:
            salon_id: Salon ID
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            Tuple of (list of payments, error_message)
        """
        try:
            # Base query for payments
            query = supabase.table("payments")\
                .select("id, amount, created_at, payment_status, payment_method, user_id, appointment_id, order_id")\
                .eq("salon_id", salon_id)\
                .order("created_at", desc=True)\
                .range(offset, offset + limit - 1)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            payments = response.data or []
            
            if not payments:
                return [], None
            
            # Get unique user IDs and fetch customer info separately
            user_ids = list(set([p.get("user_id") for p in payments if p.get("user_id")]))
            customer_profiles = {}
            
            if user_ids:
                try:
                    # Try user_profiles first
                    prof_res = supabase.table("user_profiles")\
                        .select("user_id, first_name, last_name")\
                        .in_("user_id", user_ids)\
                        .execute()
                    
                    if prof_res.data:
                        for row in prof_res.data:
                            customer_profiles[str(row["user_id"])] = {
                                "first_name": row.get("first_name", ""),
                                "last_name": row.get("last_name", "")
                            }
                    
                    # Also try user_details as fallback
                    alt_res = supabase.table("user_details")\
                        .select("id, first_name, last_name")\
                        .in_("id", user_ids)\
                        .execute()
                    
                    if alt_res.data:
                        for row in alt_res.data:
                            user_id_key = str(row["id"])
                            if user_id_key not in customer_profiles:
                                customer_profiles[user_id_key] = {
                                    "first_name": row.get("first_name", ""),
                                    "last_name": row.get("last_name", "")
                                }
                except Exception:
                    pass
            
            # Get appointment details for appointment payments
            appointment_ids = [p.get("appointment_id") for p in payments if p.get("appointment_id")]
            appointments_map = {}
            services_map = {}
            
            if appointment_ids:
                try:
                    appt_res = supabase.table("appointments")\
                        .select("id, service_id")\
                        .in_("id", appointment_ids)\
                        .execute()
                    
                    if appt_res.data:
                        service_ids = [a.get("service_id") for a in appt_res.data if a.get("service_id")]
                        appointments_map = {a["id"]: a for a in appt_res.data}
                        
                        if service_ids:
                            service_res = supabase.table("services")\
                                .select("id, name")\
                                .in_("id", service_ids)\
                                .execute()
                            
                            if service_res.data:
                                services_map = {s["id"]: s for s in service_res.data}
                except Exception:
                    pass
            
            # Get order details for order payments
            order_ids = [p.get("order_id") for p in payments if p.get("order_id")]
            orders_map = {}
            
            if order_ids:
                try:
                    order_res = supabase.table("orders")\
                        .select("id, order_status")\
                        .in_("id", order_ids)\
                        .execute()
                    
                    if order_res.data:
                        orders_map = {o["id"]: o for o in order_res.data}
                except Exception:
                    pass
            
            # Format payments for frontend
            formatted_payments = []
            for payment in payments:
                user_id = payment.get("user_id")
                profile = customer_profiles.get(str(user_id), {}) if user_id else {}
                customer_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or "Customer"
                
                # Determine service/order name
                service_name = None
                payment_type = None
                
                appointment_id = payment.get("appointment_id")
                order_id = payment.get("order_id")
                
                if appointment_id:
                    appointment = appointments_map.get(appointment_id)
                    if appointment:
                        service_id = appointment.get("service_id")
                        service = services_map.get(service_id) if service_id else None
                        service_name = service.get("name") if service else "Appointment"
                    else:
                        service_name = "Appointment"
                    payment_type = "appointment"
                elif order_id:
                    order = orders_map.get(order_id)
                    service_name = "Product Order"
                    payment_type = "order"
                else:
                    service_name = "Payment"
                
                formatted_payments.append({
                    "id": payment.get("id"),
                    "date": payment.get("created_at"),
                    "customer": customer_name,
                    "service": service_name,
                    "amount": float(payment.get("amount", 0)),
                    "status": payment.get("payment_status"),
                    "paymentMethod": payment.get("payment_method"),
                    "appointment_id": appointment_id,
                    "order_id": order_id,
                    "type": payment_type
                })
            
            return formatted_payments, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get salon payments: {str(e)}"
    
    @staticmethod
    def get_salon_revenue_analytics(
        salon_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get comprehensive revenue analytics for a salon.
        
        Args:
            salon_id: Salon ID
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
        
        Returns:
            Tuple of (revenue_analytics_dict, error_message)
        """
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Base query for all completed payments
            query = supabase.table("payments")\
                .select("id, amount, created_at, payment_status, appointment_id, order_id")\
                .eq("salon_id", salon_id)\
                .eq("payment_status", "completed")\
                .order("created_at", desc=False)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            payments = response.data or []
            
            if not payments:
                return {
                    "total_revenue": 0.0,
                    "total_payments": 0,
                    "monthly_breakdown": [],
                    "weekly_revenue": 0.0,
                    "revenue_by_type": {
                        "appointments": 0.0,
                        "orders": 0.0
                    },
                    "average_transaction": 0.0,
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }, None
            
            # Calculate totals
            total_revenue = sum(float(p.get("amount", 0)) for p in payments)
            total_payments = len(payments)
            average_transaction = total_revenue / total_payments if total_payments > 0 else 0.0
            
            # Monthly breakdown
            monthly_revenue = defaultdict(float)
            monthly_count = defaultdict(int)
            
            for payment in payments:
                created_at = payment.get("created_at")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        month_key = dt.strftime("%Y-%m")
                        amount = float(payment.get("amount", 0))
                        monthly_revenue[month_key] += amount
                        monthly_count[month_key] += 1
                    except Exception:
                        pass
            
            monthly_breakdown = [
                {
                    "month": month,
                    "revenue": round(revenue, 2),
                    "count": monthly_count[month],
                    "average": round(revenue / monthly_count[month], 2) if monthly_count[month] > 0 else 0.0
                }
                for month, revenue in sorted(monthly_revenue.items())
            ]
            
            # Weekly revenue (past 7 days)
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)
            week_ago_iso = week_ago.isoformat()
            
            weekly_revenue = sum(
                float(p.get("amount", 0))
                for p in payments
                if p.get("created_at") and p.get("created_at") >= week_ago_iso
            )
            
            # Revenue by type (appointments vs orders)
            appointment_revenue = 0.0
            order_revenue = 0.0
            
            for payment in payments:
                amount = float(payment.get("amount", 0))
                if payment.get("appointment_id"):
                    appointment_revenue += amount
                elif payment.get("order_id"):
                    order_revenue += amount
            
            analytics = {
                "total_revenue": round(total_revenue, 2),
                "total_payments": total_payments,
                "average_transaction": round(average_transaction, 2),
                "monthly_breakdown": monthly_breakdown,
                "weekly_revenue": round(weekly_revenue, 2),
                "revenue_by_type": {
                    "appointments": round(appointment_revenue, 2),
                    "orders": round(order_revenue, 2)
                },
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            }
            
            return analytics, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get revenue analytics: {str(e)}"
    
    @staticmethod
    def get_all_salons_revenue_analytics(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get comprehensive revenue analytics for all salons (admin only).
        
        Args:
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
        
        Returns:
            Tuple of (revenue_analytics_dict, error_message)
        """
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Base query for all completed payments
            query = supabase.table("payments")\
                .select("id, amount, created_at, payment_status, appointment_id, order_id, salon_id")\
                .eq("payment_status", "completed")\
                .order("created_at", desc=False)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            payments = response.data or []
            
            if not payments:
                return {
                    "total_revenue": 0.0,
                    "total_payments": 0,
                    "salon_breakdown": [],
                    "monthly_breakdown": [],
                    "revenue_by_type": {
                        "appointments": 0.0,
                        "orders": 0.0
                    }
                }, None
            
            # Get salon names
            salon_ids = list(set([p.get("salon_id") for p in payments if p.get("salon_id")]))
            salons_map = {}
            
            if salon_ids:
                salon_res = supabase.table("salons")\
                    .select("id, name")\
                    .in_("id", salon_ids)\
                    .execute()
                
                if salon_res.data:
                    salons_map = {s["id"]: s.get("name", "Unknown Salon") for s in salon_res.data}
            
            # Calculate totals
            total_revenue = sum(float(p.get("amount", 0)) for p in payments)
            total_payments = len(payments)
            
            # Revenue by salon
            salon_revenue = defaultdict(float)
            salon_count = defaultdict(int)
            
            for payment in payments:
                salon_id = payment.get("salon_id")
                if salon_id:
                    amount = float(payment.get("amount", 0))
                    salon_revenue[salon_id] += amount
                    salon_count[salon_id] += 1
            
            salon_breakdown = [
                {
                    "salon_id": salon_id,
                    "salon_name": salons_map.get(salon_id, "Unknown Salon"),
                    "revenue": round(revenue, 2),
                    "count": salon_count[salon_id],
                    "average": round(revenue / salon_count[salon_id], 2) if salon_count[salon_id] > 0 else 0.0
                }
                for salon_id, revenue in sorted(salon_revenue.items(), key=lambda x: x[1], reverse=True)
            ]
            
            # Monthly breakdown
            monthly_revenue = defaultdict(float)
            monthly_count = defaultdict(int)
            
            for payment in payments:
                created_at = payment.get("created_at")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        month_key = dt.strftime("%Y-%m")
                        amount = float(payment.get("amount", 0))
                        monthly_revenue[month_key] += amount
                        monthly_count[month_key] += 1
                    except Exception:
                        pass
            
            monthly_breakdown = [
                {
                    "month": month,
                    "revenue": round(revenue, 2),
                    "count": monthly_count[month],
                    "average": round(revenue / monthly_count[month], 2) if monthly_count[month] > 0 else 0.0
                }
                for month, revenue in sorted(monthly_revenue.items())
            ]
            
            # Revenue by type
            appointment_revenue = 0.0
            order_revenue = 0.0
            
            for payment in payments:
                amount = float(payment.get("amount", 0))
                if payment.get("appointment_id"):
                    appointment_revenue += amount
                elif payment.get("order_id"):
                    order_revenue += amount
            
            analytics = {
                "total_revenue": round(total_revenue, 2),
                "total_payments": total_payments,
                "salon_breakdown": salon_breakdown,
                "monthly_breakdown": monthly_breakdown,
                "revenue_by_type": {
                    "appointments": round(appointment_revenue, 2),
                    "orders": round(order_revenue, 2)
                },
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            }
            
            return analytics, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get all salons revenue analytics: {str(e)}"
    
    @staticmethod
    def get_payment(payment_id: str, user_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get a single payment by ID.
        
        Args:
            payment_id: Payment ID
            user_id: Optional user ID to verify ownership
        
        Returns:
            Tuple of (payment_dict, error_message)
        """
        try:
            query = supabase.table("payments")\
                .select("*, appointments:appointment_id(*), saved_payment_methods:payment_method_id(*)")\
                .eq("id", payment_id)
            
            if user_id:
                query = query.eq("user_id", user_id)
            
            response = query.single().execute()
            
            if getattr(response, "error", None) or not response.data:
                return None, "Payment not found"
            
            return response.data, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get payment: {str(e)}"

