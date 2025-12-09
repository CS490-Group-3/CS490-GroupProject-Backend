
import uuid
from datetime import datetime
from config import supabase
from services.notification_service import NotificationService
from services.audit_logging_service import AuditLoggingService

class PromotionService:
    @staticmethod
    def create_offer(salon_id, data):
        """
        Handles creating a new promotional offer and triggering notifications.
        """
        required = [
            "title", "description", "discount_type",
            "discount_value", "valid_from", "valid_until"
        ]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")

        offer_id = str(uuid.uuid4())
        offer_record = {
            "id": offer_id,
            "salon_id": str(salon_id),
            "title": data["title"],
            "description": data["description"],
            "discount_type": data["discount_type"],
            "discount_value": data["discount_value"],
            "min_purchase_amount": data.get("min_purchase_amount", 0),
            "valid_from": data["valid_from"],
            "valid_until": data["valid_until"],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "target_audience": data.get("target_audience", "existing_customers"),
            "min_visits": data.get("min_visits"),  # For custom targeting
            "min_loyalty_points": data.get("min_loyalty_points"),  # For custom targeting
            "targeting_logic": data.get("targeting_logic"),  # "and" or "or" for custom targeting
        }

        # --- Insert offer (service handles the DB, not route)
        supabase.table("promotional_offers").insert(offer_record).execute()
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='promotional_offers',
            record_id=offer_id,
            action='INSERT',
            new_values=offer_record,
            changed_by=None  # Could get salon owner from context if needed
        )

        # --- Trigger notifications ---
        target_audience = data.get("target_audience", "existing_customers")
        min_visits = data.get("min_visits")
        min_loyalty_points = data.get("min_loyalty_points")
        targeting_logic = data.get("targeting_logic", "and")  # Default to AND if both criteria specified
        NotificationService.notify_promotional_offer(
            offer_id, 
            target_audience,
            min_visits=min_visits,
            min_loyalty_points=min_loyalty_points,
            targeting_logic=targeting_logic
        )

        return {
            "message": f"Offer created and notifications sent to {target_audience}.",
            "offer_id": offer_id,
        }
    
    @staticmethod
    def get_salon_promotions(salon_id):
        """
        Get all promotional offers for a salon.
        
        Args:
            salon_id: Salon ID
        
        Returns:
            Tuple of (list of promotions, error_message)
        """
        try:
            response = supabase.table("promotional_offers")\
                .select("*")\
                .eq("salon_id", salon_id)\
                .order("created_at", desc=True)\
                .execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            promotions = response.data or []
            
            # Get recipient counts for each promotion
            for promotion in promotions:
                recipients_res = supabase.table("promotional_recipients")\
                    .select("id", count="exact")\
                    .eq("offer_id", promotion["id"])\
                    .execute()
                
                promotion["recipient_count"] = recipients_res.count if hasattr(recipients_res, "count") else 0
            
            return promotions, None
            
        except Exception as e:
            from services.error_logging_service import ErrorLoggingService
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get promotions: {str(e)}"
    
    @staticmethod
    def update_promotion(promotion_id, salon_id, data):
        """
        Update a promotional offer.
        
        Args:
            promotion_id: Promotion ID
            salon_id: Salon ID (for verification)
            data: Update data
        
        Returns:
            Tuple of (updated_promotion, error_message)
        """
        try:
            # Verify ownership
            check = supabase.table("promotional_offers")\
                .select("id")\
                .eq("id", promotion_id)\
                .eq("salon_id", salon_id)\
                .single()\
                .execute()
            
            if getattr(check, "error", None) or not check.data:
                return None, "Promotion not found or unauthorized"
            
            # Build update record
            update_record = {}
            allowed_fields = ["title", "description", "discount_type", "discount_value", 
                            "min_purchase_amount", "valid_from", "valid_until", "is_active",
                            "target_audience", "min_visits", "min_loyalty_points", "targeting_logic"]
            
            for field in allowed_fields:
                if field in data:
                    update_record[field] = data[field]
            
            if not update_record:
                return None, "No valid fields to update"
            
            # Update
            response = supabase.table("promotional_offers")\
                .update(update_record)\
                .eq("id", promotion_id)\
                .execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='promotional_offers',
                record_id=promotion_id,
                action='UPDATE',
                new_values=update_record,
                changed_by=None
            )
            
            return response.data[0] if response.data else None, None
            
        except Exception as e:
            from services.error_logging_service import ErrorLoggingService
            ErrorLoggingService.log_exception(e, severity='medium')
            return None, f"Failed to update promotion: {str(e)}"
    
    @staticmethod
    def delete_promotion(promotion_id, salon_id):
        """
        Delete a promotional offer.
        
        Args:
            promotion_id: Promotion ID
            salon_id: Salon ID (for verification)
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify ownership
            check = supabase.table("promotional_offers")\
                .select("id")\
                .eq("id", promotion_id)\
                .eq("salon_id", salon_id)\
                .single()\
                .execute()
            
            if getattr(check, "error", None) or not check.data:
                return False, "Promotion not found or unauthorized"
            
            # Delete
            response = supabase.table("promotional_offers")\
                .delete()\
                .eq("id", promotion_id)\
                .execute()
            
            if getattr(response, "error", None):
                return False, response.error.message
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='promotional_offers',
                record_id=promotion_id,
                action='DELETE',
                new_values=None,
                changed_by=None
            )
            
            return True, None
            
        except Exception as e:
            from services.error_logging_service import ErrorLoggingService
            ErrorLoggingService.log_exception(e, severity='medium')
            return False, f"Failed to delete promotion: {str(e)}"
    
    @staticmethod
    def get_active_promotions(salon_id, purchase_amount=0.0, user_id=None):
        """
        Get active promotional offers for a salon that are currently valid.
        If user_id is provided, only returns promotions the user is eligible for.
        
        Args:
            salon_id: Salon ID
            purchase_amount: Purchase amount to check min_purchase_amount requirement
            user_id: Optional user ID to check eligibility (must be in promotional_recipients)
        
        Returns:
            Tuple of (list of active promotions, error_message)
        """
        try:
            from datetime import datetime, timezone
            
            now = datetime.now(timezone.utc).isoformat()
            
            # Get promotions that are:
            # 1. For this salon
            # 2. is_active = True
            # 3. valid_from <= now
            # 4. valid_until >= now
            # 5. min_purchase_amount <= purchase_amount (if specified)
            response = supabase.table("promotional_offers")\
                .select("*")\
                .eq("salon_id", salon_id)\
                .eq("is_active", True)\
                .lte("valid_from", now)\
                .gte("valid_until", now)\
                .order("created_at", desc=True)\
                .execute()
            
            if getattr(response, "error", None):
                return [], response.error.message
            
            promotions = response.data or []
            
            # Filter by min_purchase_amount if specified
            if purchase_amount > 0:
                promotions = [
                    p for p in promotions 
                    if not p.get("min_purchase_amount") or float(p.get("min_purchase_amount", 0)) <= purchase_amount
                ]
            
            # If user_id provided, filter to only promotions they're eligible for
            if user_id:
                # Get all promotion IDs this user is a recipient of
                recipients_response = supabase.table("promotional_recipients")\
                    .select("offer_id")\
                    .eq("user_id", user_id)\
                    .execute()
                
                if getattr(recipients_response, "error", None):
                    return [], recipients_response.error.message
                
                eligible_offer_ids = {r["offer_id"] for r in (recipients_response.data or [])}
                promotions = [p for p in promotions if p["id"] in eligible_offer_ids]
            
            return promotions, None
            
        except Exception as e:
            from services.error_logging_service import ErrorLoggingService
            ErrorLoggingService.log_exception(e, severity='medium')
            return [], f"Failed to get active promotions: {str(e)}"
    
    @staticmethod
    def calculate_discount(promotion, amount):
        """
        Calculate discount amount for a given promotion and purchase amount.
        
        Args:
            promotion: Promotion dict with discount_type and discount_value
            amount: Purchase amount before discount
        
        Returns:
            Discount amount (float)
        """
        try:
            discount_type = promotion.get("discount_type")
            discount_value = float(promotion.get("discount_value", 0))
            
            if discount_type == "percentage":
                discount = amount * (discount_value / 100.0)
            elif discount_type == "fixed_amount":
                discount = min(discount_value, amount)  # Can't discount more than the amount
            else:
                discount = 0.0
            
            return round(discount, 2)
            
        except Exception as e:
            from services.error_logging_service import ErrorLoggingService
            ErrorLoggingService.log_exception(e, severity='low')
            return 0.0

