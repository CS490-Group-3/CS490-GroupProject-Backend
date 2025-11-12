import uuid
from datetime import datetime, timedelta
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

            for notif in data:
                NotificationService._send_email(notif)


    @staticmethod
    def _send_email(notif):
        """
        Send a transactional email (confirmation/reschedule) using Supabase function or SMTP.
        """
        try:
            user = supabase.table("user_profiles").select("email, full_name").eq("user_id", notif["user_id"]).single().execute()
            if not user.data or not user.data.get("email"):
                return

            subject = notif["title"]
            body = notif["message"]

            # Example: using Supabase Edge Function or SendGrid webhook
            requests.post(
                "https://<your-supabase-project>.functions.supabase.co/send-email",
                json={
                    "to": user.data["email"],
                    "subject": subject,
                    "body": body,
                },
                timeout=5,
            )
        except Exception as e:
            print(f"[Email Error] {e}")

    #when an appointment is made(maybe confirmed) or updated we call to schedule reminder notifications  
    @staticmethod
    def schedule_upcoming_appointment(appointment_id):
        """
        Create scheduled notifications (1 day, 1 hour, and barber-only 30 min before)
        for a given appointment.
        Message format: "Appointment at {salon_name} for {service_name} in X time."
        """
        # --- Fetch appointment details ---
        appt = (
            supabase.table("appointments")
            .select("id, user_id, barber_id, salon_id, service_id, scheduled_at")
            .eq("id", appointment_id)
            .single()
            .execute()
        )

        if not appt.data:
            return

        appt_data = appt.data

        # --- Fetch salon and service info ---
        salon = (
            supabase.table("salons")
            .select("name")
            .eq("id", appt_data["salon_id"])
            .single()
            .execute()
        )
        service = (
            supabase.table("services")
            .select("name")
            .eq("id", appt_data["service_id"])
            .single()
            .execute()
        )

        salon_name = salon.data["name"] if salon.data else "Salon"
        service_name = service.data["name"] if service.data else "Service"

        # --- Build reminder times ---
        appt_time = datetime.fromisoformat(appt_data["scheduled_at"].replace("Z", "+00:00"))
        reminders = [
            ("Appointment tomorrow", appt_time - timedelta(days=1)),
            ("Appointment in 1 hour", appt_time - timedelta(hours=1)),
        ]

        # --- Recipient: customer ---
        data = []
        customer_id = appt_data.get("user_id")
        if customer_id:
            for label, sched_time in reminders:
                message = f"Reminder: Appointment at {salon_name} for {service_name} {label.lower()}."
                data.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": customer_id,
                        "notification_type": "appointment_reminder",
                        "title": "Upcoming Appointment",
                        "message": message,
                        "status": "pending",
                        "related_id": appointment_id,
                        "created_at": datetime.utcnow().isoformat(),
                        "scheduled_for": sched_time.isoformat(),
                    }
                )

        # --- Barber-only 30-minute reminder ---
        barber_id = appt_data.get("barber_id")
        if barber_id:
            thirty_min_before = appt_time - timedelta(minutes=30)
            data.append(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": barber_id,
                    "notification_type": "appointment_reminder",
                    "title": "Upcoming Appointment",
                    "message": f"Reminder: Appointment at {salon_name} for {service_name} in 30 minutes.",
                    "status": "pending",
                    "related_id": appointment_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "scheduled_for": thirty_min_before.isoformat(),
                }
            )

        # --- Insert all notifications ---
        if data:
            supabase.table("notifications").insert(data).execute()




    @staticmethod
    def notify_promotional_offer(offer_id, target_audience="existing_customers"):
        """
        Broadcast a promotional offer to eligible customers of a salon.
        target_audience: "existing_customers" (default) or "all_users"
        """
        # ---Fetch the offer ---
        offer = (
            supabase.table("promotional_offers")
            .select("id, salon_id, title, description, valid_from, valid_until, is_active")
            .eq("id", offer_id)
            .single()
            .execute()
        )
        if not offer.data:
            print(f"[notify_promotional_offer] Offer {offer_id} not found.")
            return

        salon_id = offer.data["salon_id"]
        title = offer.data["title"]
        description = offer.data["description"]
        now = datetime.utcnow().isoformat()

        user_ids = set()

        if target_audience == "all_users":
            users = supabase.table("user_profiles").select("user_id, role").execute()
            # exclude admins and the salon owner
            for u in users.data or []:
                if u["role"] not in ("admin", "owner"):
                    user_ids.add(u["user_id"])
        else:
            # existing customers only (bookings + loyalty)
            bookings = (
                supabase.table("appointments")
                .select("customer_id")
                .eq("salon_id", salon_id)
                .execute()
            )
            loyalty = (
                supabase.table("loyalty_balances")
                .select("user_id")
                .eq("salon_id", salon_id)
                .execute()
            )
            user_ids = {b["user_id"] for b in (bookings.data or [])} | {
                l["user_id"] for l in (loyalty.data or [])
            }

        if not user_ids:
            print(f"[notify_promotional_offer] No recipients found for salon {salon_id}.")
            return

        # --- Insert promotional_recipients ---
        recipients_data = [
            {
                "id": str(uuid.uuid4()),
                "offer_id": offer_id,
                "user_id": uid,
                "sent_at": None,
            }
            for uid in user_ids
        ]
        supabase.table("promotional_recipients").insert(recipients_data).execute()

        # --- Create in-app notifications ---
        notifications_data = [
            {
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "notification_type": "promotional_offer",
                "title": f"New Offer: {title}",
                "message": description,
                "status": "pending",
                "related_id": offer_id,
                "created_at": now,
                "scheduled_for": offer.data.get("valid_from") or now,
            }
            for uid in user_ids
        ]
        supabase.table("notifications").insert(notifications_data).execute()

        print(f"[notify_promotional_offer] Sent to {len(user_ids)} users for offer {offer_id} ({target_audience}).")







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

