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
                
                # Format description to remove UUID and show appointment date if available
                description = trans.get("description", "")
                appointment_date = None
                if isinstance(appointment, dict) and appointment.get("start_at"):
                    try:
                        appt_date_str = appointment["start_at"]
                        if appt_date_str:
                            # Handle ISO format with or without timezone
                            if appt_date_str.endswith("Z"):
                                appt_date_str = appt_date_str[:-1] + "+00:00"
                            appt_date = datetime.fromisoformat(appt_date_str)
                            appointment_date = appt_date.strftime("%b %d, %Y")
                    except Exception:
                        pass
                
                # Clean up description - remove UUID references and add appointment date
                if "original transaction:" in description.lower() and appointment_date:
                    # For no-show removals, show appointment date instead of UUID
                    description = f"Points removed due to no-show (appointment on {appointment_date})"
                elif "original transaction:" in description.lower():
                    # If no appointment date, just remove the UUID part
                    description = description.split("(original transaction:")[0].strip()
                    if description.endswith(")"):
                        description = description[:-1].strip()
                
                formatted_transactions.append({
                    "id": trans.get("id"),
                    "salon_id": trans.get("salon_id"),
                    "salon_name": salon.get("name") if isinstance(salon, dict) else None,
                    "points": trans.get("points"),
                    "transaction_type": trans.get("transaction_type"),
                    "description": description,
                    "date": trans.get("created_at"),
                    "appointment_id": trans.get("appointment_id"),
                    "appointment_date": appointment_date,
                    "balance_after": trans.get("balance_after"),
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
        order_id: Optional[str] = None,
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
            order_id: Optional order ID that earned the points
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
                "balance_after": new_balance,
                "description": description or f"Earned {points} points"
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
    def remove_points_for_no_show(
        user_id: str,
        salon_id: str,
        points: int,
        appointment_id: str,
        description: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Remove loyalty points that were awarded for an appointment that was marked as no-show.
        
        Args:
            user_id: User ID
            salon_id: Salon ID
            points: Points to remove (must be positive)
            appointment_id: Appointment ID that the points were awarded for
            description: Optional description
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if points <= 0:
                return False, "Points to remove must be positive"
            
            # Get balance
            balance, error = LoyaltyService._get_or_create_balance(user_id, salon_id)
            if error:
                return False, error
            
            old_balance = balance.get("points_balance", 0)
            # Don't allow negative balance
            new_balance = max(0, old_balance - points)
            balance_id = balance.get("id")
            
            # Update balance (don't modify lifetime_points_earned - we're just removing from current balance)
            update_response = supabase.table("loyalty_balances")\
                .update({
                    "points_balance": new_balance,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })\
                .eq("id", balance_id)\
                .execute()
            
            if getattr(update_response, "error", None):
                return False, update_response.error.message
            
            # Create transaction record for the removal
            # Use "redeemed" transaction type since "removed" may not be a valid enum
            # The description will indicate it's a no-show removal
            transaction_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "salon_id": salon_id,
                "transaction_type": "redeemed",  # Using "redeemed" as it's a valid type
                "points": -points,  # Negative to indicate removal
                "appointment_id": appointment_id,
                "balance_after": new_balance,
                "description": description or f"Removed {points} points due to no-show"
            }
            
            trans_response = supabase.table("loyalty_transactions")\
                .insert(transaction_data)\
                .execute()
            
            if getattr(trans_response, "error", None):
                # Rollback balance update if transaction creation fails
                supabase.table("loyalty_balances")\
                    .update({
                        "points_balance": old_balance,
                    })\
                    .eq("id", balance_id)\
                    .execute()
                return False, trans_response.error.message
            
            return True, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to remove points: {str(e)}"
    
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
                "balance_after": new_balance,
                "description": description or f"Redeemed {points_to_redeem} points"
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
    def calculate_potential_points(
        amount: float,
        salon_id: str
    ) -> Tuple[int, Optional[str]]:
        """
        Calculate potential loyalty points that would be earned for a given amount.
        This is used to show customers how many points they'll earn.
        
        Args:
            amount: Payment amount
            salon_id: Salon ID
        
        Returns:
            Tuple of (points, error_message)
        """
        try:
            loyalty_program, error = LoyaltyService.get_loyalty_program(salon_id)
            if error:
                return 0, error
            
            if not loyalty_program or not loyalty_program.get("is_active"):
                return 0, None  # No program or inactive - no points
            
            points_per_dollar = float(loyalty_program.get("points_per_dollar", 1.0))
            points = LoyaltyService.calculate_points_earned(amount, points_per_dollar)
            
            return points, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='low')
            return 0, str(e)
    
    @staticmethod
    def get_loyalty_usage_analytics(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get loyalty program usage statistics across all salons (admin only).
        
        Args:
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
        
        Returns:
            Tuple of (usage_analytics_dict, error_message)
        """
        try:
            from collections import defaultdict
            
            # Get all loyalty programs
            programs_res = supabase.table("loyalty_programs")\
                .select("id, salon_id, is_active, points_per_dollar, reward_threshold, reward_discount_percent")\
                .execute()
            
            if getattr(programs_res, "error", None):
                return None, programs_res.error.message
            
            programs = programs_res.data or []
            salon_programs = {p["salon_id"]: p for p in programs if p.get("is_active")}
            
            # Get salon names
            salon_ids = list(salon_programs.keys())
            salons_map = {}
            
            if salon_ids:
                salon_res = supabase.table("salons")\
                    .select("id, name")\
                    .in_("id", salon_ids)\
                    .execute()
                
                if salon_res.data:
                    salons_map = {s["id"]: s.get("name", "Unknown Salon") for s in salon_res.data}
            
            # Get all loyalty transactions
            query = supabase.table("loyalty_transactions")\
                .select("id, user_id, salon_id, transaction_type, points, created_at")\
                .order("created_at", desc=False)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            trans_res = query.execute()
            
            if getattr(trans_res, "error", None):
                return None, trans_res.error.message
            
            transactions = trans_res.data or []
            
            # Get all loyalty balances
            balances_res = supabase.table("loyalty_balances")\
                .select("user_id, salon_id, points_balance")\
                .execute()
            
            balances = balances_res.data or [] if not getattr(balances_res, "error", None) else []
            
            # Calculate statistics
            total_transactions = len(transactions)
            total_points_earned = sum(
                abs(int(t.get("points", 0))) 
                for t in transactions 
                if t.get("transaction_type") == "earned"
            )
            total_points_redeemed = sum(
                abs(int(t.get("points", 0))) 
                for t in transactions 
                if t.get("transaction_type") == "redeemed"
            )
            total_points_expired = sum(
                abs(int(t.get("points", 0))) 
                for t in transactions 
                if t.get("transaction_type") == "expired"
            )
            
            # Current total balances
            total_current_balance = sum(float(b.get("points_balance", 0)) for b in balances)
            
            # Statistics by salon
            salon_stats = defaultdict(lambda: {
                "salon_name": "",
                "program_active": False,
                "transactions": 0,
                "points_earned": 0,
                "points_redeemed": 0,
                "points_expired": 0,
                "current_balance": 0,
                "active_users": set()
            })
            
            for transaction in transactions:
                salon_id = transaction.get("salon_id")
                if salon_id:
                    stats = salon_stats[salon_id]
                    stats["transactions"] += 1
                    stats["active_users"].add(transaction.get("user_id"))
                    
                    trans_type = transaction.get("transaction_type")
                    points = abs(int(transaction.get("points", 0)))
                    
                    if trans_type == "earned":
                        stats["points_earned"] += points
                    elif trans_type == "redeemed":
                        stats["points_redeemed"] += points
                    elif trans_type == "expired":
                        stats["points_expired"] += points
            
            for balance in balances:
                salon_id = balance.get("salon_id")
                if salon_id and salon_id in salon_stats:
                    salon_stats[salon_id]["current_balance"] += float(balance.get("points_balance", 0))
            
            # Format salon breakdown
            salon_breakdown = []
            for salon_id, stats in salon_stats.items():
                program = salon_programs.get(salon_id, {})
                salon_breakdown.append({
                    "salon_id": salon_id,
                    "salon_name": salons_map.get(salon_id, "Unknown Salon"),
                    "program_active": program.get("is_active", False),
                    "points_per_dollar": program.get("points_per_dollar", 0),
                    "reward_threshold": program.get("reward_threshold", 0),
                    "reward_discount": program.get("reward_discount_percent", 0),
                    "transactions": stats["transactions"],
                    "points_earned": stats["points_earned"],
                    "points_redeemed": stats["points_redeemed"],
                    "points_expired": stats["points_expired"],
                    "current_balance": round(stats["current_balance"], 0),
                    "active_users": len(stats["active_users"])
                })
            
            salon_breakdown.sort(key=lambda x: x["points_earned"], reverse=True)
            
            # Get unique users
            unique_users = len(set(t.get("user_id") for t in transactions if t.get("user_id")))
            
            analytics = {
                "total_programs": len(salon_programs),
                "total_transactions": total_transactions,
                "total_points_earned": total_points_earned,
                "total_points_redeemed": total_points_redeemed,
                "total_points_expired": total_points_expired,
                "total_current_balance": round(total_current_balance, 0),
                "unique_users": unique_users,
                "salon_breakdown": salon_breakdown,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            }
            
            return analytics, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to get loyalty usage analytics: {str(e)}"
    
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
        redeem_loyalty_points: bool = False,
        promotion_id: Optional[str] = None
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
            
            # Handle promotion discount first
            promotion_discount = 0.0
            if promotion_id:
                from services.promotion_service import PromotionService
                # Check if user is eligible for this promotion (must be in promotional_recipients)
                # Filter by context: appointments for appointment payments
                promotions, error = PromotionService.get_active_promotions(salon_id, payment_amount, user_id=user_id, context="appointments")
                if error:
                    return None, f"Failed to validate promotion: {error}"
                
                promotion = next((p for p in promotions if p["id"] == promotion_id), None)
                if not promotion:
                    return None, "Promotion not found, not active, or you are not eligible for this promotion"
                
                promotion_discount = PromotionService.calculate_discount(promotion, payment_amount)
            
            # Handle loyalty redemption
            loyalty_points_used = 0
            loyalty_discount = 0.0
            final_amount = payment_amount - promotion_discount
            
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
                    # Calculate discount on amount after promotion discount
                    discount_percent = loyalty_program.get("discount", 10)
                    loyalty_discount = LoyaltyService.calculate_redemption_discount(
                        final_amount,  # Apply loyalty discount to amount after promotion
                        discount_percent
                    )
                    final_amount = final_amount - loyalty_discount
                    loyalty_points_used = min_points
                else:
                    return None, f"Insufficient points. Need {min_points}, have {current_balance}"
            
            # Total discount is promotion + loyalty
            total_discount = promotion_discount + loyalty_discount
            
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
                discount_applied=total_discount
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
            
            # Note: Loyalty points are now awarded when appointment is marked as "completed",
            # not when payment is processed. This prevents the exploit where customers can
            # cancel appointments after redeeming points.
            
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
            
            # Check if points were already awarded and NOT removed
            # We need to check if there's a valid "earned" transaction that hasn't been fully reversed
            existing_earned = supabase.table("loyalty_transactions")\
                .select("id, points")\
                .eq("appointment_id", appointment_id)\
                .eq("transaction_type", "earned")\
                .execute()
            
            # Check for removed points (stored as "redeemed" transactions with no-show in description)
            existing_removed = supabase.table("loyalty_transactions")\
                .select("id, points, description")\
                .eq("appointment_id", appointment_id)\
                .eq("transaction_type", "redeemed")\
                .ilike("description", "%no-show%")\
                .execute()  # Only count no-show removals, not regular redemptions
            
            # Calculate net points: earned - removed
            earned_points = sum([t.get("points", 0) for t in (existing_earned.data or [])])
            removed_points = abs(sum([t.get("points", 0) for t in (existing_removed.data or [])]))  # removed points are negative, so abs()
            
            # Track original points amount for re-awarding if needed
            original_points_amount = earned_points if earned_points > 0 else None
            
            # If points were already awarded and not fully removed, don't award again
            net_points = earned_points - removed_points
            if net_points > 0:
                # Points already awarded and still valid (not fully removed)
                # This prevents duplicate awards
                return True, None
            
            # If net_points <= 0, it means either:
            # 1. No points were ever awarded (earned_points == 0)
            # 2. All points were removed (removed_points >= earned_points)
            # In both cases, we need to award points (either initial or re-award)
            
            # Get loyalty program
            loyalty_program, error = LoyaltyService.get_loyalty_program(salon_id)
            if error:
                return False, error
            
            if not loyalty_program or not loyalty_program.get("is_active"):
                # No loyalty program or inactive - no points awarded
                return True, None
            
            # Calculate points
            points_per_dollar = float(loyalty_program.get("points_per_dollar", 1.0))
            calculated_points = LoyaltyService.calculate_points_earned(payment_amount, points_per_dollar)
            
            if calculated_points <= 0:
                return True, None  # No points to award
            
            # Determine points to award:
            # - If there were original points that were removed, re-award the same amount
            # - Otherwise, award the calculated amount
            if original_points_amount and original_points_amount > 0 and removed_points >= original_points_amount:
                # Re-awarding after no-show was reversed
                points_earned = original_points_amount
                description_suffix = " (re-awarded after no-show reversal)"
            else:
                # Initial award
                points_earned = calculated_points
                description_suffix = ""
            
            # Award points (this will create a new "earned" transaction)
            # If points were previously removed, this effectively re-awards them
            success, error = LoyaltyService.earn_points(
                user_id=user_id,
                salon_id=salon_id,
                points=points_earned,
                appointment_id=appointment_id,
                payment_id=payment["id"],
                description=f"Earned {points_earned} points from completed appointment{description_suffix}"
            )
            
            return success, error
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to award points for appointment: {str(e)}"
    
    @staticmethod
    def award_points_for_delivered_order(order_id: str) -> Tuple[bool, Optional[str]]:
        """
        Award loyalty points when an order is marked as delivered.
        This should be called when order status changes to "delivered".
        
        Args:
            order_id: Order ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get order
            order_response = supabase.table("orders")\
                .select("id, user_id, salon_id, order_status, total_amount")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            if getattr(order_response, "error", None) or not order_response.data:
                return False, "Order not found"
            
            order = order_response.data
            
            if order["order_status"] != "delivered":
                return False, "Order must be delivered to earn points"
            
            user_id = order["user_id"]
            salon_id = order["salon_id"]
            order_amount = float(order.get("total_amount", 0))
            
            # Get payment for this order
            payment_response = supabase.table("payments")\
                .select("id, amount, payment_status")\
                .eq("order_id", order_id)\
                .eq("payment_status", "completed")\
                .maybe_single()\
                .execute()
            
            if getattr(payment_response, "error", None) or not payment_response.data:
                return False, "No paid payment found for this order"
            
            payment = payment_response.data
            payment_amount = float(payment.get("amount", 0))
            
            # Check if points were already awarded (using payment_id)
            existing_trans = supabase.table("loyalty_transactions")\
                .select("id")\
                .eq("payment_id", payment["id"])\
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
            
            # Calculate points (use payment amount, which may have discounts applied)
            points_per_dollar = float(loyalty_program.get("points_per_dollar", 1.0))
            points_earned = LoyaltyService.calculate_points_earned(payment_amount, points_per_dollar)
            
            if points_earned <= 0:
                return True, None  # No points to award
            
            # Award points
            success, error = LoyaltyService.earn_points(
                user_id=user_id,
                salon_id=salon_id,
                points=points_earned,
                payment_id=payment["id"],
                description=f"Earned {points_earned} points from delivered order"
            )
            
            return success, error
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, f"Failed to award points for order: {str(e)}"
    
    @staticmethod
    def process_order_payment_with_loyalty(
        user_id: str,
        order_id: str,
        payment_amount: float,
        payment_method_id: Optional[str] = None,
        card_number: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        cvv: Optional[str] = None,
        cardholder_name: Optional[str] = None,
        billing_address: Optional[Dict] = None,
        save_payment_method: bool = False,
        redeem_loyalty_points: bool = False,
        promotion_id: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Process payment for an order with loyalty points handling.
        
        Args:
            user_id: User ID
            order_id: Order ID
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
            # Get order
            order_response = supabase.table("orders")\
                .select("id, user_id, salon_id, order_status")\
                .eq("id", order_id)\
                .single()\
                .execute()
            
            if getattr(order_response, "error", None) or not order_response.data:
                return None, "Order not found"
            
            order = order_response.data
            salon_id = order["salon_id"]
            
            # Verify order belongs to user
            if order["user_id"] != user_id:
                return None, "Order does not belong to user"
            
            # Get loyalty program
            loyalty_program, error = LoyaltyService.get_loyalty_program(salon_id)
            if error:
                return None, error
            
            # Handle promotion discount first
            promotion_discount = 0.0
            if promotion_id:
                from services.promotion_service import PromotionService
                # Check if user is eligible for this promotion (must be in promotional_recipients)
                # Filter by context: products for order payments
                promotions, error = PromotionService.get_active_promotions(salon_id, payment_amount, user_id=user_id, context="products")
                if error:
                    return None, f"Failed to validate promotion: {error}"
                
                promotion = next((p for p in promotions if p["id"] == promotion_id), None)
                if not promotion:
                    return None, "Promotion not found, not active, or you are not eligible for this promotion"
                
                promotion_discount = PromotionService.calculate_discount(promotion, payment_amount)
            
            # Handle loyalty redemption
            loyalty_points_used = 0
            loyalty_discount = 0.0
            final_amount = payment_amount - promotion_discount
            
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
                    # Calculate discount on amount after promotion discount
                    discount_percent = loyalty_program.get("discount", 10)
                    loyalty_discount = LoyaltyService.calculate_redemption_discount(
                        final_amount,  # Apply loyalty discount to amount after promotion
                        discount_percent
                    )
                    final_amount = final_amount - loyalty_discount
                    loyalty_points_used = min_points
                else:
                    return None, f"Insufficient points. Need {min_points}, have {current_balance}"
            
            # Total discount is promotion + loyalty
            total_discount = promotion_discount + loyalty_discount
            
            # Create payment
            from services.payment_service import PaymentService
            payment, error = PaymentService.create_order_payment(
                user_id=user_id,
                order_id=order_id,
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
                discount_applied=total_discount
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
                    ErrorLoggingService.log_exception(
                        Exception(f"Payment created but points redemption failed: {error}"),
                        severity='high'
                    )
            
            # Note: Loyalty points are now awarded when order is marked as "delivered",
            # not when payment is processed. This prevents the exploit where customers can
            # cancel orders after redeeming points.
            
            return payment, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to process payment with loyalty: {str(e)}"

