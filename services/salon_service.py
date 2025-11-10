from config import supabase
from datetime import datetime
from services.upload_file import StorageService
import uuid

class SalonService:


    #------------------------------------1. SALONS
    """registration and appeals made by salon owners """
    @staticmethod
    def register_salon(data, owner_id, owner_email=None, logo_file=None, license_file=None):
        """
        Register a new salon using validated Pydantic data.
        """
        license_url = data.license_url
        logo_url = data.logo_url if hasattr(data, "logo_url") else None


        new = supabase.table("salons").insert({
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
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        salon_id = new.data[0]["id"]


        updates = {}
        if license_file:
            updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        elif license_url:
            updates["license_url"] = license_url

        if logo_file:
            updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")

        if updates:
            supabase.table("salons").update(updates).eq("id", salon_id).execute()
        
        """
        admins = supabase.table("user_profiles").select("user_id").eq("role", "admin").execute()
        for admin in admins.data:
            supabase.table("notifications").insert({
                "id": str(uuid.uuid4()),
                "user_id": admin["user_id"],
                "notification_type": "salon_verification",
                "title": "New Salon Registration",
                "message": f"A new salon '{data.name}' has been submitted for approval.",
                "status": "pending",
                "related_id": salon_id,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        """
        return {"message": "Salon registered successfully", "salon_name": data.name, "salon_id": salon_id,  "verification_status": "pending"}


    #Admin notification format may need to be changed

    @staticmethod
    def appeal_salon(salon_id, user_id, updates=None, logo_file=None, license_file=None):

        salon_response = supabase.table("salons").select("status, owner_id, name").eq("id", salon_id).single().execute()

        if not salon_response.data:
            return {"error": "Salon not found"}, 404

        salon = salon_response.data

        if salon["status"] != "rejected":
            return {
                "error": f"Appeals are only allowed for rejected salons (current status: '{salon['status']}')."},400

        if salon["owner_id"] != user_id:
            return {"error": "You are not authorized to appeal this salon."}, 403
        

        allowed_fields = ["name", "description", "address", "phone", "license_url", "logo_url"]
        valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields}

        if license_file:
            valid_updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        if logo_file:
            valid_updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")

        if valid_updates:
            valid_updates["status"] = "pending"
            supabase.table("salons").update(valid_updates).eq("id", salon_id).execute()
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
        return {"message": "Salon approved successfully"}


    @staticmethod
    def reject_salon(salon_id, approver_id, reason):
        supabase.table("salons").update({
            "status": "rejected",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        salon = supabase.table("salons").select("name, owner_id").eq("id", salon_id).single().execute()
        owner_id = salon.data["owner_id"]

        return {"message": "Salon rejected", "reason": reason}


  
    @staticmethod
    def get_pending_salons():
        response = supabase.table("salons").select("*").eq("status", "pending").execute()
        return response.data


    @staticmethod
    def get_status_history(salon_id: str):
        try:
            response = (
                supabase.table("notifications")
                .select("title, message, created_at, user_id")
                .eq("notification_type", "salon_verification")
                .eq("related_id", str(salon_id))
                .order("created_at", desc=False)
                .execute()
            )
            return {"timeline": response.data, "count": len(response.data)}
        except Exception as e:
            raise Exception(f"Failed to fetch salon status history: {e}")
