from flask import Blueprint, send_file, jsonify, g
from datetime import datetime
from config import supabase
import io
import uuid
from pydantic import ValidationError
from services.notification_service import NotificationService
from middleware.auth import login_required
from middleware.error_logging import auto_log_errors
from flasgger.utils import swag_from


notifications_bp = Blueprint('notifications', __name__, url_prefix="/api/notifications")

"""
@notifications_bp.route('/track/<notification_id>.png', methods=['GET'])
def track_open(notification_id):
    # Delegate DB logic to service layer
    NotificationService.mark_as_read(notification_id)

    # Return transparent pixel (1x1)
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00' \
            b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00' \
            b'\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return send_file(io.BytesIO(pixel), mimetype='image/gif')
"""

@notifications_bp.get("/")
@auto_log_errors
@login_required()
@swag_from("../docs/notifications_list.yml")
def get_notifications():
    user_id = g.user["sub"]
    rows = NotificationService.get_user_notifications(user_id)
    return jsonify(rows), 200


@notifications_bp.get("/unread-count")
@auto_log_errors
@login_required()
@swag_from("../docs/notifications_unread_count.yml")
def unread_count():
    user_id = g.user["sub"]
    count = NotificationService.get_unread_count(user_id)
    return jsonify({"unread": count}), 200


@notifications_bp.patch("/<notif_id>/mark-read")
@auto_log_errors
@login_required()
@swag_from("../docs/notifications_mark_read.yml")
def mark_notif_read(notif_id):
    user_id = g.user["sub"]
    updated = NotificationService.mark_as_read(user_id, notif_id)
    return jsonify(updated), 200


@notifications_bp.patch("/mark-all-read")
@auto_log_errors
@login_required()
@swag_from("../docs/notifications_mark_all_read.yml")
def mark_all_read():
    user_id = g.user["sub"]
    updated = NotificationService.mark_all_as_read(user_id)
    return jsonify(updated), 200
