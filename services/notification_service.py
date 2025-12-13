import uuid
from datetime import datetime, timedelta, timezone
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
            
            # Fetch appointment date/time if needed for appointment-related notifications
            if (("{appointment_date}" in recipient_message or "{appointment_time}" in recipient_message or "{start_at}" in recipient_message) and related_id):
                try:
                    appt_lookup = (
                        supabase.table("appointments")
                        .select("start_at, salon_id")
                        .eq("id", related_id)
                        .single()
                        .execute()
                    )
                    
                    if appt_lookup.data and appt_lookup.data.get("start_at"):
                        start_at = appt_lookup.data["start_at"]
                        salon_id = appt_lookup.data.get("salon_id")
                        
                        try:
                            # Parse ISO format datetime (UTC)
                            dt_utc = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                            if dt_utc.tzinfo is None:
                                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                            else:
                                dt_utc = dt_utc.astimezone(timezone.utc)
                            
                            # Get salon timezone and convert
                            salon_timezone = "America/New_York"  # Default
                            if salon_id:
                                try:
                                    salon_info = supabase.table("salons").select("timezone").eq("id", salon_id).maybe_single().execute()
                                    if salon_info.data and salon_info.data.get("timezone"):
                                        salon_timezone = salon_info.data["timezone"]
                                except Exception:
                                    pass  # Use default
                            
                            # Convert to salon's timezone
                            try:
                                from zoneinfo import ZoneInfo
                                salon_tz = ZoneInfo(salon_timezone)
                                dt_local = dt_utc.astimezone(salon_tz)
                            except Exception:
                                # Fallback to UTC if timezone conversion fails
                                dt_local = dt_utc
                            
                            # Format date as "MM/DD/YYYY"
                            context["appointment_date"] = dt_local.strftime("%m/%d/%Y")
                            # Format time as "H:MM AM/PM"
                            context["appointment_time"] = dt_local.strftime("%I:%M %p").lstrip("0")
                            # Format start_at as "MM/DD/YY at H:MM AM/PM" for barber notifications
                            context["start_at"] = dt_local.strftime("%m/%d/%y at %I:%M %p").lstrip("0")
                        except Exception:
                            # Fallback to raw value if parsing fails
                            context["appointment_date"] = start_at
                            context["appointment_time"] = start_at
                            context["start_at"] = start_at
                except Exception as e:
                    print(f"[notify] Failed to resolve appointment date/time: {e}")

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

    # Send immediate notification with appointment details when appointment is created/updated
    @staticmethod
    def notify_appointment_details(appointment_id):
        """
        Send immediate notification with appointment date/time details.
        No scheduled reminders - just immediate notification with full details.
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
        
        # Get salon timezone
        salon_timezone = "America/New_York"  # Default
        try:
            salon_tz_info = supabase.table("salons").select("timezone").eq("id", appt_data["salon_id"]).maybe_single().execute()
            if salon_tz_info.data and salon_tz_info.data.get("timezone"):
                salon_timezone = salon_tz_info.data["timezone"]
        except Exception:
            pass  # Use default

        # --- Format appointment date/time in salon's timezone ---
        appt_time_utc = datetime.fromisoformat(appt_data["start_at"].replace("Z", "+00:00"))
        if appt_time_utc.tzinfo is None:
            appt_time_utc = appt_time_utc.replace(tzinfo=timezone.utc)
        else:
            appt_time_utc = appt_time_utc.astimezone(timezone.utc)
        
        # Convert to salon's timezone
        try:
            from zoneinfo import ZoneInfo
            salon_tz = ZoneInfo(salon_timezone)
            appt_time_local = appt_time_utc.astimezone(salon_tz)
        except Exception:
            # Fallback to UTC if timezone conversion fails
            appt_time_local = appt_time_utc
        
        appt_date_str = appt_time_local.strftime("%m/%d/%Y")
        appt_time_str = appt_time_local.strftime("%I:%M %p").lstrip("0")

        # --- Create immediate notifications ---
        data = []
        now = datetime.now(timezone.utc)
        
        # Customer notification
        customer_id = appt_data.get("customer_id")
        if customer_id:
            message = f"Your appointment at {salon_name} for {service_name} is scheduled for {appt_date_str} at {appt_time_str}."
            data.append(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": customer_id,
                    "notification_type": "appointment_reminder",
                    "title": "Appointment Scheduled",
                    "message": message,
                    "status": "sent",
                    "related_id": appointment_id,
                    "created_at": now.isoformat(),
                    "scheduled_for": now.isoformat(),
                    "sent_at": now.isoformat(),
                }
            )

        # Barber notification
        barber_profile_id = appt_data.get("barber_id")
        if barber_profile_id:
            barber_profile = supabase.table("barbers").select("user_id").eq("id", barber_profile_id).single().execute()
            if barber_profile.data:
                barber_user_id = barber_profile.data["user_id"]
                message = f"You have an appointment at {salon_name} for {service_name} on {appt_date_str} at {appt_time_str}."
                data.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": barber_user_id,
                        "notification_type": "appointment_reminder",
                        "title": "Appointment Scheduled",
                        "message": message,
                        "status": "sent",
                        "related_id": appointment_id,
                        "created_at": now.isoformat(),
                        "scheduled_for": now.isoformat(),
                        "sent_at": now.isoformat(),
                    }
                )

        # --- Insert all notifications immediately ---
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
        # Immediate notifications should be marked as "sent" so they show up right away
        # scheduled_for is set to now so they're immediately available
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "notification_type": event_type,
            "title": title,
            "message": message,
            "status": "sent",  # Mark as sent immediately so it shows up in app right away
            "related_id": related_id,
            "created_at": now.isoformat(),
            "scheduled_for": now.isoformat(),  # Set to now so it's immediately available
            "sent_at": now.isoformat(),  # Mark as sent immediately
        }



    @staticmethod
    def get_user_notifications(user_id):
        # First, check for upcoming appointments and create notifications on-demand
        # This creates new notifications if needed
        NotificationService._check_and_create_upcoming_appointment_notifications(user_id)
        
        # Then return all notifications
        # Use a slightly future time to ensure we catch notifications just created
        # (accounts for any small timing differences)
        now_plus_buffer = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        rows = (
            supabase.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .lte("scheduled_for", now_plus_buffer)
            .order("created_at", desc=True)
            .execute()
            .data
        )
        return rows
    
    @staticmethod
    def _check_and_create_upcoming_appointment_notifications(user_id):
        """
        On-demand check for upcoming appointments and create reminder notifications.
        This runs when users fetch notifications, so no scheduled job is needed.
        """
        try:
            now = datetime.now(timezone.utc)
            # Check appointments in the next 24 hours
            next_24h = now + timedelta(hours=24)
            
            # Get user's role to determine how to query appointments
            user_profile = supabase.table("user_profiles").select("role").eq("user_id", user_id).single().execute()
            if not user_profile.data:
                return
            
            role = user_profile.data.get("role")
            upcoming_appointments = []
            
            if role == "customer":
                # Get customer's upcoming appointments (includes in-progress)
                # Query appointments from 4 hours ago to 24 hours in the future
                # This catches both in-progress (started but not ended) and truly upcoming
                past_4h = (now - timedelta(hours=4)).isoformat()
                appointments = (
                    supabase.table("appointments")
                    .select("id, start_at, end_at, salon_id, service_id")
                    .eq("customer_id", user_id)
                    .in_("status", ["scheduled", "confirmed"])
                    .gte("start_at", past_4h)
                    .lte("start_at", next_24h.isoformat())
                    .order("start_at", desc=False)
                    .execute()
                )
                if appointments.data:
                    # Filter to only include appointments that haven't ended yet
                    upcoming_appointments = []
                    for apt in appointments.data:
                        start_at = datetime.fromisoformat(apt["start_at"].replace("Z", "+00:00"))
                        if start_at.tzinfo is None:
                            start_at = start_at.replace(tzinfo=timezone.utc)
                        else:
                            start_at = start_at.astimezone(timezone.utc)
                        
                        # Check if appointment has ended
                        if apt.get("end_at"):
                            end_at = datetime.fromisoformat(apt["end_at"].replace("Z", "+00:00"))
                            if end_at.tzinfo is None:
                                end_at = end_at.replace(tzinfo=timezone.utc)
                            else:
                                end_at = end_at.astimezone(timezone.utc)
                            if end_at < now:
                                continue  # Appointment has ended, skip it
                        else:
                            # No end_at, assume 30 min duration
                            end_at = start_at + timedelta(minutes=30)
                            if end_at < now:
                                continue  # Appointment has ended, skip it
                        
                        upcoming_appointments.append(apt)
                    
            elif role == "barber":
                # Get barber's upcoming appointments (includes in-progress)
                barber_profile = supabase.table("barbers").select("id").eq("user_id", user_id).maybe_single().execute()
                if barber_profile.data:
                    barber_id = barber_profile.data["id"]
                    past_4h = (now - timedelta(hours=4)).isoformat()
                    appointments = (
                        supabase.table("appointments")
                        .select("id, start_at, end_at, salon_id, service_id")
                        .eq("barber_id", barber_id)
                        .in_("status", ["scheduled", "confirmed"])
                        .gte("start_at", past_4h)
                        .lte("start_at", next_24h.isoformat())
                        .order("start_at", desc=False)
                        .execute()
                    )
                    if appointments.data:
                        # Filter to only include appointments that haven't ended yet
                        upcoming_appointments = []
                        for apt in appointments.data:
                            start_at = datetime.fromisoformat(apt["start_at"].replace("Z", "+00:00"))
                            if start_at.tzinfo is None:
                                start_at = start_at.replace(tzinfo=timezone.utc)
                            else:
                                start_at = start_at.astimezone(timezone.utc)
                            
                            # Check if appointment has ended
                            if apt.get("end_at"):
                                end_at = datetime.fromisoformat(apt["end_at"].replace("Z", "+00:00"))
                                if end_at.tzinfo is None:
                                    end_at = end_at.replace(tzinfo=timezone.utc)
                                else:
                                    end_at = end_at.astimezone(timezone.utc)
                                if end_at < now:
                                    continue  # Appointment has ended, skip it
                            else:
                                # No end_at, assume 30 min duration
                                end_at = start_at + timedelta(minutes=30)
                                if end_at < now:
                                    continue  # Appointment has ended, skip it
                            
                            upcoming_appointments.append(apt)
            
            if not upcoming_appointments:
                return
            
            # Get existing reminder notifications for these appointments
            appointment_ids = [apt["id"] for apt in upcoming_appointments]
            existing_notifs = (
                supabase.table("notifications")
                .select("related_id")
                .eq("user_id", user_id)
                .eq("notification_type", "appointment_reminder")
                .in_("related_id", appointment_ids)
                .execute()
            )
            existing_appointment_ids = {n["related_id"] for n in (existing_notifs.data or [])}
            
            # Create notifications for appointments that don't have reminders yet
            new_notifications = []
            for apt in upcoming_appointments:
                if apt["id"] in existing_appointment_ids:
                    continue  # Already has a notification
                
                # Fetch salon and service details
                salon = supabase.table("salons").select("name, timezone").eq("id", apt["salon_id"]).single().execute()
                service = supabase.table("services").select("name").eq("id", apt["service_id"]).single().execute()
                
                salon_name = salon.data["name"] if salon.data else "Salon"
                service_name = service.data["name"] if service.data else "Service"
                salon_timezone = salon.data.get("timezone") if salon.data else "America/New_York"
                
                # Format appointment time in salon's timezone
                appt_time_utc = datetime.fromisoformat(apt["start_at"].replace("Z", "+00:00"))
                if appt_time_utc.tzinfo is None:
                    appt_time_utc = appt_time_utc.replace(tzinfo=timezone.utc)
                else:
                    appt_time_utc = appt_time_utc.astimezone(timezone.utc)
                
                # Convert to salon's timezone
                try:
                    from zoneinfo import ZoneInfo
                    salon_tz = ZoneInfo(salon_timezone)
                    appt_time_local = appt_time_utc.astimezone(salon_tz)
                except Exception:
                    # Fallback to UTC if timezone conversion fails
                    appt_time_local = appt_time_utc
                
                time_until = appt_time_utc - now
                hours_until = int(time_until.total_seconds() / 3600)
                minutes_until = int((time_until.total_seconds() % 3600) / 60)
                
                if hours_until > 0:
                    time_str = f"in {hours_until} hour{'s' if hours_until > 1 else ''}"
                elif minutes_until > 0:
                    time_str = f"in {minutes_until} minute{'s' if minutes_until > 1 else ''}"
                else:
                    time_str = "soon"
                
                appt_date_str = appt_time_local.strftime("%m/%d/%Y")
                appt_time_str = appt_time_local.strftime("%I:%M %p").lstrip("0")
                
                message = f"Upcoming appointment at {salon_name} for {service_name} on {appt_date_str} at {appt_time_str} ({time_str})."
                
                new_notifications.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "notification_type": "appointment_reminder",
                    "title": "Upcoming Appointment",
                    "message": message,
                    "status": "sent",
                    "related_id": apt["id"],
                    "created_at": now.isoformat(),
                    "scheduled_for": now.isoformat(),
                    "sent_at": now.isoformat(),
                })
            
            # Insert new notifications
            if new_notifications:
                supabase.table("notifications").insert(new_notifications).execute()
                
        except Exception as e:
            # Don't fail notification fetching if this check fails
            print(f"[notify] Failed to check upcoming appointments: {e}")

    @staticmethod
    def get_unread_count(user_id):
        count = (
            supabase.table("notifications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .neq("status", "read")
            .lte("scheduled_for", datetime.now(timezone.utc).isoformat())
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
                # Fetch salon name and timezone
                salon_timezone = "America/New_York"  # Default
                if appt.get("salon_id"):
                    salon_resp = (
                        supabase.table("salons")
                        .select("name, timezone")
                        .eq("id", appt["salon_id"])
                        .single()
                        .execute()
                    )
                    if salon_resp.data:
                        if salon_resp.data.get("name"):
                            salon_name = salon_resp.data["name"]
                        if salon_resp.data.get("timezone"):
                            salon_timezone = salon_resp.data["timezone"]
                
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
                
                # Format appointment time in salon's timezone
                if appt.get("start_at"):
                    try:
                        start_dt_utc = datetime.fromisoformat(appt["start_at"].replace("Z", "+00:00"))
                        if start_dt_utc.tzinfo is None:
                            start_dt_utc = start_dt_utc.replace(tzinfo=timezone.utc)
                        else:
                            start_dt_utc = start_dt_utc.astimezone(timezone.utc)
                        
                        # Convert to salon's timezone
                        try:
                            from zoneinfo import ZoneInfo
                            salon_tz = ZoneInfo(salon_timezone)
                            start_dt_local = start_dt_utc.astimezone(salon_tz)
                        except Exception:
                            # Fallback to UTC if timezone conversion fails
                            start_dt_local = start_dt_utc
                        
                        appt_time = start_dt_local.strftime("%I:%M %p").lstrip("0")
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


