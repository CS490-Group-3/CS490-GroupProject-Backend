import uuid
from datetime import datetime
from config import supabase

class NotificationService:
    @staticmethod
    def broadcast(recipients, event_type, title, message, related_id=None):
        """
        Send notifications to given recipients.

        recipients: list of roles or user_ids (e.g., ['admins', 'owner'])
        event_type: string (e.g., 'salon_verification')
        title: string
        message: formatted string, may contain placeholders like {salon_name}
        related_id: UUID of related record (e.g., salon_id, appointment_id)
        """
        data = []

        for r in recipients:
            # --- Specific user UUID ---
            if isinstance(r, str) and len(r) > 20 and "-" in r:
                data.append(NotificationService._record(r, event_type, title, message, related_id))
                continue

            # --- Admins ---
            if r == "admins":
                admins = supabase.table("user_profiles").select("user_id").eq("role", "admin").execute()
                for admin in admins.data:
                    data.append(NotificationService._record(admin["user_id"], event_type, title, message, related_id))
                continue

            # --- Salon Owner ---
            if r == "owner" and related_id:
                salon = supabase.table("salons").select("owner_id, name").eq("id", related_id).single().execute()
                if salon.data:
                    owner_id = salon.data["owner_id"]
                    salon_name = salon.data.get("name", "")
                    formatted_msg = message.format(salon_name=salon_name) if "{salon_name" in message else message
                    data.append(NotificationService._record(owner_id, event_type, title, formatted_msg, related_id))
                continue

            # --- Appointment User ---
            if r == "user" and related_id:
                appt = supabase.table("appointments").select("user_id").eq("id", related_id).single().execute()
                if appt.data:
                    data.append(NotificationService._record(appt.data["user_id"], event_type, title, message, related_id))
                continue

        if data:
            supabase.table("notifications").insert(data).execute()

    @staticmethod
    def _record(user_id, event_type, title, message, related_id=None):
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "notification_type": event_type,
            "title": title,
            "message": message,
            "status": "pending",
            "related_id": related_id,
            "created_at": datetime.utcnow().isoformat(),
        }

