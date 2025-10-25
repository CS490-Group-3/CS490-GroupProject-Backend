from flask import Blueprint, request, jsonify
import re, uuid
from datetime import datetime
from supabase_client import supabase
import jwt, os


salon_bp = Blueprint("salon_bp", __name__)


PHONE_REGEX = re.compile(r"^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")




#-------------------------------------------------------------1.Register a salon
#requires at least 1 of phone number or email

@salon_bp.route("/register", methods=["POST"])
def register_salon():
    data = request.get_json()

    owner_id = data.get("owner_id")

    required_fields = ["owner_id", "name", "address", "city", "state", "zip_code"]
    missing = [f for f in required_fields if f not in data or not str(data[f]).strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        user_check = supabase.table("users").select("role").eq("id", owner_id).single().execute()

        if not user_check.data:
            return jsonify({"error": "User not found"}), 404

        if user_check.data["role"] != "salon_owner":
            return jsonify({"error": "Only users with 'salon_owner' role can register a salon"}), 403

    except Exception as e:
        return jsonify({"error": f"Role validation failed: {str(e)}"}), 500


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

        admins = supabase.table("users").select("id").eq("role", "admin").execute()
        for admin in admins.data:
            supabase.table("notifications").insert({
            "id": str(uuid.uuid4()),
            "user_id": admin["id"],
            "notification_type": "salon_verification", 
            "title": "New Salon Registration",
            "message": f"A new salon '{data['name']}' has been submitted for review.",
            "status": "pending",
            "related_id": salon_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()


        return jsonify({
            "message": "Salon registration submitted successfully",
            "salon_id": salon_id,
            "status": "pending"
        }), 201

        


    except Exception as e:
        return jsonify({"error": str(e)}), 500


#Salon appeal submission

@salon_bp.route("/<salon_id>/appeal", methods=["PUT"])
def appeal_salon(salon_id):
    data = request.get_json()
    owner_id = data.get("owner_id")
    appeal_message = data.get("message", "Salon owner has appealed the rejection.")

    if not owner_id:
        return jsonify({"error": "Missing owner_id"}), 400

    try:
        salon = supabase.table("salons").select("owner_id, name, status").eq("id", salon_id).single().execute()
        if not salon.data:
            return jsonify({"error": "Salon not found"}), 404
        if salon.data["owner_id"] != owner_id:
            return jsonify({"error": "Unauthorized: not your salon"}), 403
        if salon.data["status"] != "rejected":
            return jsonify({"error": "Salon must be rejected before appealing"}), 400

        supabase.table("salons").update({
            "status": "pending",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        admins = supabase.table("users").select("id").eq("role", "admin").execute()
        for admin in admins.data:
            supabase.table("notifications").insert({
                "id": str(uuid.uuid4()),
                "user_id": admin["id"],
                "notification_type": "salon_verification",  #maybe new enum type for appeal notifications
                "title": "Salon Appeal Submitted",
                "message": f"'{salon.data['name']}' has appealed its rejection. Message: {appeal_message}",
                "status": "pending", 
                "related_id": salon_id,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

        return jsonify({
            "message": "Appeal submitted",
            "salon_id": salon_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




#-------------------------------------------------------------- 2.Approve a salon (ADMIN)

#function checking admin role of user before allowing actions

def is_admin(user_id):
    try:
        result = supabase.table("users").select("role").eq("id", user_id).single().execute()
        if result.data and result.data.get("role") == "admin":
            return True
        return False
    except Exception as e:
        print("Error checking admin role:", e)
        return False



#Approving a salon
#approver need the role of admin

@salon_bp.route("/<salon_id>/approve", methods=["PUT"])
def approve_salon(salon_id):
    data = request.get_json()
    approver_id = data.get("approver_id")

    if not approver_id or not is_admin(approver_id):
        return jsonify({"error": "Unauthorized: Admin access required"}), 403

    try:
        salon = supabase.table("salons").select("owner_id, name").eq("id", salon_id).single().execute()
        if not salon.data:
            return jsonify({"error": "Salon not found"}), 404

        owner_id = salon.data["owner_id"]

        supabase.table("salons").update({
            "status": "verified",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        supabase.table("notifications").insert({
            "id": str(uuid.uuid4()),
            "user_id": owner_id,
            "notification_type": "salon_verification",
            "title": "Salon Approved",
            "message": f"Your salon '{salon.data['name']}' has been approved!",
            "status": "pending",
            "related_id": salon_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return jsonify({"message": "Salon approved successfully", "salon_id": salon_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



#Rejecting a salon


@salon_bp.route("/<salon_id>/reject", methods=["PUT"])
def reject_salon(salon_id):
    data = request.get_json()
    rejection_reason = data.get("message", "Your salon application was rejected.")
    approver_id = data.get("approver_id")

    if not approver_id or not is_admin(approver_id):
        return jsonify({"error": "Unauthorized: Admin access required"}), 403

    try:
        salon = supabase.table("salons").select("owner_id, name").eq("id", salon_id).single().execute()

        if not salon.data:
            return jsonify({"error": "Salon not found"}), 404

        owner_id = salon.data["owner_id"]

        supabase.table("salons").update({
            "status": "rejected",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        # Step 3: create rejection notification
        supabase.table("notifications").insert({
            "id": str(uuid.uuid4()),
            "user_id": owner_id,
            "notification_type": "salon_verification",
            "title": "Salon Application Rejected",
            "message": f"Your salon '{salon.data['name']}' was rejected. Reason: {rejection_reason}",
            "status": "pending",  
            "related_id": salon_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return jsonify({
            "message": "Salon rejected successfully and owner notified",
            "salon_id": salon_id,
            "reason": rejection_reason
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500






# Read salons
@salon_bp.route("/", methods=["GET"])
def get_salons():
    rows = query_db("SELECT id, name, city, state FROM salons")
    return jsonify(rows)


