from functools import wraps
from flask import g
from services.notification_service import NotificationService
from datetime import datetime


def notify(
    recipients=None,
    event_type=None,
    title=None,
    message_template=None,
    message_templates=None,
    related_key=None,
    schedule_func=None,
):
    """
    Decorator to automatically send notifications after a successful route execution.

    Args:
        recipients (list[str]): Roles, user UUIDs, or identifiers to notify (e.g., ['admins', 'salon_owner'])
        event_type (str): Notification type (e.g., 'salon_verification', 'appointment_update')
        title (str): Notification title
        message_template (str): Message with placeholders like {reason}, {salon_id}, {user_id}
        related_key (str): Optional key to specify which route arg is the related_id (default auto-detect)
        schedule_func (callable): Optional function to schedule follow-up notifications (like appointment reminders)

    """

    recipients = recipients or []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            response = func(*args, **kwargs)

            # --- Normalize the response ---
            status_code = 200
            payload = {}

            if isinstance(response, tuple):
                # Handles cases like: return jsonify(data), 200
                try:
                    payload = response[0].get_json(force=True)
                except Exception:
                    payload = {}
                status_code = response[1]

            elif hasattr(response, "status_code"):
                # Handles cases like: return jsonify(data)
                status_code = getattr(response, "status_code", 200)
                try:
                    payload = response.get_json(force=True)
                except Exception:
                    payload = {}

            # Only proceed for successful responses (2xx)
            if 200 <= status_code < 300:
                try:
                    context = {
                        "user_id": g.user.get("sub"),
                        "user_role": g.user.get("role"),
                        **getattr(g, "_notify_context", {}),  # Optional dynamic data
                        **payload,  
                        **kwargs,   
                    }
                    
                    # Helper function to format date
                    def format_date(date_str):
                        if not date_str:
                            return date_str
                        try:
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            return dt.strftime("%m/%d/%y at %I:%M %p")
                        except Exception:
                            return date_str  # Fallback to raw if parsing fails
                    
                    # Format start_at if it exists in payload directly
                    if "start_at" in payload and isinstance(payload["start_at"], str):
                        context["start_at"] = format_date(payload["start_at"])
                    
                    # Extract nested appointment values into context if available
                    if "appointment" in payload:
                        appt = payload["appointment"]
                        if "salon" in appt and "name" in appt["salon"]:
                            context["salon_name"] = appt["salon"]["name"]
                        if "service" in appt and "name" in appt["service"]:
                            context["service_name"] = appt["service"]["name"]
                        if "start_at" in appt:
                            # Format date as "MM/DD/YY at H:MM AM/PM"
                            context["start_at"] = format_date(appt["start_at"])
                        if "end_at" in appt:
                            context["end_at"] = appt["end_at"]

                    related_id = None
                    if "id" in payload:
                        related_id = payload["id"]
                    elif "appointment" in payload and "id" in payload["appointment"]:
                        related_id = payload["appointment"]["id"]
                    elif related_key and related_key in kwargs:
                        related_id = kwargs[related_key]
                    elif "salon_id" in kwargs:
                        related_id = kwargs["salon_id"]
                    elif "appointment_id" in kwargs:
                        related_id = kwargs["appointment_id"]
                    elif "user_id" in kwargs:
                        related_id = kwargs["user_id"]

                    # --- Format message using template ---
                    # Determine template for this recipient
                    if message_template:
                        try:
                            message = message_template.format(**context)
                        except KeyError:
                            message = message_template
                    else:
                        message = "A new event occurred."



                    try:
                        NotificationService.broadcast(
                            recipients=recipients,
                            event_type=event_type or "system_event",
                            title=title or "System Notification",
                            message=message,
                            related_id=related_id,
                            messages_by_recipient=message_templates,
                            context=context
                        )

                    except Exception as e:
                        print(f"[notify] Failed to send notification: {e}")
                    
                    if schedule_func and callable(schedule_func):
                        try:
                            schedule_func(related_id)
                            print(f"[notify] Scheduled follow-up notifications for {related_id}")
                        except Exception as e:
                            print(f"[notify] schedule_func failed: {e}")


                except Exception as e:
                    print(f"[notify] General notify wrapper error: {e}")
            return response
        return wrapper
    return decorator

