from flask import Blueprint, request, jsonify
import re, uuid
from datetime import datetime
from app.db import query_db
import jwt, os


salon_bp = Blueprint("salon_bp", __name__)

PHONE_REGEX = re.compile(r"^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET") 
"""
auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
        role = payload.get("role")
    except Exception as e:
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401

    # only salon owners can register
    if role != "salon_owner":
        return jsonify({"error": "Only salon owners can register salons"}), 403

"""



# Register a salon

@salon_bp.route("/register", methods=["POST"])
def register_salon():

    user_id = "56136dd5-c40d-4e70-9a66-ab80ff43c218"



    data = request.get_json()
    required = ["name", "address", "city", "state", "zip_code"]
    missing = [f for f in required if f not in data or not data[f]]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    salon_id = str(uuid.uuid4())
   #needed for jwt
   #email = data.get("email") or payload.get("email")
    email = data.get("email") 


    try:
        query_db(
            """
            INSERT INTO salons
                (id, owner_id, name, description, address, city, state, zip_code,
                 phone, email, status, created_at, updated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            """,
            (
                salon_id,
                user_id,
                data["name"],
                data.get("description"),
                data["address"],
                data["city"],
                data["state"],
                data["zip_code"],
                data.get("phone"),
                email,
                datetime.utcnow(),
                datetime.utcnow(),
            ),
            commit=True,
        )
        return jsonify({"message": "Salon registration submitted", "status": "pending"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500




# Read salons
@salon_bp.route("/", methods=["GET"])
def get_salons():
    rows = query_db("SELECT id, name, city, state FROM salons")
    return jsonify(rows)



