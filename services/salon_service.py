from config import supabase
from datetime import datetime
from services.upload_file import StorageService
from zoneinfo import ZoneInfo
import uuid

class SalonService:
    #------------------------------------helpers
    @staticmethod
    def _clean_tz(tz: str | None) -> str:
        DEFAULT_TZ = "America/New_York"
        if not tz:
            return DEFAULT_TZ
        try:
            ZoneInfo(tz)   # raises if invalid
            return tz
        except Exception:
            return DEFAULT_TZ

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
            "timezone": SalonService._clean_tz(getattr(data, "timezone", None)),
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

    @staticmethod
    def add_service_provider(salon_id, provider_id, bio=None, specialties=None, years_experience=None, is_active=True):
        """
        Add a service provider (barber) to a salon.
        """
        specialties = specialties or []

        try:
            supabase.table("barbers").insert({
                "salon_id": salon_id,
                "user_id": provider_id,
                "bio": bio,
                "specialties": specialties,
                "years_experience": years_experience,
                "is_active": is_active,
            }).execute()
            return {"message": "Service provider added to salon successfully"}, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def create_service(salon_id, name, description, duration_minutes, price, is_active=True):
        """
        Create a new service for a salon.
        """
        try:
            supabase.table("services").insert({
                "salon_id": salon_id,
                "name": name,
                "description": description,
                "duration_minutes": duration_minutes,
                "price": price,
                "is_active": is_active,
            }).execute()
            return {"message": "Service created successfully"}, None
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_service(service_id):
        """
        Retrieve service details by ID.
        """
        try:
            response = supabase.table("services").select("*").eq("id", service_id).single().execute()
            if not response.data:
                return "Service not found",
            return response.data, None
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_salon_services(salon_id, data=None):
        """
        Get all services for a salon.
        """
        try:
            if data is None:
                response = supabase.table("services").select("*").eq("salon_id", salon_id).execute()
                if not response.data:
                    return {"error":"No services found for this salon"}
            else:
                query = supabase.table("services").select("*").eq("salon_id", salon_id)

                # Apply search filter
                search = data.get("search", "")
                if search != "":
                    query = query.ilike("name", f"%{search}%")

                # Apply additional filters
                filters = data.get("filters", {})
                if "is_active" in filters:
                    query = query.eq("is_active", filters.get("is_active"))
                if "price_range" in filters:
                    price_min, price_max = filters.get("price_range")
                    query = query.gte("price", price_min).lte("price", price_max)
                if "duration_range" in filters:
                    duration_min, duration_max = filters.get("duration_range")
                    query = query.gte("duration_minutes", duration_min).lte("duration_minutes", duration_max)
        
                response = query.execute()
                if not response.data:
                    return {"error":"No services found matching the criteria"}
                if "tags" in filters:
                    tags = filters.get("tags", [])
                    services_with_tags = supabase.table("service_tags").select("service_id").in_("tag_id", tags).execute()
                    service_ids = {item["service_id"] for item in services_with_tags.data}
                    filtered_services = [service for service in response.data if service["id"] in service_ids]
                    return filtered_services
                
            return response.data, None
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_salon_employees(salon_id):
        """
        Get all service providers (barbers) for a salon.
        """
        try:
            #matches salon_id in barbers table to get user details from user_profiles
            response = supabase.table("barbers").select("*, user_details(*)").eq("salon_id", salon_id).execute()
            if not response.data:
                return {"error":"No employees found for this salon"}
            return response.data
        except Exception as e:
            return None, str(e)
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
        

        allowed_fields = ["name", "description", "address", "phone", "license_url", "logo_url", "timezone"]
        valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields}

        if license_file:
            valid_updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        if logo_file:
            valid_updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")
        if "timezone" in valid_updates:
            valid_updates["timezone"] = SalonService._clean_tz(valid_updates["timezone"])

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
