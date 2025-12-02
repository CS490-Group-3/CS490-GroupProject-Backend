
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
        NotificationService.notify_promotional_offer(offer_id, target_audience)

        return {
            "message": f"Offer created and notifications sent to {target_audience}.",
            "offer_id": offer_id,
        }

