"""
Loyalty service for managing loyalty points, balances, transactions, and redemptions.
"""
from config import supabase
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from services.audit_logging_service import AuditLoggingService
from services.error_logging_service import ErrorLoggingService
from services.payment_service import PaymentService
import uuid
import math


class LoyaltyService:
    """Service for managing loyalty program operations."""
    
    @staticmethod
    def get_loyalty_program(salon_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get loyalty program configuration for a salon.
        
        Args:
            salon_id: Salon ID
        
        Returns:
            Tuple of (loyalty_program_dict, error_message)
            Returns (None, None) if salon doesn't have a loyalty program (not an error)
        """
        try:
            response = supabase.table("loyalty_programs")\
                .select("*")\
                .eq("salon_id", salon_id)\
                .maybe_single()\
                .execute()
            
            # Handle case where response itself might be None
            if response is None:
                return None, None
            
            # Check for errors in response
            if getattr(response, "error", None):
                # If not found, return None (salon doesn't have loyalty program configured)
                error_str = str(response.error)
                if "No rows" in error_str or "PGRST116" in error_str or "0 rows" in error_str:
                    return None, None
                return None, getattr(response.error, 'message', str(response.error))
            
            # maybe_single() returns None in data if no rows found (not an error)
            if not hasattr(response, 'data') or response.data is None:
                return None, None
            
            return response.data, None
            
        except Exception as e:
            error_str = str(e)
            # Check if it's a "no rows" error - this is not a failure, just means no program exists
            if "PGRST116" in error_str or "0 rows" in error_str or "No rows" in error_str:
                return None, None
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get loyalty program: {error_str}"
    
    @staticmethod
    def create_or_update_loyalty_program(
        salon_id: str,
        points_per_dollar: float,
        discount: int,
        min_points_for_redemption: int,
        is_active: bool = True
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create or update loyalty program configuration for a salon.
        
        Args:
            salon_id: Salon ID
            points_per_dollar: Points earned per dollar spent
            discount: Discount percentage (0-100)
            min_points_for_redemption: Minimum points required to redeem
            is_active: Whether the program is active
        
        Returns:
            Tuple of (loyalty_program_dict, error_message)
        """
        try:
            # Validate inputs
            if points_per_dollar < 0:
                return None, "Points per dollar must be non-negative"
            if discount < 0 or discount > 100:
                return None, "Discount must be between 0 and 100"
            if min_points_for_redemption <= 0:
                return None, "Minimum points for redemption must be greater than 0"
            
            # Check if program exists
            existing, error = LoyaltyService.get_loyalty_program(salon_id)
            if error:
                return None, error
            
            program_data = {
                "salon_id": salon_id,
                "points_per_dollar": float(points_per_dollar),
                "discount": discount,
                "min_points_for_redemption": min_points_for_redemption,
                "is_active": is_active
            }
            
            if existing:
                # Update existing
                response = supabase.table("loyalty_programs")\
                    .update(program_data)\
                    .eq("salon_id", salon_id)\
                    .execute()
                
                if getattr(response, "error", None):
                    return None, response.error.message
                
                updated_program = response.data[0]
                
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='loyalty_programs',
                    record_id=updated_program["id"],
                    action='UPDATE',
                    old_values=existing,
                    new_values=program_data,
                    changed_by=None  # Salon owner - would need user_id from route
                )
                
                return updated_program, None
            else:
                # Create new
                program_data["id"] = str(uuid.uuid4())
                response = supabase.table("loyalty_programs")\
                    .insert(program_data)\
                    .execute()
                
                if getattr(response, "error", None):
                    return None, response.error.message
                
                created_program = response.data[0]
                
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='loyalty_programs',
                    record_id=created_program["id"],
                    action='INSERT',
                    new_values=program_data,
                    changed_by=None
                )
                
                return created_program, None
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to create/update loyalty program: {str(e)}"
    
    @staticmethod
    def get_user_loyalty_balances(user_id: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Get loyalty point balances for a user across all salons.
        
        Args:
            user_id: User ID
        
        Returns:
            Tuple of (list of balance dicts with salon info, error_message)
        """
        try:
            response = supabase.table("loyalty_balances")\
                .select("*, salons:salon_id(id, name)")\
                .eq("user_id", user_id)\
                .order("points_balance", desc=True)\
                .execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            balances = response.data or []
            
            # Format for frontend
            formatted_balances = []
            for balance in balances:
                salon = balance.get("salons")
                salon_name = salon.get("name") if isinstance(salon, dict) else "Salon"
                
                formatted_balances.append({
                    "salon_id": balance.get("salon_id"),
                    "salon_name": salon_name,
                    "balance": balance.get("points_balance", 0),
                    "lifetime_points_earned": balance.get("lifetime_points_earned", 0),
                    "lifetime_points_redeemed": balance.get("lifetime_points_redeemed", 0)
                })
            
            return formatted_balances, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get loyalty balances: {str(e)}"
    
    @staticmethod
    def get_user_loyalty_balance(user_id: str, salon_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get loyalty point balance for a user at a specific salon.
        
        Args:
            user_id: User ID
            salon_id: Salon ID
        
        Returns:
            Tuple of (balance_dict, error_message)
        """
        try:
            response = supabase.table("loyalty_balances")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("salon_id", salon_id)\
                .maybe_single()\
                .execute()
            
            print(f"[LOYALTY DEBUG] get_user_loyalty_balance: response error={getattr(response, 'error', None)}, data={response.data if hasattr(response, 'data') else None}")
            
            if getattr(response, "error", None):
                # If not found, return zero balance
                error_obj = response.error
                error_str = str(error_obj)
                error_code = getattr(error_obj, 'code', None) or (error_obj.get('code') if isinstance(error_obj, dict) else None)
                
                print(f"[LOYALTY DEBUG] get_user_loyalty_balance: Error detected: code={error_code}, str={error_str}")
                
                if error_code == "PGRST116" or "No rows" in error_str or "PGRST116" in error_str or "0 rows" in error_str:
                    print(f"[LOYALTY DEBUG] get_user_loyalty_balance: No rows found, returning fake dict")
                    return {
                        "user_id": user_id,
                        "salon_id": salon_id,
                        "points_balance": 0,
                        "lifetime_points_earned": 0,
                        "lifetime_points_redeemed": 0
                    }, None
                error_msg = getattr(error_obj, 'message', None) or (error_obj.get('message') if isinstance(error_obj, dict) else str(error_obj))
                return None, f"Failed to get loyalty balance: {error_msg}"
            
            # maybe_single() returns None in data if no rows found
            if not hasattr(response, 'data') or response.data is None:
                print(f"[LOYALTY DEBUG] get_user_loyalty_balance: No data in response, returning fake dict")
                return {
                    "user_id": user_id,
                    "salon_id": salon_id,
                    "points_balance": 0,
                    "lifetime_points_earned": 0,
                    "lifetime_points_redeemed": 0
                }, None
            
            print(f"[LOYALTY DEBUG] get_user_loyalty_balance: Found balance: {response.data}")
            return response.data, None
            
            return response.data, None
            
        except Exception as e:
            error_str = str(e)
            print(f"[LOYALTY DEBUG] get_user_loyalty_balance: Exception caught: {error_str}")
            # Check if it's a "no rows" error - this is not a failure, just means no balance exists
            if "PGRST116" in error_str or "0 rows" in error_str or "No rows" in error_str or "Cannot coerce" in error_str:
                print(f"[LOYALTY DEBUG] get_user_loyalty_balance: No rows exception, returning fake dict")
                return {
                    "user_id": user_id,
                    "salon_id": salon_id,
                    "points_balance": 0,
                    "lifetime_points_earned": 0,
                    "lifetime_points_redeemed": 0
                }, None
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get loyalty balance: {error_str}"
    
    @staticmethod
    def get_loyalty_transactions(
        user_id: str,
        salon_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get loyalty transaction history for a user.
        
        Args:
            user_id: User ID
            salon_id: Optional salon ID to filter by
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            Tuple of (list of transactions, error_message)
        """
        try:
            query = supabase.table("loyalty_transactions")\
                .select("*, salons:salon_id(name), appointments:appointment_id(id, start_at)")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .range(offset, offset + limit - 1)
            
            if salon_id:
                query = query.eq("salon_id", salon_id)
            
            response = query.execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            transactions = response.data or []
            
            # Format for frontend
            formatted_transactions = []
            for trans in transactions:
                salon = trans.get("salons")
                appointment = trans.get("appointments")
                
                formatted_transactions.append({
                    "id": trans.get("id"),
                    "salon_id": trans.get("salon_id"),
                    "salon_name": salon.get("name") if isinstance(salon, dict) else None,
                    "points": trans.get("points"),
                    "transaction_type": trans.get("transaction_type"),
                    "description": trans.get("description"),
                    "date": trans.get("created_at"),
                    "appointment_id": appointment.get("id") if isinstance(appointment, dict) else None,
                    "balance_after": trans.get("balance_after")
                })
            
            return formatted_transactions, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get loyalty transactions: {str(e)}"
    
    @staticmethod
    def _get_or_create_balance(user_id: str, salon_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get or create a loyalty balance record for a user at a salon.
        
        Args:
            user_id: User ID
            salon_id: Salon ID
        
        Returns:
            Tuple of (balance_dict, error_message)
        """
        try:
            print(f"[LOYALTY DEBUG] _get_or_create_balance: user_id={user_id}, salon_id={salon_id}")
            balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
            print(f"[LOYALTY DEBUG] _get_or_create_balance: get_user_loyalty_balance returned: balance={balance is not None}, has_id={balance.get('id') if balance else False}, error={error}")
            if error:
                print(f"[LOYALTY DEBUG] _get_or_create_balance: ERROR: {error}")
                return None, error
            
            # Check if balance actually exists in database (has an id)
            # get_user_loyalty_balance returns a fake dict with zeros if no record exists
            if balance and balance.get("id"):
                print(f"[LOYALTY DEBUG] _get_or_create_balance: Balance exists with id={balance.get('id')}, returning it")
                # Real balance record exists
                return balance, None
            
            # No balance record exists - create one
            print(f"[LOYALTY DEBUG] _get_or_create_balance: No balance exists, creating new one...")
            balance_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "salon_id": salon_id,
                "points_balance": 0,
                "lifetime_points_earned": 0,
                "lifetime_points_redeemed": 0
            }
            
            print(f"[LOYALTY DEBUG] _get_or_create_balance: Inserting balance: {balance_data}")
            response = supabase.table("loyalty_balances")\
                .insert(balance_data)\
                .execute()
            
            print(f"[LOYALTY DEBUG] _get_or_create_balance: Insert response: error={getattr(response, 'error', None)}, data={response.data if hasattr(response, 'data') else None}")
            
            if getattr(response, "error", None):
                print(f"[LOYALTY DEBUG] _get_or_create_balance: Insert ERROR: {response.error.message}")
                return None, response.error.message
            
            print(f"[LOYALTY DEBUG] _get_or_create_balance: ✓ Successfully created balance with id={response.data[0].get('id')}")
            return response.data[0], None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get or create balance: {str(e)}"
    
    @staticmethod
    def earn_points(
        user_id: str,
        salon_id: str,
        points: int,
        appointment_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Award loyalty points to a user.
        
        Args:
            user_id: User ID
            salon_id: Salon ID
            points: Points to award (must be positive)
            appointment_id: Optional appointment ID that earned the points
            payment_id: Optional payment ID
            description: Optional description
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            print(f"[LOYALTY DEBUG] earn_points called: user_id={user_id}, salon_id={salon_id}, points={points}")
            if points <= 0:
                print(f"[LOYALTY DEBUG] earn_points: Points must be positive, returning False")
                return False, "Points must be positive"
            
            # Get or create balance
            print(f"[LOYALTY DEBUG] earn_points: Getting or creating balance...")
            balance, error = LoyaltyService._get_or_create_balance(user_id, salon_id)
            print(f"[LOYALTY DEBUG] earn_points: _get_or_create_balance returned: balance={balance is not None}, has_id={balance.get('id') if balance else False}, error={error}")
            if error:
                print(f"[LOYALTY DEBUG] earn_points: ERROR getting balance: {error}")
                return False, error
            
            old_balance = balance.get("points_balance", 0)
            new_balance = old_balance + points
            balance_id = balance.get("id")
            
            print(f"[LOYALTY DEBUG] earn_points: Updating balance: id={balance_id}, old_balance={old_balance}, new_balance={new_balance}")
            
            # Update balance
            update_response = supabase.table("loyalty_balances")\
                .update({
                    "points_balance": new_balance,
                    "lifetime_points_earned": balance.get("lifetime_points_earned", 0) + points,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })\
                .eq("id", balance_id)\
                .execute()
            
            print(f"[LOYALTY DEBUG] earn_points: Update response: error={getattr(update_response, 'error', None)}, data={update_response.data if hasattr(update_response, 'data') else None}")
            
            if getattr(update_response, "error", None):
                print(f"[LOYALTY DEBUG] earn_points: Update ERROR: {update_response.error.message}")
                return False, update_response.error.message
            
            # Create transaction record
            transaction_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "salon_id": salon_id,
                "transaction_type": "earned",
                "points": points,
                "appointment_id": appointment_id,
                "payment_id": payment_id,
                "description": description or f"Earned {points} points",
                "balance_after": new_balance
            }
            
            trans_response = supabase.table("loyalty_transactions")\
                .insert(transaction_data)\
                .execute()
            
            if getattr(trans_response, "error", None):
                # Rollback balance update if transaction creation fails
                supabase.table("loyalty_balances")\
                    .update({
                        "points_balance": old_balance,
                        "lifetime_points_earned": balance.get("lifetime_points_earned", 0)
                    })\
                    .eq("id", balance["id"])\
                    .execute()
                return False, trans_response.error.message
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to earn points: {str(e)}"
    
    @staticmethod
    def redeem_points(
        user_id: str,
        salon_id: str,
        points_to_redeem: int,
        payment_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Redeem loyalty points (deduct from balance).
        
        Args:
            user_id: User ID
            salon_id: Salon ID
            points_to_redeem: Points to redeem (must be positive, will be stored as negative)
            payment_id: Optional payment ID where points were redeemed
            description: Optional description
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if points_to_redeem <= 0:
                return False, "Points to redeem must be positive"
            
            # Get balance
            balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
            if error:
                return False, error
            
            if not balance:
                balance, error = LoyaltyService._get_or_create_balance(user_id, salon_id)
                if error:
                    return False, error
            
            current_balance = balance.get("points_balance", 0)
            
            if current_balance < points_to_redeem:
                return False, f"Insufficient points. Current balance: {current_balance}, required: {points_to_redeem}"
            
            new_balance = current_balance - points_to_redeem
            
            # Update balance
            update_response = supabase.table("loyalty_balances")\
                .update({
                    "points_balance": new_balance,
                    "lifetime_points_redeemed": balance.get("lifetime_points_redeemed", 0) + points_to_redeem,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })\
                .eq("id", balance["id"])\
                .execute()
            
            if getattr(update_response, "error", None):
                return False, update_response.error.message
            
            # Create transaction record (negative points)
            transaction_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "salon_id": salon_id,
                "transaction_type": "redeemed",
                "points": -points_to_redeem,  # Negative for redeemed
                "payment_id": payment_id,
                "description": description or f"Redeemed {points_to_redeem} points",
                "balance_after": new_balance
            }
            
            trans_response = supabase.table("loyalty_transactions")\
                .insert(transaction_data)\
                .execute()
            
            if getattr(trans_response, "error", None):
                # Rollback balance update if transaction creation fails
                supabase.table("loyalty_balances")\
                    .update({
                        "points_balance": current_balance,
                        "lifetime_points_redeemed": balance.get("lifetime_points_redeemed", 0)
                    })\
                    .eq("id", balance["id"])\
                    .execute()
                return False, trans_response.error.message
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to redeem points: {str(e)}"
    
    @staticmethod
    def calculate_points_earned(payment_amount: float, points_per_dollar: float) -> int:
        """
        Calculate points earned from a payment amount.
        
        Args:
            payment_amount: Payment amount (after discounts)
            points_per_dollar: Points per dollar rate
        
        Returns:
            Points earned (rounded down)
        """
        return math.floor(payment_amount * points_per_dollar)
    
    @staticmethod
    def calculate_redemption_discount(
        appointment_amount: float,
        discount_percent: int
    ) -> float:
        """
        Calculate discount amount from redemption.
        
        Args:
            appointment_amount: Original appointment amount
            discount_percent: Discount percentage (0-100)
        
        Returns:
            Discount amount
        """
        return round(appointment_amount * (discount_percent / 100.0), 2)
    
    @staticmethod
    def process_appointment_payment_with_loyalty(
        user_id: str,
        appointment_id: str,
        payment_amount: float,
        payment_method_id: Optional[str] = None,
        card_number: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        cvv: Optional[str] = None,
        cardholder_name: Optional[str] = None,
        billing_address: Optional[Dict] = None,
        save_payment_method: bool = False,
        redeem_loyalty_points: bool = False
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Process payment for an appointment with loyalty points handling.
        This is the main method that handles both payment and loyalty logic.
        
        Args:
            user_id: User ID
            appointment_id: Appointment ID
            payment_amount: Original payment amount (before discounts)
            payment_method_id: Optional saved payment method ID
            card_number: Optional new card number
            exp_month: Optional expiration month
            exp_year: Optional expiration year
            cvv: Optional CVV
            cardholder_name: Optional cardholder name
            billing_address: Optional billing address
            save_payment_method: Whether to save the new card
            redeem_loyalty_points: Whether to redeem loyalty points for discount
        
        Returns:
            Tuple of (payment_dict with loyalty info, error_message)
        """
        try:
            # Get appointment
            appt_response = supabase.table("appointments")\
                .select("id, customer_id, salon_id, service_id, status")\
                .eq("id", appointment_id)\
                .single()\
                .execute()
            
            if getattr(appt_response, "error", None) or not appt_response.data:
                return None, "Appointment not found"
            
            appointment = appt_response.data
            salon_id = appointment["salon_id"]
            
            # Verify appointment belongs to user
            if appointment["customer_id"] != user_id:
                return None, "Appointment does not belong to user"
            
            # Get loyalty program
            print(f"[LOYALTY DEBUG] Getting loyalty program for salon_id: {salon_id}")
            loyalty_program, error = LoyaltyService.get_loyalty_program(salon_id)
            print(f"[LOYALTY DEBUG] get_loyalty_program returned: program={loyalty_program is not None}, error={error}")
            if error:
                print(f"[LOYALTY DEBUG] ERROR getting loyalty program: {error}")
                ErrorLoggingService.log_exception(
                    Exception(f"Error getting loyalty program for salon {salon_id}: {error}"),
                    severity='medium'
                )
                return None, error
            
            # Log loyalty program status for debugging
            if loyalty_program:
                print(f"[LOYALTY DEBUG] Loyalty program found: is_active={loyalty_program.get('is_active')}, points_per_dollar={loyalty_program.get('points_per_dollar')}, discount={loyalty_program.get('discount')}")
                ErrorLoggingService.log_exception(
                    Exception(f"Loyalty program found for salon {salon_id}: is_active={loyalty_program.get('is_active')}, points_per_dollar={loyalty_program.get('points_per_dollar')}"),
                    severity='low'
                )
            else:
                print(f"[LOYALTY DEBUG] NO LOYALTY PROGRAM FOUND for salon {salon_id}")
                ErrorLoggingService.log_exception(
                    Exception(f"No loyalty program found for salon {salon_id}"),
                    severity='low'
                )
            
            # Handle loyalty redemption
            loyalty_points_used = 0
            discount_applied = 0.0
            final_amount = payment_amount
            
            if redeem_loyalty_points and loyalty_program and loyalty_program.get("is_active"):
                # Get user balance
                balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
                if error:
                    return None, error
                
                if not balance:
                    balance, error = LoyaltyService._get_or_create_balance(user_id, salon_id)
                    if error:
                        return None, error
                
                min_points = loyalty_program.get("min_points_for_redemption", 100)
                current_balance = balance.get("points_balance", 0)
                
                if current_balance >= min_points:
                    # Calculate discount
                    discount_percent = loyalty_program.get("discount", 10)
                    discount_applied = LoyaltyService.calculate_redemption_discount(
                        payment_amount,
                        discount_percent
                    )
                    final_amount = payment_amount - discount_applied
                    loyalty_points_used = min_points
                else:
                    return None, f"Insufficient points. Need {min_points}, have {current_balance}"
            
            # Create payment
            payment, error = PaymentService.create_payment(
                user_id=user_id,
                appointment_id=appointment_id,
                amount=final_amount,
                payment_method_id=payment_method_id,
                card_number=card_number,
                exp_month=exp_month,
                exp_year=exp_year,
                cvv=cvv,
                cardholder_name=cardholder_name,
                billing_address=billing_address,
                save_payment_method=save_payment_method,
                loyalty_points_used=loyalty_points_used,
                discount_applied=discount_applied
            )
            
            if error:
                return None, error
            
            # Redeem points if used
            if loyalty_points_used > 0:
                success, error = LoyaltyService.redeem_points(
                    user_id=user_id,
                    salon_id=salon_id,
                    points_to_redeem=loyalty_points_used,
                    payment_id=payment["id"],
                    description=f"Redeemed {loyalty_points_used} points for {loyalty_program.get('discount', 10)}% discount"
                )
                
                if not success:
                    # Payment was created but points redemption failed
                    # This is a partial failure - payment exists but points weren't deducted
                    # In production, you might want to refund or handle this differently
                    ErrorLoggingService.log_exception(
                        Exception(f"Payment created but points redemption failed: {error}"),
                        severity='high'
                    )
                    return None, f"Payment created but points redemption failed: {error}"
            
            # Award loyalty points when payment is completed (not when appointment is completed)
            # Only award if loyalty program is active and no points were redeemed (can't earn and redeem in same transaction)
            print(f"[LOYALTY DEBUG] Checking if points should be awarded: loyalty_program={loyalty_program is not None}, is_active={loyalty_program.get('is_active') if loyalty_program else 'N/A'}, loyalty_points_used={loyalty_points_used}")
            
            if loyalty_program and loyalty_program.get("is_active") and loyalty_points_used == 0:
                points_per_dollar = float(loyalty_program.get("points_per_dollar", 1.0))
                points_earned = LoyaltyService.calculate_points_earned(final_amount, points_per_dollar)
                
                print(f"[LOYALTY DEBUG] Points calculation: final_amount={final_amount}, points_per_dollar={points_per_dollar}, points_earned={points_earned}")
                
                # Log for debugging
                ErrorLoggingService.log_exception(
                    Exception(f"Loyalty points calculation: final_amount={final_amount}, points_per_dollar={points_per_dollar}, points_earned={points_earned}, appointment_id={appointment_id}, salon_id={salon_id}, user_id={user_id}"),
                    severity='low'
                )
                
                if points_earned > 0:
                    # Check if points were already awarded (shouldn't happen, but safety check)
                    existing_trans = supabase.table("loyalty_transactions")\
                        .select("id")\
                        .eq("appointment_id", appointment_id)\
                        .eq("transaction_type", "earned")\
                        .execute()
                    
                    print(f"[LOYALTY DEBUG] Existing transactions check: {len(existing_trans.data) if existing_trans.data else 0} found")
                    
                    if not existing_trans.data:
                        # Award points now (when payment is completed)
                        print(f"[LOYALTY DEBUG] CALLING earn_points: user_id={user_id}, salon_id={salon_id}, points={points_earned}, appointment_id={appointment_id}")
                        ErrorLoggingService.log_exception(
                            Exception(f"Attempting to award {points_earned} points to user {user_id} for salon {salon_id}, appointment {appointment_id}"),
                            severity='low'
                        )
                        earn_success, earn_error = LoyaltyService.earn_points(
                            user_id=user_id,
                            salon_id=salon_id,
                            points=points_earned,
                            appointment_id=appointment_id,
                            payment_id=payment["id"],
                            description=f"Earned {points_earned} points from appointment payment"
                        )
                        print(f"[LOYALTY DEBUG] earn_points returned: success={earn_success}, error={earn_error}")
                        if earn_success:
                            print(f"[LOYALTY DEBUG] ✓ SUCCESS: Points awarded successfully!")
                            ErrorLoggingService.log_exception(
                                Exception(f"Successfully awarded {points_earned} points to user {user_id} for salon {salon_id}"),
                                severity='low'
                            )
                        else:
                            print(f"[LOYALTY DEBUG] ✗ FAILED: {earn_error}")
                            # Log but don't fail payment
                            ErrorLoggingService.log_exception(
                                Exception(f"Failed to award loyalty points: {earn_error}"),
                                severity='high'
                            )
                    else:
                        print(f"[LOYALTY DEBUG] Points already awarded, skipping")
                        ErrorLoggingService.log_exception(
                            Exception(f"Points already awarded for appointment {appointment_id}"),
                            severity='low'
                        )
                else:
                    print(f"[LOYALTY DEBUG] No points earned (points_earned={points_earned})")
                    # Log why points weren't earned
                    ErrorLoggingService.log_exception(
                        Exception(f"No points earned: final_amount={final_amount}, points_per_dollar={points_per_dollar}, calculated={points_earned}"),
                        severity='low'
                    )
            else:
                # Log why points weren't awarded
                reason = []
                if not loyalty_program:
                    reason.append("no loyalty program")
                elif not loyalty_program.get("is_active"):
                    reason.append(f"program not active (is_active={loyalty_program.get('is_active')})")
                if loyalty_points_used > 0:
                    reason.append(f"points were redeemed ({loyalty_points_used})")
                print(f"[LOYALTY DEBUG] Points NOT awarded: {', '.join(reason) if reason else 'unknown'}")
                ErrorLoggingService.log_exception(
                    Exception(f"Loyalty points not awarded: {', '.join(reason) if reason else 'unknown'}, appointment_id={appointment_id}, salon_id={salon_id}, user_id={user_id}"),
                    severity='low'
                )
            
            return payment, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to process payment with loyalty: {str(e)}"
    
    @staticmethod
    def award_points_for_completed_appointment(appointment_id: str) -> Tuple[bool, Optional[str]]:
        """
        Award loyalty points when an appointment is marked as completed.
        This should be called when appointment status changes to "completed".
        
        Args:
            appointment_id: Appointment ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get appointment
            appt_response = supabase.table("appointments")\
                .select("id, customer_id, salon_id, service_id, status")\
                .eq("id", appointment_id)\
                .single()\
                .execute()
            
            if getattr(appt_response, "error", None) or not appt_response.data:
                return False, "Appointment not found"
            
            appointment = appt_response.data
            
            if appointment["status"] != "completed":
                return False, "Appointment must be completed to earn points"
            
            user_id = appointment["customer_id"]
            salon_id = appointment["salon_id"]
            
            # Get payment for this appointment
            payment_response = supabase.table("payments")\
                .select("id, amount, payment_status")\
                .eq("appointment_id", appointment_id)\
                .eq("payment_status", "completed")\
                .single()\
                .execute()
            
            if getattr(payment_response, "error", None) or not payment_response.data:
                return False, "No paid payment found for this appointment"
            
            payment = payment_response.data
            payment_amount = float(payment.get("amount", 0))
            
            # Check if points were already awarded (check for existing transaction)
            existing_trans = supabase.table("loyalty_transactions")\
                .select("id")\
                .eq("appointment_id", appointment_id)\
                .eq("transaction_type", "earned")\
                .execute()
            
            if existing_trans.data:
                # Points already awarded
                return True, None
            
            # Get loyalty program
            loyalty_program, error = LoyaltyService.get_loyalty_program(salon_id)
            if error:
                return False, error
            
            if not loyalty_program or not loyalty_program.get("is_active"):
                # No loyalty program or inactive - no points awarded
                return True, None
            
            # Calculate points
            points_per_dollar = float(loyalty_program.get("points_per_dollar", 1.0))
            points_earned = LoyaltyService.calculate_points_earned(payment_amount, points_per_dollar)
            
            if points_earned <= 0:
                return True, None  # No points to award
            
            # Award points
            success, error = LoyaltyService.earn_points(
                user_id=user_id,
                salon_id=salon_id,
                points=points_earned,
                appointment_id=appointment_id,
                payment_id=payment["id"],
                description=f"Earned {points_earned} points from completed appointment"
            )
            
            return success, error
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to award points for appointment: {str(e)}"

