from config import supabase
from datetime import datetime, time as dt_time
from services.upload_file import StorageService
from services.audit_logging_service import AuditLoggingService
from services.error_logging_service import ErrorLoggingService
from zoneinfo import ZoneInfo
import uuid
import traceback

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

    @staticmethod
    def _format_price(value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _full_address(row):
        parts = [
            row.get("address"),
            row.get("city"),
            row.get("state"),
            row.get("zip_code"),
        ]
        return ", ".join([p for p in parts if p])

    @staticmethod
    def _serialize_service(row):
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description"),
            "duration_minutes": row.get("duration_minutes"),
            "price": SalonService._format_price(row.get("price")),
            "is_active": row.get("is_active", True),
        }
    
    @staticmethod
    def _normalize_time(value):
        if value is None:
            return None
        if isinstance(value, dt_time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, str):
            val = value.strip()
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(val, fmt).strftime("%H:%M:%S")
                except Exception:
                    continue
        return None

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
        if getattr(new, "error", None):
            raise ValueError(f"salons insert failed: {getattr(new, 'error', None)}")

        salon_id = new.data[0]["id"]


        updates = {}
        if license_file:
            updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        elif license_url:
            updates["license_url"] = license_url

        if logo_file:
            updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")
        elif logo_url:
            updates["logo_url"] = logo_url

        if updates:
            supabase.table("salons").update(updates).eq("id", salon_id).execute()

        # Log audit
        AuditLoggingService.log_audit(
            table_name='salons',
            record_id=salon_id,
            action='INSERT',
            new_values={'name': data.name, 'status': 'pending', 'owner_id': owner_id},
            changed_by=owner_id
        )

        return {
            "message": "Salon registered successfully. Verification required.",
            "salon_name": data.name,
            "salon_id": salon_id,
            "verification_status": "pending",
        }

    @staticmethod
    def list_salons(search=None, location=None, service_names=None, sort="top"):
        """
        Return verified salons with optional filters.
        """
        try:
            response = (
                supabase.table("salons")
                .select("*")
                .eq("status", "verified")
                .order("created_at", desc=False)
                .execute()
            )
            salons = response.data or []
            search_lc = (search or "").strip().lower()
            location_lc = (location or "").strip().lower()
            service_filters = [s.strip().lower() for s in (service_names or []) if s.strip()]

            if search_lc:
                salons = [
                    row for row in salons
                    if search_lc in (row.get("name") or "").lower()
                    or search_lc in (row.get("description") or "").lower()
                    or search_lc in SalonService._full_address(row).lower()
                ]

            if location_lc:
                salons = [
                    row for row in salons
                    if location_lc in (row.get("city") or "").lower()
                    or location_lc in (row.get("state") or "").lower()
                    or location_lc in (row.get("zip_code") or "").lower()
                    or location_lc in (row.get("address") or "").lower()
                ]

            salon_ids = [row["id"] for row in salons if row.get("id")]
            services_map = {}
            if salon_ids:
                svc_resp = (
                    supabase.table("services")
                    .select("id,name,salon_id,duration_minutes,price")
                    .in_("salon_id", salon_ids)
                    .execute()
                )
                for svc in svc_resp.data or []:
                    services_map.setdefault(svc["salon_id"], []).append(SalonService._serialize_service(svc))

            if service_filters:
                salons = [
                    row for row in salons
                    if all(
                        any((svc.get("name") or "").lower() == target for svc in services_map.get(row["id"], []))
                        for target in service_filters
                    )
                ]

            rating_map = {}
            if salon_ids:
                rev_resp = (
                    supabase.table("reviews")
                    .select("salon_id,rating")
                    .in_("salon_id", salon_ids)
                    .execute()
                )
                for rev in rev_resp.data or []:
                    sid = rev["salon_id"]
                    entry = rating_map.setdefault(sid, {"sum": 0, "count": 0})
                    entry["sum"] += rev.get("rating") or 0
                    entry["count"] += 1

            results = []
            for row in salons:
                rid = row["id"]
                rating = rating_map.get(rid, {"sum": 0, "count": 0})
                avg = (rating["sum"] / rating["count"]) if rating["count"] else None
                services = services_map.get(rid, [])
                results.append({
                    "id": rid,
                    "name": row.get("name"),
                    "created_at": row.get("created_at"),
                    "description": row.get("description"),
                    "address": SalonService._full_address(row),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "zip_code": row.get("zip_code"),
                    "phone": row.get("phone"),
                    "email": row.get("email"),
                    "rating": round(avg, 1) if avg is not None else None,
                    "reviews_count": rating["count"],
                    "logo_url": row.get("logo_url"),
                    "services": services[:4],
                })

            if sort == "top":
                results.sort(key=lambda x: x.get("rating") or 0, reverse=True)
            elif sort == "recent":
                results.sort(key=lambda x: x.get("created_at") or "", reverse=True)

            return results, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def get_owned_salon(owner_id: str):
        """
        Fetch the first/only salon for a given owner.
        """
        try:
            resp = (
                supabase.table("salons")
                .select("id,name,status,created_at,city,state,zip_code,address,phone,email,description,timezone,logo_url,license_url")
                .eq("owner_id", owner_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            data = resp.data or []
            return (data[0] if data else None), None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def get_salon_detail(salon_id):
        """
        Fetch a single salon with services, team, hours, and rating summary.
        """
        try:
            salon_resp = (
                supabase.table("salons")
                .select("*")
                .eq("id", salon_id)
                .single()
                .execute()
            )
            salon = salon_resp.data
            if not salon:
                return None, "Salon not found"

            services_res = SalonService.get_salon_services(salon_id)
            if isinstance(services_res, tuple):
                services, _ = services_res
            else:
                services = services_res or []

            employees_res = SalonService.get_salon_employees(salon_id)
            if isinstance(employees_res, tuple):
                employees, _ = employees_res
            else:
                employees = employees_res or []

            hours_resp = (
                supabase.table("salon_hours")
                .select("day_of_week,open_time,close_time,is_closed")
                .eq("salon_id", salon_id)
                .order("day_of_week", desc=False)
                .execute()
            )
            hours = hours_resp.data or []

            reviews_resp = (
                supabase.table("reviews")
                .select("rating")
                .eq("salon_id", salon_id)
                .execute()
            )
            ratings = reviews_resp.data or []
            count = len(ratings)
            avg = round(sum(r.get("rating") or 0 for r in ratings) / count, 1) if count else None

            return {
                "id": salon.get("id"),
                "name": salon.get("name"),
                "description": salon.get("description"),
                "address": SalonService._full_address(salon),
                "city": salon.get("city"),
                "state": salon.get("state"),
                "zip_code": salon.get("zip_code"),
                "phone": salon.get("phone"),
                "email": salon.get("email"),
                "logo_url": salon.get("logo_url"),
                "license_url": salon.get("license_url"),
                "status": salon.get("status"),
                "services": services or [],
                "employees": employees or [],
                "hours": hours,
                "rating": avg,
                "reviews_count": count,
                "gallery": [],
            }, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def list_reviews(salon_id, limit=6):
        """
        Return latest reviews for a salon, including responses.
        """
        try:
            response = (
                supabase.table("reviews")
                .select("id,salon_id,user_id,appointment_id,rating,comment,created_at")
                .eq("salon_id", salon_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            reviews = response.data or []
            user_ids = [row["user_id"] for row in reviews if row.get("user_id")]
            profiles = {}
            if user_ids:
                prof = (
                    supabase.table("user_details")
                    .select("id,first_name,last_name")
                    .in_("id", user_ids)
                    .execute()
                )
                profiles = {row["id"]: row for row in (prof.data or [])}

            # Fetch responses for all reviews
            review_ids = [row["id"] for row in reviews if row.get("id")]
            responses = {}
            if review_ids:
                responses_resp = (
                    supabase.table("review_responses")
                    .select("*")
                    .in_("review_id", review_ids)
                    .execute()
                )
                responses = {r["review_id"]: r for r in (responses_resp.data or [])}

            output = []
            for row in reviews:
                profile = profiles.get(row.get("user_id"), {})
                review_data = {
                    "id": row.get("id"),
                    "stars": row.get("rating"),
                    "text": row.get("comment"),
                    "created_at": row.get("created_at"),
                    "user": {
                        "name": f"{profile.get('first_name','')} {profile.get('last_name','')}".strip() or "Guest"
                    }
                }
                # Attach response if it exists
                if row.get("id") in responses:
                    review_data["response"] = responses[row.get("id")]
                output.append(review_data)
            return output, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def add_service_provider(salon_id, provider_id, bio=None, years_experience=None, is_active=True):
        """
        Add a service provider (barber) to a salon.
        """
        try:
            barber_data = {
                "salon_id": salon_id,
                "user_id": provider_id,
                "bio": bio,
                "years_experience": years_experience,
                "is_active": is_active,
            }
            response = supabase.table("barbers").insert(barber_data).execute()
            created_id = response.data[0]["id"] if response.data else None
            
            # Log audit
            if created_id:
                AuditLoggingService.log_audit(
                    table_name='barbers',
                    record_id=created_id,
                    action='INSERT',
                    new_values=barber_data,
                    changed_by=None  # Could get from context if needed
                )
            
            return {"message": "Service provider added to salon successfully"}, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
        
    @staticmethod
    def create_service(salon_id, name, description, duration_minutes, price, is_active=True):
        """
        Create a new service for a salon.
        """
        try:
            service_data = {
                "salon_id": salon_id,
                "name": name,
                "description": description,
                "duration_minutes": duration_minutes,
                "price": price,
                "is_active": is_active,
            }
            response = supabase.table("services").insert(service_data).execute()
            created_id = response.data[0]["id"] if response.data else None
            
            # Log audit
            if created_id:
                AuditLoggingService.log_audit(
                    table_name='services',
                    record_id=created_id,
                    action='INSERT',
                    new_values=service_data,
                    changed_by=None  # Could get from context if needed
                )
            
            return {"message": "Service created successfully"}, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    @staticmethod
    def get_salon_services(salon_id, data=None):
        """
        Get all services for a salon.
        Returns tuple: (services_list, error_message)
        """
        try:
            if data is None:
                response = supabase.table("services").select("*").eq("salon_id", salon_id).execute()
                if not response.data:
                    return [], None  # Return empty list, not error
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
                    return [], None  # Return empty list, not error
                if "tags" in filters:
                    tags = filters.get("tags", [])
                    services_with_tags = supabase.table("service_tags").select("service_id").in_("tag_id", tags).execute()
                    service_ids = {item["service_id"] for item in services_with_tags.data}
                    filtered_services = [service for service in response.data if service["id"] in service_ids]
                    return filtered_services, None
                
            return response.data or [], None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def get_salon_employees(salon_id):
        """
        Get all service providers (barbers) for a salon.
        """
        try:
            response = (
                supabase.table("barbers")
                .select("id,user_id,bio,years_experience,is_active")
                .eq("salon_id", salon_id)
                .execute()
            )
            rows = response.data or []
            user_ids = [row["user_id"] for row in rows if row.get("user_id")]
            profiles = {}
            if user_ids:
                try:
                    prof_res = (
                        supabase.table("user_profiles")
                        .select("user_id,first_name,last_name,profile_image_url")
                        .in_("user_id", user_ids)
                        .execute()
                    )
                    profiles = {row["user_id"]: row for row in (prof_res.data or [])}
                except Exception:
                    alt = (
                        supabase.table("user_details")
                        .select("id,first_name,last_name,profile_image_url")
                        .in_("id", user_ids)
                        .execute()
                    )
                    profiles = {
                        row["id"]: {
                            "first_name": row.get("first_name"),
                            "last_name": row.get("last_name"),
                            "profile_image_url": row.get("profile_image_url"),
                        }
                        for row in (alt.data or [])
                    }

            employees = []
            for row in rows:
                profile = profiles.get(row.get("user_id"), {})
                employees.append({
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "name": f"{profile.get('first_name','')} {profile.get('last_name','')}".strip() or "Team member",
                    "bio": row.get("bio"),
                    "years_experience": row.get("years_experience"),
                    "is_active": row.get("is_active", True),
                    "avatar": profile.get("profile_image_url"),
                })
            return employees, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    @staticmethod
    def salon_owner_employee_search(query_str):
        """
        Search by email for service providers (barbers) to add to a salon.
        Returns users with role "barber" who are NOT currently in any salon (not in barbers table).
        """
        try:
            response= supabase.table("user_details").select("id,email,first_name,last_name").ilike("email", f"%{query_str}%").eq("role", "barber").execute()
            if not response.data:
                return None, "No service providers found matching the search criteria"
            
            print("Search response data:", response.data)
            
            user_ids= [item["id"] for item in response.data]
            barber_response= supabase.table("barbers").select("user_id").in_("user_id", user_ids).eq("is_active", True).execute()
            
            active_user_ids = {item["user_id"] for item in barber_response.data}
            # Filter to only return users NOT in barbers table, and return full user details
            available_users = [item for item in response.data if item["id"] not in active_user_ids]
            print("Found available users:", available_users)
            return available_users, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    @staticmethod
    def get_salon_tags(salon_id):
        """
        Get all unique service tags for a salon.
        """
        try:
            tags_response = supabase.table("salon_tags").select("*, tags(name)").eq("salon_id", salon_id).execute()
            return tags_response.data, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    #Admin notification format may need to be changed

    @staticmethod
    def get_salon_hours(salon_id: str):
        """
        Fetch weekly salon hours ordered by day_of_week.
        """
        try:
            resp = (
                supabase.table("salon_hours")
                .select("*")
                .eq("salon_id", salon_id)
                .order("day_of_week", desc=False)
                .execute()
            )
            return resp.data or [], None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def upsert_salon_hours(salon_id: str, hours: list):
        """
        Replace salon hours with the provided weekly schedule.
        """
        try:
            if not isinstance(hours, list) or not hours:
                return None, "hours must be a non-empty list"

            normalized = []
            seen_days = set()

            for entry in hours:
                if not isinstance(entry, dict):
                    return None, "Each hours entry must be an object"

                day = entry.get("day_of_week")
                is_closed = bool(entry.get("is_closed", False))
                open_time = entry.get("open_time")
                close_time = entry.get("close_time")

                if day is None or not isinstance(day, int) or day < 0 or day > 6:
                    return None, "day_of_week must be an integer between 0 (Sunday) and 6 (Saturday)"
                if day in seen_days:
                    return None, "Duplicate day_of_week entries are not allowed"
                seen_days.add(day)

                norm_open = SalonService._normalize_time(open_time)
                norm_close = SalonService._normalize_time(close_time)

                if not is_closed:
                    if not norm_open or not norm_close:
                        return None, f"open_time and close_time are required for day {day}"
                    if norm_open >= norm_close:
                        return None, f"open_time must be before close_time for day {day}"
                else:
                    # DB has NOT NULL on open_time/close_time; store zeros for closed days
                    norm_open = "00:00:00"
                    norm_close = "00:00:00"

                normalized.append({
                    "salon_id": salon_id,
                    "day_of_week": day,
                    "open_time": norm_open,
                    "close_time": norm_close,
                    "is_closed": is_closed,
                })

            # Auto-fill any missing days as closed
            for missing_day in range(7):
                if missing_day not in seen_days:
                    normalized.append({
                        "salon_id": salon_id,
                        "day_of_week": missing_day,
                        "open_time": "00:00:00",
                        "close_time": "00:00:00",
                        "is_closed": True,
                    })

            normalized.sort(key=lambda x: x["day_of_week"])

            delete_resp = supabase.table("salon_hours").delete().eq("salon_id", salon_id).execute()
            if getattr(delete_resp, "error", None):
                print(f"[salon_hours] delete failed for salon_id={salon_id}: {delete_resp.error}")
                return None, f"salon_hours delete failed: {delete_resp.error}"
            insert_resp = supabase.table("salon_hours").insert(normalized).execute()
            if getattr(insert_resp, "error", None):
                print(f"[salon_hours] insert failed for salon_id={salon_id}: {insert_resp.error} payload_count={len(normalized)} payload={normalized}")
                return None, f"salon_hours insert failed: {insert_resp.error}"
            return normalized, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            traceback.print_exc()
            return None, f"salon_hours upsert exception: {e}"

    @staticmethod
    def upsert_salon_hour_day(salon_id: str, day_of_week: int, payload: dict):
        """
        Create or update a single day's hours.
        """
        try:
            if day_of_week is None or not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return None, "day_of_week must be an integer between 0 (Sunday) and 6 (Saturday)"

            is_closed = bool(payload.get("is_closed", False))
            open_time = payload.get("open_time")
            close_time = payload.get("close_time")

            norm_open = SalonService._normalize_time(open_time)
            norm_close = SalonService._normalize_time(close_time)

            if not is_closed:
                if not norm_open or not norm_close:
                    return None, "open_time and close_time are required when is_closed is false"
                if norm_open >= norm_close:
                    return None, "open_time must be before close_time"
            else:
                norm_open = "00:00:00"
                norm_close = "00:00:00"

            existing = (
                supabase.table("salon_hours")
                .select("id")
                .eq("salon_id", salon_id)
                .eq("day_of_week", day_of_week)
                .maybe_single()
                .execute()
            )
            row = {
                "salon_id": salon_id,
                "day_of_week": day_of_week,
                "open_time": norm_open,
                "close_time": norm_close,
                "is_closed": is_closed,
            }

            if getattr(existing, "data", None):
                upd = supabase.table("salon_hours").update(row).eq("id", existing.data["id"]).execute()
                if getattr(upd, "error", None):
                    return None, str(upd.error)
            else:
                ins = supabase.table("salon_hours").insert(row).execute()
                if getattr(ins, "error", None):
                    return None, str(ins.error)

            return row, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

    @staticmethod
    def delete_salon_hour_day(salon_id: str, day_of_week: int):
        """
        Delete a single day's hours entry.
        """
        try:
            if day_of_week is None or not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return None, "day_of_week must be an integer between 0 (Sunday) and 6 (Saturday)"

            supabase.table("salon_hours").delete().eq("salon_id", salon_id).eq("day_of_week", day_of_week).execute()
            return True, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)

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
        
        # Allow all fields that can be set during registration
        allowed_fields = ["name", "description", "address", "city", "state", "zip_code", "phone", "email", "license_url", "logo_url", "timezone"]
        valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields}

        # Handle file uploads (same as register_salon)
        if license_file:
            valid_updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        if logo_file:
            valid_updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")
        
        # Clean timezone if provided
        if "timezone" in valid_updates:
            valid_updates["timezone"] = SalonService._clean_tz(valid_updates["timezone"])
        
        # Validate that at least one contact method is provided
        phone = valid_updates.get("phone") or salon.get("phone")
        email = valid_updates.get("email") or salon.get("email")
        if not (phone or email):
            return {"error": "At least one contact method (phone or email) is required."}, 400

        # Get old values for audit log
        old_salon = supabase.table("salons").select("*").eq("id", salon_id).maybe_single().execute()
        old_values = {}
        if old_salon.data:
            for key in valid_updates.keys():
                if key in old_salon.data:
                    old_values[key] = old_salon.data[key]
            old_values['status'] = old_salon.data.get('status')
        
        if valid_updates:
            valid_updates["status"] = "pending"
            valid_updates["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("salons").update(valid_updates).eq("id", salon_id).execute()
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='salons',
                record_id=salon_id,
                action='UPDATE',
                old_values=old_values,
                new_values={**valid_updates, 'status': 'pending'},
                changed_by=user_id
            )
        return {"message": "Appeal submitted successfully", "new_status": "pending"}

    @staticmethod
    def update_pending_salon(salon_id, owner_id, updates=None, logo_file=None, license_file=None, hours=None):
        """
        Allow an owner to update a pending salon application.
        """
        salon_response = (
            supabase.table("salons")
            .select("status, owner_id")
            .eq("id", salon_id)
            .single()
            .execute()
        )

        if not salon_response.data:
            return {"error": "Salon not found"}, 404

        salon = salon_response.data

        if salon["status"] != "pending":
            return {"error": "Only pending applications can be updated."}, 400

        if str(salon["owner_id"]) != str(owner_id):
            return {"error": "You are not authorized to update this salon."}, 403

        allowed_fields = ["name", "description", "address", "city", "state", "zip_code", "phone", "email", "license_url", "logo_url", "timezone"]
        valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields and v is not None}

        if "timezone" in valid_updates:
            valid_updates["timezone"] = SalonService._clean_tz(valid_updates["timezone"])

        if license_file:
            valid_updates["license_url"] = StorageService.upload_file(license_file, salon_id, "license")
        if logo_file:
            valid_updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")

        if valid_updates:
            valid_updates["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("salons").update(valid_updates).eq("id", salon_id).execute()

        return {"message": "Application updated successfully", "status": "pending"}, 200




    #--------------------------------------2. ADMINS

    """appeal and rejection done by a user with role of admin, the salon being review must have a current status of pending before review is submitted. Salon owners are notified of decision"""



    @staticmethod
    def approve_salon(salon_id, approver_id):
        # Get old values before update
        old_salon = supabase.table("salons").select("status").eq("id", salon_id).maybe_single().execute()
        old_status = old_salon.data.get("status") if old_salon.data else None
        
        supabase.table("salons").update({
            "status": "verified",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        salon = supabase.table("salons").select("name, owner_id").eq("id", salon_id).single().execute()
        owner_id = salon.data["owner_id"]
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='salons',
            record_id=salon_id,
            action='UPDATE',
            old_values={'status': old_status},
            new_values={'status': 'verified'},
            changed_by=approver_id
        )
        
        return {"message": "Salon approved successfully"}


    @staticmethod
    def reject_salon(salon_id, approver_id, reason):
        # Get old values before update
        old_salon = supabase.table("salons").select("status").eq("id", salon_id).maybe_single().execute()
        old_status = old_salon.data.get("status") if old_salon.data else None
        
        supabase.table("salons").update({
            "status": "rejected",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", salon_id).execute()

        salon = supabase.table("salons").select("name, owner_id").eq("id", salon_id).single().execute()
        owner_id = salon.data["owner_id"]
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='salons',
            record_id=salon_id,
            action='UPDATE',
            old_values={'status': old_status},
            new_values={'status': 'rejected', 'rejection_reason': reason},
            changed_by=approver_id
        )

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

    #------------------------------------BARBER SERVICES MANAGEMENT
    @staticmethod
    def add_service_to_barber(salon_id: str, barber_id: str, service_id: str, owner_id: str):
        """
        Add a service to a barber. Validates:
        - Salon ownership
        - Barber belongs to salon
        - Service belongs to salon
        
        Args:
            salon_id: Salon UUID
            barber_id: Barber UUID
            service_id: Service UUID
            owner_id: Owner user ID for validation
        
        Returns:
            Tuple of (result_dict, error_message)
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "Barber not found"
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return None, "Barber does not belong to this salon"
            
            # Verify service belongs to salon
            service_resp = supabase.table("services").select("id,salon_id").eq("id", service_id).single().execute()
            if getattr(service_resp, "error", None) or not service_resp.data:
                return None, "Service not found"
            
            if str(service_resp.data.get("salon_id")) != str(salon_id):
                return None, "Service does not belong to this salon"
            
            # Check if relationship already exists
            existing = supabase.table("barber_services").select("barber_id,service_id").eq("barber_id", barber_id).eq("service_id", service_id).execute()
            if existing.data:
                return None, "Service is already assigned to this barber"
            
            # Insert the relationship
            relationship_data = {
                "barber_id": barber_id,
                "service_id": service_id
            }
            response = supabase.table("barber_services").insert(relationship_data).execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            created_id = response.data[0]["id"] if response.data else None
            
            # Log audit
            if created_id:
                AuditLoggingService.log_audit(
                    table_name='barber_services',
                    record_id=created_id,
                    action='INSERT',
                    new_values=relationship_data,
                    changed_by=owner_id
                )
            
            return {"message": "Service added to barber successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def remove_service_from_barber(salon_id: str, barber_id: str, service_id: str, owner_id: str):
        """
        Remove a service from a barber. Validates:
        - Salon ownership
        - Barber belongs to salon
        - Service belongs to salon
        
        Args:
            salon_id: Salon UUID
            barber_id: Barber UUID
            service_id: Service UUID
            owner_id: Owner user ID for validation
        
        Returns:
            Tuple of (result_dict, error_message)
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "Barber not found"
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return None, "Barber does not belong to this salon"
            
            # Verify service belongs to salon
            service_resp = supabase.table("services").select("id,salon_id").eq("id", service_id).single().execute()
            if getattr(service_resp, "error", None) or not service_resp.data:
                return None, "Service not found"
            
            if str(service_resp.data.get("salon_id")) != str(salon_id):
                return None, "Service does not belong to this salon"
            
            # Get old relationship for audit log
            old_rel = supabase.table("barber_services").select("*").eq("barber_id", barber_id).eq("service_id", service_id).maybe_single().execute()
            old_values = old_rel.data if old_rel.data else {}
            
            # Delete the relationship
            response = supabase.table("barber_services").delete().eq("barber_id", barber_id).eq("service_id", service_id).execute()
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            if not response.data:
                return None, "Service is not assigned to this barber"
            
            # Log audit
            if old_values:
                AuditLoggingService.log_audit(
                    table_name='barber_services',
                    record_id=old_values.get('id'),
                    action='DELETE',
                    old_values=old_values,
                    changed_by=owner_id
                )
            
            return {"message": "Service removed from barber successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def get_barber_services(salon_id: str, barber_id: str, owner_id: str = None):
        """
        Get all services assigned to a barber. Validates:
        - Salon exists
        - Barber belongs to salon
        - If owner_id provided, validates salon ownership
        
        Args:
            salon_id: Salon UUID
            barber_id: Barber UUID
            owner_id: Owner user ID for validation (optional, for salon_owner role)
        
        Returns:
            Tuple of (services_list, error_message)
        """
        try:
            # Verify salon exists
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            # If owner_id provided, verify salon ownership
            if owner_id:
                if str(salon_resp.data.get("owner_id")) != str(owner_id):
                    return None, "Forbidden: You don't own this salon"
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "Barber not found"
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return None, "Barber does not belong to this salon"
            
            # Get services for this barber
            response = (
                supabase.table("barber_services")
                .select("service_id, services(id, name, description, duration_minutes, price, is_active)")
                .eq("barber_id", barber_id)
                .execute()
            )
            
            if getattr(response, "error", None):
                return None, response.error.message
            
            services = []
            for row in (response.data or []):
                service_data = row.get("services")
                if service_data:
                    services.append(service_data)
            
            return services, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def update_verified_salon(salon_id: str, owner_id: str, updates=None, logo_file=None):
        """
        Update a verified salon's details. Allows updating name, description, address, phone, email, logo.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id,status").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            salon = salon_resp.data
            if str(salon.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            if salon.get("status") != "verified":
                return None, "Only verified salons can be updated through this endpoint"
            
            allowed_fields = ["name", "description", "address", "city", "state", "zip_code", "phone", "email"]
            valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields and v is not None}
            
            if logo_file:
                from services.storage_service import StorageService
                valid_updates["logo_url"] = StorageService.upload_file(logo_file, salon_id, "logo")
            
            if valid_updates:
                valid_updates["updated_at"] = datetime.utcnow().isoformat()
                supabase.table("salons").update(valid_updates).eq("id", salon_id).execute()
            
            return {"message": "Salon updated successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def update_service(service_id: str, salon_id: str, owner_id: str, updates=None):
        """
        Update a service. Validates salon ownership and service belongs to salon.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify service belongs to salon
            service_resp = supabase.table("services").select("id,salon_id").eq("id", service_id).single().execute()
            if getattr(service_resp, "error", None) or not service_resp.data:
                return None, "Service not found"
            
            if str(service_resp.data.get("salon_id")) != str(salon_id):
                return None, "Service does not belong to this salon"
            
            # Get old values for audit log
            old_service = supabase.table("services").select("*").eq("id", service_id).maybe_single().execute()
            old_values = {}
            if old_service.data:
                for key in (updates or {}).keys():
                    if key in old_service.data:
                        old_values[key] = old_service.data[key]
            
            allowed_fields = ["name", "description", "duration_minutes", "price", "is_active"]
            valid_updates = {k: v for k, v in (updates or {}).items() if k in allowed_fields and v is not None}
            
            if valid_updates:
                supabase.table("services").update(valid_updates).eq("id", service_id).execute()
                
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='services',
                    record_id=service_id,
                    action='UPDATE',
                    old_values=old_values,
                    new_values=valid_updates,
                    changed_by=owner_id
                )
            
            return {"message": "Service updated successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def delete_service(service_id: str, salon_id: str, owner_id: str):
        """
        Delete a service. Validates salon ownership and service belongs to salon.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify service belongs to salon
            service_resp = supabase.table("services").select("id,salon_id").eq("id", service_id).single().execute()
            if getattr(service_resp, "error", None) or not service_resp.data:
                return None, "Service not found"
            
            if str(service_resp.data.get("salon_id")) != str(salon_id):
                return None, "Service does not belong to this salon"
            
            # Get old values for audit log before deletion
            old_values = {
                'salon_id': service_resp.data.get('salon_id'),
                'name': service_resp.data.get('name'),
                'description': service_resp.data.get('description'),
                'duration_minutes': service_resp.data.get('duration_minutes'),
                'price': service_resp.data.get('price'),
                'is_active': service_resp.data.get('is_active')
            }
            
            # Delete service
            supabase.table("services").delete().eq("id", service_id).execute()
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='services',
                record_id=service_id,
                action='DELETE',
                old_values=old_values,
                changed_by=owner_id
            )
            
            return {"message": "Service deleted successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def remove_employee(salon_id: str, barber_id: str, owner_id: str):
        """
        Remove an employee (barber) from a salon. Validates salon ownership and barber belongs to salon.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "Barber not found"
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return None, "Barber does not belong to this salon"
            
            # Get old values for audit log before deletion
            old_values = {
                'salon_id': barber_resp.data.get('salon_id'),
                'user_id': barber_resp.data.get('user_id'),
                'bio': barber_resp.data.get('bio'),
                'years_experience': barber_resp.data.get('years_experience'),
                'is_active': barber_resp.data.get('is_active')
            }
            
            # Delete barber (this will cascade delete barber_services)
            supabase.table("barbers").delete().eq("id", barber_id).execute()
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='barbers',
                record_id=barber_id,
                action='DELETE',
                old_values=old_values,
                changed_by=owner_id
            )
            
            return {"message": "Employee removed successfully"}, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def update_employee(salon_id: str, barber_id: str, owner_id: str, updates: dict):
        """
        Update an employee's (barber's) information. Validates salon ownership and barber belongs to salon.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Verify barber belongs to salon
            barber_resp = supabase.table("barbers").select("id,salon_id").eq("id", barber_id).single().execute()
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return None, "Barber not found"
            
            if str(barber_resp.data.get("salon_id")) != str(salon_id):
                return None, "Barber does not belong to this salon"
            
            # Get old values for audit log
            old_values = {}
            for key in ["bio", "years_experience", "is_active"]:
                if key in barber_resp.data:
                    old_values[key] = barber_resp.data[key]
            
            # Build update dict (only include provided fields)
            update_data = {}
            if "bio" in updates:
                update_data["bio"] = updates["bio"]
            if "years_experience" in updates:
                update_data["years_experience"] = updates["years_experience"]
            if "is_active" in updates:
                update_data["is_active"] = updates["is_active"]
            
            if not update_data:
                return None, "No valid fields to update"
            
            # Update barber
            updated = supabase.table("barbers").update(update_data).eq("id", barber_id).execute()
            
            if getattr(updated, "error", None) or not updated.data:
                return None, "Failed to update barber"
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='barbers',
                record_id=barber_id,
                action='UPDATE',
                old_values=old_values,
                new_values=update_data,
                changed_by=owner_id
            )
            
            return updated.data[0], None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def get_salon_customers(salon_id: str, owner_id: str):
        """
        Get all customers who have appointments at a salon, sorted by visit count (completed appointments).
        Returns customer info with visit count.
        """
        try:
            # Verify salon ownership
            salon_resp = supabase.table("salons").select("owner_id").eq("id", salon_id).single().execute()
            if getattr(salon_resp, "error", None) or not salon_resp.data:
                return None, "Salon not found"
            
            if str(salon_resp.data.get("owner_id")) != str(owner_id):
                return None, "Forbidden: You don't own this salon"
            
            # Get all appointments for this salon (all statuses to get all customers)
            appointments_resp = (
                supabase.table("appointments")
                .select("customer_id,id,start_at,status")
                .eq("salon_id", salon_id)
                .execute()
            )
            appointments = appointments_resp.data or []
            
            # Count completed visits per customer (for sorting)
            customer_visit_counts = {}
            customer_ids_set = set()
            for apt in appointments:
                customer_id = apt.get("customer_id")
                if customer_id:
                    customer_ids_set.add(customer_id)
                    # Only count completed appointments as visits
                    if apt.get("status") == "completed":
                        customer_visit_counts[customer_id] = customer_visit_counts.get(customer_id, 0) + 1
            
            # Get unique customer IDs (all customers, not just those with completed appointments)
            customer_ids = list(customer_ids_set)
            
            if not customer_ids:
                return [], None
            
            # Get customer profiles - try user_details first (has email), fallback to user_profiles
            profiles = {}
            try:
                profiles_resp = (
                    supabase.table("user_details")
                    .select("id,first_name,last_name,email,profile_image_url")
                    .in_("id", customer_ids)
                    .execute()
                )
                for row in profiles_resp.data or []:
                    profiles[row["id"]] = {
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "email": row.get("email"),
                        "profile_image_url": row.get("profile_image_url"),
                    }
            except Exception:
                # Fallback to user_profiles if user_details doesn't work
                try:
                    profiles_resp = (
                        supabase.table("user_profiles")
                        .select("user_id,first_name,last_name,profile_image_url")
                        .in_("user_id", customer_ids)
                        .execute()
                    )
                    for row in profiles_resp.data or []:
                        profiles[row["user_id"]] = {
                            "first_name": row.get("first_name"),
                            "last_name": row.get("last_name"),
                            "email": None,  # user_profiles doesn't have email
                            "profile_image_url": row.get("profile_image_url"),
                        }
                except Exception:
                    pass
            
            # Build customer list with visit counts
            customers = []
            for user_id in customer_ids:
                profile = profiles.get(user_id, {})
                customers.append({
                    "user_id": user_id,
                    "first_name": profile.get("first_name"),
                    "last_name": profile.get("last_name"),
                    "email": profile.get("email"),
                    "profile_image_url": profile.get("profile_image_url"),
                    "visit_count": customer_visit_counts.get(user_id, 0)
                })
            
            # Sort by visit count (descending)
            customers.sort(key=lambda x: x["visit_count"], reverse=True)
            
            return customers, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
