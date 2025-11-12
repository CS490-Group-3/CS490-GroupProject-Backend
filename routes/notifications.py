from flask import Blueprint, send_file
from datetime import datetime
from config import supabase
import io
import uuid
from pydantic import ValidationError
from services.notification_service import NotificationService

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/track/<notification_id>.png', methods=['GET'])
def track_open(notification_id):
    """Public tracking pixel endpoint for email opens."""
    # Delegate DB logic to service layer
    NotificationService.mark_as_read(notification_id)

    # Return transparent pixel (1x1)
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00' \
            b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00' \
            b'\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return send_file(io.BytesIO(pixel), mimetype='image/gif')
