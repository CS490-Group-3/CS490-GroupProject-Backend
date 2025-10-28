from config import supabase
from datetime import datetime
import uuid

class SalonService:


    #------------------------------------1. SALONS
    """registration and appeals made by salon owners """
    @staticmethod
    def register_salon(data, owner_id, owner_email=None):
        """
        Register a new salon using validated Pydantic data.
        """
        supabase.table("salons").insert({
            "name": data.name,
            "address": data.address,
            "city": data.city,
            "state": data.state,
            "zip_code": data.zip_code,
            "phone": data.phone,
            "email": data.email or owner_email,
            "description": data.description,
            "owner_id": owner_id,
            "status": "pending",
            "license_url": data.license_url,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()



        admins = supabase.table("user_profiles").select("user_id").eq("role", "admin").execute()
        for admin in admins.data:
            supabase.table("notifications").insert({
                "id": str(uuid.uuid4()),
                "user_id": admin["id"],
                "notification_type": "salon_application",
                "title": "New Salon Registration",
                "message": f"A new salon '{data.name}' has been submitted for approval.",
                "status": "pending",
                "related_id": salon_id,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

        return {"message": "Salon registered successfully", "salon_id": salon_id, "status": "pending"}


    #Admin notification format may need to be changed

    
    def appeal_salon(salon_id, user_id):

        salon_response = supabase.table("salons").select("status, owner_id, name").eq("id", salon_id).single().execute()

        if not salon_response.data:
            return {"error": "Salon not found"}, 404

        salon = salon_response.data

        if salon["status"] != "rejected":
            return {
                "error": f"Appeals are only allowed for rejected salons (current status: '{salon['status']}')."
            }, 400

        if salon["owner_id"] != user_id:
            return {"error": "You are not authorized to appeal this salon."}, 403

        supabase.table("salons").update({
            "status": "pending",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        admins = supabase.table("user_profiles").select("user_id").eq("role", "admin").execute()
        for admin in admins.data:
            supabase.table("notifications").insert({
                "id": str(uuid.uuid4()),
                "user_id": admin["id"],
                "notification_type": "salon_appeal",
                "title": "Salon Appeal Submitted",
                "message": f"Salon '{salon['name']}' has appealed its rejection.",
                "status": "pending",
                "related_id": salon_id,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

        return {"message": "Appeal submitted successfully", "new_status": "pending"}




    #--------------------------------------2. ADMINS

    """appeal and rejection done by a user with role of admin, the salon being review must have a current status of pending before review is submitted. Salon owners are notified of decision"""



    @staticmethod
    def approve_salon(salon_id, approver_id):
        supabase.table("salons").update({
            "status": "verified",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        salon = supabase.table("salons").select("name, owner_id").eq("id", salon_id).single().execute()
        owner_id = salon.data["owner_id"]

        supabase.table("notifications").insert({
            "id": str(uuid.uuid4()),
            "user_id": owner_id,
            "notification_type": "salon_verification",
            "title": "Salon Approved",
            "message": f"Your salon '{salon.data['name']}' has been approved.",
            "status": "pending",
            "related_id": salon_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return {"message": "Salon approved successfully"}


    @staticmethod
    def reject_salon(salon_id, approver_id, reason):
        supabase.table("salons").update({
            "status": "rejected",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        salon = supabase.table("salons").select("name, owner_id").eq("id", salon_id).single().execute()
        owner_id = salon.data["owner_id"]

        supabase.table("notifications").insert({
            "id": str(uuid.uuid4()),
            "user_id": owner_id,
            "notification_type": "salon_rejection",
            "title": "Salon Application Rejected",
            "message": f"Your salon '{salon.data['name']}' was rejected. Reason: {reason}",
            "status": "pending",
            "related_id": salon_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return {"message": "Salon rejected", "reason": reason}

