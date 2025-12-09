import uuid
from datetime import datetime, timedelta
from config import supabase
from services.error_logging_service import ErrorLoggingService
import json
from flask import jsonify
import requests

def serialize(row):
    for key, value in row.items():
        if isinstance(value, datetime):
            row[key] = value.isoformat()
    return row


class NotificationService:
    @staticmethod
    def broadcast(recipients, event_type, title, message, related_id=None, messages_by_recipient=None, context=None):
        """
        Send notifications to given recipients.

        recipients: list of roles or user_ids (e.g., ['admins', 'salon_owner'])
        event_type: string (e.g., 'salon_verification')
        title: string
        message: formatted string, may contain placeholders like {salon_name}
        related_id: UUID of related record (e.g., salon_id, appointment_id)
        """
        context = context or {}
        data = []
        try:
            message = message.format(**context)
        except Exception:
            pass
        for r in recipients:
            recipient_message = (
            messages_by_recipient.get(r, message)
            if messages_by_recipient else message
            )
            if "{salon_name}" in recipient_message and related_id:
                try:
                    salon_lookup = (
                        supabase.table("appointments")
                        .select("salon_id")
                        .eq("id", related_id)
                        .single()
                        .execute()
                    )

                    if salon_lookup.data and salon_lookup.data.get("salon_id"):
                        salon_id = salon_lookup.data["salon_id"]

                        salon = (
                            supabase.table("salons")
                            .select("name")
                            .eq("id", salon_id)
                            .single()
                            .execute()
                        )

                        if salon.data:
                            context["salon_name"] = salon.data["name"]

                except Exception as e:
                    print(f"[notify] Failed to resolve salon_name: {e}")
            if "{service_name}" in recipient_message and related_id:
                try:
                    svc_lookup = (
                        supabase.table("appointments")
                        .select("service_id")
                        .eq("id", related_id)
                        .single()
                        .execute()
                    )

                    if svc_lookup.data and svc_lookup.data.get("service_id"):
                        service_id = svc_lookup.data["service_id"]

                        service = (
                            supabase.table("services")
                            .select("name")
                            .eq("id", service_id)
                            .single()
                            .execute()
                        )

                        if service.data:
                            context["service_name"] = service.data["name"]

                except Exception as e:
                    print(f"[notify] Failed to resolve service_name: {e}")

            try:
                recipient_message = recipient_message.format(**context)
            except Exception:
                pass
            # --- Specific user UUID ---
            if isinstance(r, str) and len(r) > 20 and "-" in r:
                data.append(NotificationService._record(r, event_type, title,recipient_message, related_id))
                continue

            # --- Admins ---
            if r == "admins":
                admins = supabase.table("user_profiles").select("user_id").eq("role", "admin").execute()
                for admin in admins.data:
                    data.append(NotificationService._record(admin["user_id"], event_type, title,recipient_message, related_id))
                continue

            # --- Salon Owner ---
            if r == "salon_owner" and related_id:
                salon = supabase.table("salons").select("owner_id, name").eq("id", related_id).single().execute()
                if salon.data:
                    owner_id = salon.data["owner_id"]
                    salon_name = salon.data.get("name", "")
                    formatted_msg = recipient_message.format(salon_name=salon_name) if "{salon_name" in recipient_message else recipient_message
                    data.append(NotificationService._record(owner_id, event_type, title, formatted_msg, related_id))
                continue

            # --- Appointment User ---
            if r == "user" and related_id:
                appt = supabase.table("appointments").select("customer_id").eq("id", related_id).single().execute()
                if appt.data:
                    data.append(NotificationService._record(appt.data["customer_id"], event_type, title, recipient_message, related_id))

                continue
            # --- Appointment Barber ---
            if r == "barber" and related_id:
                appt = supabase.table("appointments").select("barber_id").eq("id", related_id).single().execute()
                if appt.data:
                    barber_profile_id = appt.data["barber_id"]

                    barber_profile = supabase.table("barbers").select("user_id").eq("id", barber_profile_id).single().execute()

                    if barber_profile.data:
                        barber_user_id = barber_profile.data["user_id"]
                    data.append(
                        NotificationService._record(barber_user_id, event_type, title, recipient_message, related_id)
                    )

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
            user = supabase.table("user_details").select("email").eq("id", notif["user_id"]).single().execute()
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
            .select("id, customer_id, barber_id, salon_id, service_id, start_at")
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
        appt_time = datetime.fromisoformat(appt_data["start_at"].replace("Z", "+00:00"))
        reminders = [
            ("Appointment tomorrow", appt_time - timedelta(days=1)),
            ("Appointment in 1 hour", appt_time - timedelta(hours=1)),
        ]

        # --- Recipient: customer ---
        data = []
        customer_id = appt_data.get("customer_id")
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
        barber_profile_id = appt_data.get("barber_id")
        if barber_profile_id:
            barber_profile = supabase.table("barbers").select("user_id").eq("id", barber_profile_id).single().execute()
            if barber_profile.data:
                barber_user_id = barber_profile.data["user_id"]
                thirty_min_before = appt_time - timedelta(minutes=30)
                data.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": barber_user_id,
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
    def notify_promotional_offer(offer_id, target_audience="existing_customers", min_visits=None, min_loyalty_points=None, targeting_logic="and"):
        """
        Broadcast a promotional offer to eligible customers of a salon.
        target_audience: "existing_customers" (default), "all_users", or "custom"
        min_visits: Optional minimum number of confirmed visits (for custom targeting)
        min_loyalty_points: Optional minimum lifetime loyalty points (for custom targeting)
        targeting_logic: "and" or "or" - how to combine criteria when both are specified (default: "and")
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

        salon = (
        supabase.table("salons")
        .select("name")
        .eq("id", salon_id)
        .single()
        .execute()
        )
        salon_name = salon.data["name"] 
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
        elif target_audience == "custom":
            # Custom targeting: filter by min_visits and/or min_loyalty_points
            # If both specified: user must meet BOTH (AND logic)
            # If only one specified: user must meet that ONE criterion
            
            visit_users = set()
            points_users = set()
            
            # Get users meeting min_visits criterion (if specified)
            if min_visits is not None:
                bookings = (
                    supabase.table("appointments")
                    .select("customer_id")
                    .eq("salon_id", salon_id)
                    .in_("status", ["scheduled", "confirmed", "completed"])
                    .execute()
                )
                # Count visits per user
                visit_counts = {}
                for b in (bookings.data or []):
                    customer_id = b["customer_id"]
                    visit_counts[customer_id] = visit_counts.get(customer_id, 0) + 1
                
                # Filter by min_visits
                visit_users = {cid for cid, count in visit_counts.items() if count >= min_visits}
            
            # Get users meeting min_loyalty_points criterion (if specified)
            if min_loyalty_points is not None:
                loyalty = (
                    supabase.table("loyalty_balances")
                    .select("user_id, lifetime_points_earned")
                    .eq("salon_id", salon_id)
                    .execute()
                )
                points_users = {
                    l["user_id"] for l in (loyalty.data or []) 
                    if float(l.get("lifetime_points_earned", 0)) >= min_loyalty_points
                }
            
            # Combine criteria:
            # - If both specified: use targeting_logic ("and" = intersection, "or" = union)
            # - If only one specified: use that set
            if min_visits is not None and min_loyalty_points is not None:
                # Both criteria specified: use targeting_logic
                if targeting_logic == "or":
                    # OR logic: user must meet EITHER criterion
                    user_ids = visit_users | points_users
                else:
                    # AND logic (default): user must meet BOTH criteria
                    user_ids = visit_users & points_users
            elif min_visits is not None:
                # Only visits criterion
                user_ids = visit_users
            elif min_loyalty_points is not None:
                # Only points criterion
                user_ids = points_users
            else:
                # Neither specified (shouldn't happen with validation, but handle gracefully)
                user_ids = set()
        else:
            # existing customers only (bookings + loyalty)
            # Only count scheduled/completed appointments (not cancelled)
            bookings = (
                supabase.table("appointments")
                .select("customer_id")
                .eq("salon_id", salon_id)
                .in_("status", ["scheduled", "confirmed", "completed"])
                .execute()
            )
            # Get users with any lifetime loyalty points (not just current balance)
            loyalty = (
                supabase.table("loyalty_balances")
                .select("user_id, lifetime_points_earned")
                .eq("salon_id", salon_id)
                .execute()
            )
            # Include users with appointments OR users with any lifetime points earned
            user_ids = {b["customer_id"] for b in (bookings.data or [])} | {
                l["user_id"] for l in (loyalty.data or []) if float(l.get("lifetime_points_earned", 0)) > 0
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
                "title": f"New Promotional Offer at {salon_name}: {title}",
                "message": description,
                "status": "pending",
                "related_id": salon_id,  # Use salon_id so customers can navigate to salon
                "created_at": now,
                "scheduled_for": offer.data.get("valid_from") or now,
            }
            for uid in user_ids
        ]
        supabase.table("notifications").insert(notifications_data).execute()

        print(f"[notify_promotional_offer] Sent to {len(user_ids)} users for offer {offer_id} ({target_audience}).")


    """
    @staticmethod
    def mark_as_read(notification_id: str):
        try:
            # validate uuid format
            uuid.UUID(notification_id)
        except ValueError:
            return {"error": "Invalid notification ID"}, 400

        try:
            supabase.table("notifications").update({
                "status": "read",
                "read_at": datetime.utcnow().isoformat()
            }).eq("id", notification_id).execute()
            return {"success": True}, 200
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            print("Error updating notification read_at:", e)
            return {"error": str(e)}, 500
    """

    @staticmethod
    def create_notification(user_id, event_type, title, message, related_id=None, scheduled_for=None):
        data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "notification_type": event_type,
            "title": title,
            "message": message,
            "status": "pending" if scheduled_for else "sent",
            "related_id": related_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        if scheduled_for:
            data["scheduled_for"] = scheduled_for.isoformat()
        return supabase.table("notifications").insert(data).execute()


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
            "scheduled_for": datetime.utcnow().isoformat(), 
        }



    @staticmethod
    def get_user_notifications(user_id):
        rows = (
            supabase.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .lte("scheduled_for", datetime.utcnow().isoformat())
            .order("created_at", desc=True)
            .execute()
            .data
        )
        return rows

    @staticmethod
    def get_unread_count(user_id):
        count = (
            supabase.table("notifications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .neq("status", "read")
            .lte("scheduled_for", datetime.utcnow().isoformat())
            .execute()
            .count
        )
        return count




    @staticmethod
    def mark_as_read(user_id, notif_id):
        print("MARK_AS_READ: minimal version")

        try:
            res = (
                supabase.table("notifications")
                .select("id,user_id,scheduled_for,status")
                .eq("id", notif_id)
                .single()
                .execute()
            )
        except Exception as e:
            print("ERROR on initial select:", repr(e))
            raise

        notif = res.data
        if not notif:
            raise NotFound("Notification not found")

        if notif["user_id"] != user_id:
            raise Forbidden("Not allowed to modify this notification")

        sched = notif["scheduled_for"]

        if isinstance(sched, bytes):
            sched = sched.decode("utf-8")

        if isinstance(sched, str):
            sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
        else:
            sched_dt = sched

        now = datetime.utcnow()
        if getattr(sched_dt, "tzinfo", None) is not None:
            now = now.replace(tzinfo=sched_dt.tzinfo)

        if sched_dt > now:
            raise Forbidden("Notification not active yet")

        try:
            supabase.table("notifications").update(
                {"status": "read"}   # <-- no read_at for now
            ).eq("id", notif_id).execute()
        except Exception as e:
            print("ERROR on update:", repr(e))
            raise

        return {
            "id": notif_id,
            "status": "read"
        }




    @staticmethod
    def mark_all_as_read(user_id):

        try:
            res = (
                supabase.table("notifications")
                .select("id, user_id, scheduled_for, status")
                .eq("user_id", user_id)
                .neq("status", "read")
                .lte("scheduled_for", datetime.utcnow().isoformat())
                .execute()
            )
        except Exception as e:
            print("ERROR on initial select (mark all):", repr(e))
            raise

        rows = res.data or []

        if not rows:
            return {"updated": 0}

        notif_ids = [row["id"] for row in rows]

        try:
            supabase.table("notifications").update(
                {"status": "read"}
            ).in_("id", notif_ids).execute()
        except Exception as e:
            print("ERROR on update (mark all):", repr(e))
            raise

        return {"updated": len(notif_ids)}


    @staticmethod
    def barber_running_late(user_id: str, appointment_id: str):
        """
        Notify customer that barber is running late for an appointment.
        Returns (data, error) tuple following service pattern.
        """
        try:
            # Get barber profile for this user
            barber_resp = (
                supabase.table("barbers")
                .select("id")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "You are not registered as a barber"

            barber_profile_id = barber_resp.data["id"]

            # Fetch the appointment
            appt_resp = (
                supabase.table("appointments")
                .select("id, barber_id, customer_id, salon_id, service_id, start_at")
                .eq("id", appointment_id)
                .single()
                .execute()
            )

            if getattr(appt_resp, "error", None) or not appt_resp.data:
                return None, "Appointment not found"

            appt = appt_resp.data

            # Authorization check
            if appt["barber_id"] != barber_profile_id:
                return None, "Forbidden"

            # Fetch appointment details for notification message
            salon_name = "the salon"
            service_name = "your service"
            appt_time = ""
            
            try:
                # Fetch salon name
                if appt.get("salon_id"):
                    salon_resp = (
                        supabase.table("salons")
                        .select("name")
                        .eq("id", appt["salon_id"])
                        .single()
                        .execute()
                    )
                    if salon_resp.data and salon_resp.data.get("name"):
                        salon_name = salon_resp.data["name"]
                
                # Fetch service name
                if appt.get("service_id"):
                    service_resp = (
                        supabase.table("services")
                        .select("name")
                        .eq("id", appt["service_id"])
                        .single()
                        .execute()
                    )
                    if service_resp.data and service_resp.data.get("name"):
                        service_name = service_resp.data["name"]
                
                # Format appointment time
                if appt.get("start_at"):
                    try:
                        start_dt = datetime.fromisoformat(appt["start_at"].replace("Z", "+00:00"))
                        appt_time = start_dt.strftime("%I:%M %p")
                    except Exception:
                        pass
            except Exception as e:
                ErrorLoggingService.log_exception(e, severity='low')
                # Continue with defaults if fetching details fails

            # Create notification for customer with appointment details
            message = f"Your barber is running a little behind schedule for your {service_name} appointment at {salon_name}"
            if appt_time:
                message += f" scheduled for {appt_time}."
            else:
                message += "."

            notif = {
                "id": str(uuid.uuid4()),
                "user_id": appt["customer_id"],
                "notification_type": "barber_running_late",
                "title": "Your barber is running late",
                "message": message,
                "status": "sent",
                "related_id": appointment_id,
                "created_at": datetime.utcnow().isoformat(),
                "scheduled_for": datetime.utcnow().isoformat(),
            }

            supabase.table("notifications").insert(notif).execute()

            return {"success": True, "message": "Customer has been notified that you are running late"}, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)


