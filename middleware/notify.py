from functools import wraps
from flask import g
from services.notification_service import NotificationService


def notify(
    recipients=None,
    event_type=None,
    title=None,
    message_template=None,
    related_key=None,
):
    """
    Decorator to automatically send notifications after a successful route execution.

    Args:
        recipients (list[str]): Roles, user UUIDs, or identifiers to notify (e.g., ['admins', 'owner'])
        event_type (str): Notification type (e.g., 'salon_verification', 'appointment_update')
        title (str): Notification title
        message_template (str): Message with placeholders like {reason}, {salon_id}, {user_id}
        related_key (str): Optional key to specify which route arg is the related_id (default auto-detect)
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

                    related_id = None
                    if related_key and related_key in kwargs:
                        related_id = kwargs[related_key]
                    elif "salon_id" in kwargs:
                        related_id = kwargs["salon_id"]
                    elif "appointment_id" in kwargs:
                        related_id = kwargs["appointment_id"]
                    elif "user_id" in kwargs:
                        related_id = kwargs["user_id"]

                    # --- Format message using template ---
                    if message_template:
                        try:
                            message = message_template.format(**context)
                        except KeyError as e:
                            print(f"[notify] Missing key {e} in context; using raw message template.")
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
                        )

                    except Exception as e:
                        print(f"[notify] Failed to send notification: {e}")
                except Exception as e:
                    print(f"[notify] General notify wrapper error: {e}")
            return response
        return wrapper
    return decorator

