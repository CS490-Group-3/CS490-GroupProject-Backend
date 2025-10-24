from flask import Blueprint, request, jsonify
import re, uuid
from datetime import datetime
from supabase_client import supabase
import jwt, os


salon_bp = Blueprint("salon_bp", __name__)


PHONE_REGEX = re.compile(r"^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")




# Register a salon
#requires at least 1 of phone number or email

@salon_bp.route("/register", methods=["POST"])
def register_salon():
    data = request.get_json()

    required_fields = ["owner_id", "name", "address", "city", "state", "zip_code"]
    missing = [f for f in required_fields if f not in data or not str(data[f]).strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()

    if not email and not phone:
        return jsonify({"error": "At least one contact method (email or phone) is required"}), 400

    if email and not EMAIL_REGEX.match(email):
        return jsonify({"error": "Invalid email format"}), 400

    if phone and not PHONE_REGEX.match(phone):
        return jsonify({"error": "Invalid phone number format. Expected xxx-xxx-xxxx"}), 400

    salon_id = str(uuid.uuid4())

    try:
        response = supabase.table("salons").insert({
            "id": salon_id,
            "owner_id": data["owner_id"],    
            "name": data["name"],
            "description": data.get("description"),
            "address": data["address"],
            "city": data["city"],
            "state": data["state"],
            "zip_code": data["zip_code"],
            "phone": phone if phone else None,
            "email": email if email else None,
            "logo_url": data.get("logo_url"),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()

        return jsonify({
            "message": "Salon registration submitted successfully",
            "salon_id": salon_id,
            "status": "pending"
        }), 201


    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Read salons
@salon_bp.route("/", methods=["GET"])
def get_salons():
    rows = query_db("SELECT id, name, city, state FROM salons")
    return jsonify(rows)


