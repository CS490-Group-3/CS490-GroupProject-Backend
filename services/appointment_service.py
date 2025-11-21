from config import supabase
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from services.auth_service import AuthService

class AppointmentService:
    # ------ helpers ------
    @staticmethod
    def _apply_filters(query, when: str = "all", status: Optional[List[str]] = None):
        """attach time and status filters to a query."""
        now_iso = datetime.now(timezone.utc).isoformat()

        if when == "upcoming":
            query = query.gte("start_at", now_iso)
        elif when == "past":
            query = query.lt("start_at", now_iso)

        if status:
            if isinstance(status, str):
                status = [status]
            query = query.in_("status", status)
        return query
    
    @staticmethod
    def _paginate(query, page: int, limit: int): 
        """apply limit/offset pagination."""
        offset = (page - 1) * limit
        return query.range(offset, offset + limit - 1)

    @staticmethod
    def _get_service(service_id: str):
        # helper method to get the specific service
        response = (
            supabase.table("services")
            .select("id,salon_id,duration_minutes")
            .eq("id", service_id).single().execute()
        )
        if getattr(response, "error", None) or not response.data:
            return None, "Service not found"
        return response.data, None

    @staticmethod
    def _get_barber(barber_id: str):
        # helper method to get specific barber
        response = (
            supabase.table("barbers")
            .select("id,salon_id")
            .eq("id", barber_id).single().execute()
        )
        if getattr(response, "error", None) or not response.data:
            return None, "Barber not found"
        return response.data, None
    
    @staticmethod
    def _get_salon_timezone(salon_id: str) -> str:
        response = (
            supabase.table("salons")
            .select("timezone")
            .eq("id", salon_id).single().execute()
        )
        if getattr(response, "error", None) or not response.data:
            # default if timezone not provided
            return "America/New_York"
        return response.data.get("timezone") or "America/New_York"

    @staticmethod
    def _to_local_components(utc_iso: str, tz_name: str):
        """
        convert UTC ISO string -> (day of week: int 0 (Sun) ... 6 (Sat), local time: str 'HH:MM:SS').
        """
        dt_utc = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        local = dt_utc.astimezone(ZoneInfo(tz_name))
        # Python: Sunday=0 ... Saturday=6. Our DB uses 0..6 too.
        return local.weekday(), local.strftime("%H:%M:%S")

    @staticmethod
    def has_overlap(salon_id: str, barber_id: str, start_at, end_at, exclude_id: Optional[str] = None) -> bool:
        # helper method to determine if appointments overlap; returns bool
        # HALF-OPEN overlap: existing.start < new_end AND existing.end > new_start
        # allows for the edge case where new appointment ends EXACTLY when another starts (or vice versa)
        query = (
            supabase.table("appointments")
            .select("id")
            .eq("salon_id", salon_id)
            .eq("barber_id", barber_id)
            .in_("status", ["scheduled", "confirmed"])
            .lt("start_at", end_at)
            .gt("end_at", start_at)
        )
        if exclude_id:
            query = query.neq("id", exclude_id)
        response = query.execute()
        return bool(response.data)
    
    @staticmethod
    def _to_utc_iso(dt_or_str):
        if isinstance(dt_or_str, str):
            dt = datetime.fromisoformat(dt_or_str.replace("Z","+00:00"))
        else:
            dt = dt_or_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _can_manage(user, appt) -> bool:
        role = user.get("role")
        uid  = user.get("sub")
        if role == "admin":
            return True
        if role == "customer":
            return appt["customer_id"] == uid
        if role == "barber":
            barber_id, _ = AuthService.get_barber_id(uid)
            return barber_id and appt["barber_id"] == barber_id
        if role == "salon_owner":
            salons = supabase.table("salons").select("id").eq("owner_id", uid).execute()
            owned = {s["id"] for s in (salons.data or [])}
            return appt["salon_id"] in owned
        return False

    @staticmethod
    def _hydrate_appointments(rows: List[dict]) -> List[dict]:
        if not rows:
            return []

        salon_ids = {row["salon_id"] for row in rows if row.get("salon_id")}
        service_ids = {row["service_id"] for row in rows if row.get("service_id")}
        barber_ids = {row["barber_id"] for row in rows if row.get("barber_id")}
        customer_ids = {row["customer_id"] for row in rows if row.get("customer_id")}
        appointment_ids = [row["id"] for row in rows if row.get("id")]

        salons = {}
        if salon_ids:
            resp = (
                supabase.table("salons")
                .select("id,name,address,city,state,zip_code,phone,logo_url")
                .in_("id", list(salon_ids))
                .execute()
            )
            for row in resp.data or []:
                salons[row["id"]] = {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "address": f"{row.get('address','')}, {row.get('city','')}, {row.get('state','')} {row.get('zip_code','')}".replace(" ,", ",").strip(" ,"),
                    "phone": row.get("phone"),
                    "logo_url": row.get("logo_url"),
                }

        services = {}
        if service_ids:
            resp = (
                supabase.table("services")
                .select("id,name,duration_minutes,price,description")
                .in_("id", list(service_ids))
                .execute()
            )
            for row in resp.data or []:
                price = row.get("price")
                try:
                    price = float(price) if price is not None else None
                except Exception:
                    price = None
                services[row["id"]] = {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "duration_minutes": row.get("duration_minutes"),
                    "price": price,
                    "description": row.get("description"),
                }

        barbers = {}
        if barber_ids:
            resp = (
                supabase.table("barbers")
                .select("id,user_id,bio,years_experience")
                .in_("id", list(barber_ids))
                .execute()
            )
            barbers_rows = resp.data or []
            user_ids = [row["user_id"] for row in barbers_rows if row.get("user_id")]
            profiles = {}
            if user_ids:
                try:
                    prof = (
                        supabase.table("user_profiles")
                        .select("user_id,first_name,last_name,profile_image_url")
                        .in_("user_id", user_ids)
                        .execute()
                    )
                    profiles = {row["user_id"]: row for row in (prof.data or [])}
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
            for row in barbers_rows:
                profile = profiles.get(row.get("user_id"), {})
                barbers[row["id"]] = {
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "name": f"{profile.get('first_name','')} {profile.get('last_name','')}".strip() or "Team member",
                    "avatar": profile.get("profile_image_url"),
                    "years_experience": row.get("years_experience"),
                    "bio": row.get("bio"),
                }

        reviews_map = {}
        if appointment_ids:
            rev_resp = (
                supabase.table("reviews")
                .select("appointment_id,rating,comment,id")
                .in_("appointment_id", appointment_ids)
                .execute()
            )
            for row in rev_resp.data or []:
                reviews_map[row["appointment_id"]] = {
                    "id": row.get("id"),
                    "stars": row.get("rating"),
                    "text": row.get("comment"),
                }

        customers = {}
        if customer_ids:
            try:
                cust_resp = (
                    supabase.table("user_profiles")
                    .select("user_id,first_name,last_name,profile_image_url")
                    .in_("user_id", list(customer_ids))
                    .execute()
                )
            except Exception:
                cust_resp = (
                    supabase.table("user_details")
                    .select("id,first_name,last_name,profile_image_url")
                    .in_("id", list(customer_ids))
                    .execute()
                )
            for row in cust_resp.data or []:
                uid = row.get("user_id") or row.get("id")
                customers[uid] = {
                    "id": uid,
                    "name": f"{row.get('first_name','')} {row.get('last_name','')}".strip() or "Customer",
                    "avatar": row.get("profile_image_url"),
                }

        hydrated = []
        for row in rows:
            enriched = dict(row)
            enriched["salon"] = salons.get(row.get("salon_id"))
            enriched["service"] = services.get(row.get("service_id"))
            enriched["barber"] = barbers.get(row.get("barber_id"))
            enriched["customer"] = customers.get(row.get("customer_id"))
            if row.get("id") in reviews_map:
                enriched["review"] = reviews_map[row["id"]]
            hydrated.append(enriched)
        return hydrated

    # ------ booking methods ------
    @staticmethod
    def create_appointment(appointment_data: Dict, *, user: dict):
        # creates an appointment. customer can only book for themselves.
        # other roles must provide customer_id.
        """
        Expects UTC datetimes:
          appointment_data = {
            'customer_id','barber_id','service_id','salon_id',
            'start_at' (ISO or datetime),  'end_at' (optional),
            'notes' (optional)
          }
        """
        try:
            role = user.get("role")
            uid = user.get("sub")

            if role == "customer":
                appointment_data["customer_id"] = uid
            else:
                if not appointment_data.get("customer_id"):
                    return None, "customer_id is required"

            service, err = AppointmentService._get_service(appointment_data["service_id"])
            if err: return None, err
            barber, err = AppointmentService._get_barber(appointment_data["barber_id"])
            if err: return None, err

            if str(service["salon_id"]) != str(appointment_data["salon_id"]) or str(barber["salon_id"]) != str(appointment_data["salon_id"]):
                return None, "Barber and service must belong to the specified salon"

            start_at = appointment_data["start_at"]

            # convert start time to datetime if provided as string
            if isinstance(start_at, str):
                start_at = datetime.fromisoformat(start_at.replace("Z","+00:00"))

            # what to do if end time is not provided (start time + service duration)
            if not appointment_data.get("end_at"):
                service_duration = int(service["duration_minutes"])
                end_at = start_at + timedelta(minutes=service_duration)
            else:
                end_at = appointment_data["end_at"]
                if isinstance(end_at, str):
                    # convert end time to datetime if provided as string
                    end_at = datetime.fromisoformat(end_at.replace("Z", "+00:00"))

            # convert both start and end times back to ISO strings (UTC)
            appointment_data["start_at"] = start_at.astimezone(ZoneInfo("UTC")).isoformat()
            appointment_data["end_at"] = end_at.astimezone(ZoneInfo("UTC")).isoformat()

            # Overlap check
            if AppointmentService.has_overlap(
                appointment_data["salon_id"],
                appointment_data["barber_id"],
                appointment_data["start_at"],
                appointment_data["end_at"]
            ):
                return None, "Appointment time overlaps with an existing appointment."

            ok, message = AppointmentService.is_barber_available(
                appointment_data["salon_id"],
                appointment_data["barber_id"],
                appointment_data["start_at"],
                appointment_data["end_at"]
            )
            if not ok:
                return None, message

            appointment_data.setdefault("status", "scheduled")

            payload = {
                "customer_id": appointment_data["customer_id"],
                "barber_id":   appointment_data["barber_id"],
                "service_id":  appointment_data["service_id"],
                "salon_id":    appointment_data["salon_id"],
                "start_at":    appointment_data["start_at"],
                "end_at":      appointment_data["end_at"],
                "notes":       appointment_data.get("notes"),
            }

            response = supabase.table("appointments").insert(payload).execute()
            if getattr(response, "error", None):
                return None, response.error.message
            created_id = response.data[0]["id"]
            return AppointmentService.get_by_id(created_id, user=user)

        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_appointment(appointment_id, update_data, *, user: dict):
        """
        updates appointment (supports reschedule status)
        \nNOTE: If any of start_at/end_at/barber_id/salon_id change, re-check overlap.
        """
        try:
            current, error = AppointmentService.get_by_id(appointment_id, user=user)
            if error:
                return None, error
            if not AppointmentService._can_manage(user, current):
                return None, "Forbidden"

            new_salon  = update_data.get("salon_id",  current["salon_id"])
            new_barber = update_data.get("barber_id", current["barber_id"])
            new_start  = update_data.get("start_at",  current["start_at"])
            new_end    = update_data.get("end_at",    current["end_at"])

            if "start_at" in update_data:
                update_data["start_at"] = AppointmentService._to_utc_iso(update_data["start_at"])
                new_start = update_data["start_at"]
            else:
                new_start = AppointmentService._to_utc_iso(new_start)

            if "end_at" in update_data:
                update_data["end_at"] = AppointmentService._to_utc_iso(update_data["end_at"])
                new_end = update_data["end_at"]
            else:
                new_end = AppointmentService._to_utc_iso(new_end)

            if ("barber_id" in update_data) or ("salon_id" in update_data):
                b = (
                    supabase.table("barbers")
                    .select("salon_id")
                    .eq("id", new_barber)
                    .single()
                    .execute()
                )
                if getattr(b, "error", None) or not b.data or str(b.data["salon_id"]) != str(new_salon):
                    return None, "Barber must belong to the specified salon"

            # check overlap if any time/barber/salon changed
            if any(k in update_data for k in ("start_at","end_at","barber_id","salon_id")):
                if AppointmentService.has_overlap(new_salon, new_barber, new_start, new_end, exclude_id=appointment_id):
                    return None, "Rescheduled time overlaps with another appointment."

            response = supabase.table("appointments").update(update_data).eq("id", appointment_id).execute()
            if getattr(response, "error", None):
                return None, response.error.message
            if not response.data:
                return None, "Nothing updated"
            return AppointmentService.get_by_id(appointment_id, user=user)
        
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def cancel_appointment(appointment_id: str, *, user: dict, reason: Optional[str] = None):
        # can add cancelled_by parameter in future for auditing purposes
        """
        set status=cancelled, capture optional reason.
        \nsecure, respects ownership.
        """
        try:
            current, error = AppointmentService.get_by_id(appointment_id, user=user)
            if error:
                return None, error
            if not AppointmentService._can_manage(user, current):
                return None, "Forbidden"
            
            update = {
                "status": "cancelled",
                "cancellation_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Update failed"
            return AppointmentService.get_by_id(appointment_id, user=user)
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def reschedule_appointment(appointment_id: str, 
                               salon_id: str, 
                               barber_id: str, 
                               new_start_at, 
                               new_end_at=None,
                               *,
                               user: dict):
        """
        reschedule with proper validation:
          - parse ISO -> datetime if needed
          - compute end from service duration if not provided (we need service_id from row)
          - availability + overlap checks
          - set status=scheduled
        """
        try:
            # fetch current row (need service_id + duration)
            current, error = AppointmentService.get_by_id(appointment_id, user=user)
            if error:
                return None, error
            if not AppointmentService._can_manage(user, current):
                return None, "Forbidden"

            s_iso = AppointmentService._to_utc_iso(new_start_at)
            if new_end_at is None:
                # compute end time from service duration if not provided
                service = supabase.table("services").select("duration_minutes").eq("id", current["service_id"]).single().execute()
                if getattr(service, "error", None) or not service.data:
                    return None, "Service not found to compute duration"
                dur = int(service.data.get("duration_minutes"))
                e_iso = (datetime.fromisoformat(s_iso) + timedelta(minutes=dur)).isoformat()
            else:
                e_iso = AppointmentService._to_utc_iso(new_end_at)
            
            new_start_at, new_end_at = s_iso, e_iso

            barber = supabase.table("barbers").select("salon_id").eq("id", barber_id).single().execute()
            if getattr(barber,"error",None) or not barber.data or str(barber.data["salon_id"]) != str(salon_id):
                return None, "Barber must belong to the specified salon"

            # validate availability
            ok, msg = AppointmentService.is_barber_available(salon_id, barber_id, new_start_at, new_end_at)
            if not ok:
                return None, msg

            # apply update
            update = {
                "salon_id": salon_id,
                "barber_id": barber_id,
                "start_at": new_start_at,
                "end_at": new_end_at,
                "status": "scheduled",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Nothing updated"
            return AppointmentService.get_by_id(appointment_id, user=user)
        except Exception as e:
            return None, str(e)
    
    # ------ workflow ------
    @staticmethod
    def confirm_or_deny(appointment_id: str, action: str, *, user: dict, reason: Optional[str] = None):
        """
        action: 'confirm' or 'deny'
        \nonly admins, owners (of that salon), or the assigned barber may do this.
        """
        try:
            if action not in ("confirm", "deny"):
                return None, "Invalid action"
            
            current, error = AppointmentService.get_by_id(appointment_id, user=user)
            if error:
                return None, error
            
            role = user.get("role")
            uid = user.get("sub")
            
            if role == "admin":
                pass
            elif role == "salon_owner":
                salons = supabase.table("salons").select("id").eq("owner_id", uid).execute()
                owned = {s["id"] for s in (salons.data or [])}
                if current["salon_id"] not in owned:
                    return None, "Forbidden"
            elif role == "barber":
                barber_id, _ = AuthService.get_barber_id(uid)
                if not barber_id or current["barber_id"] != barber_id:
                    return None, "Forbidden"
            else:
                return None, "Forbidden"
            
            if action == "confirm":
                update_payload = {
                    "status": "confirmed",
                    "cancellation_reason": None,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                update_payload = {
                    "status": "cancelled",
                    "cancellation_reason": reason,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }

            response = (
                supabase.table("appointments")
                .update(update_payload)
                .eq("id", appointment_id)
                .execute()
            )
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Appointment not found"
            return AppointmentService.get_by_id(appointment_id, user=user)
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def mark_completed_or_no_show(appointment_id: str, status: str, *, user: dict):
        if status not in ("completed", "no_show"):
            return None, "Invalid status"

        current, error = AppointmentService.get_by_id(appointment_id, user=user)
        if error:
            return None, error

        role = user.get("role")
        uid = user.get("sub")
        if role == "admin":
            pass
        elif role == "salon_owner":
            salons = supabase.table("salons").select("id").eq("owner_id", uid).execute()
            owned = {s["id"] for s in (salons.data or [])}
            if current["salon_id"] not in owned:
                return None, "Forbidden"
        elif role == "barber":
            barber_id, _ = AuthService.get_barber_id(uid)
            if not barber_id or current["barber_id"] != barber_id:
                return None, "Forbidden"
        else:
            return None, "Forbidden"

        update = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
        if getattr(response, "error", None) or not response.data:
            return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Update failed"
        return AppointmentService.get_by_id(appointment_id, user=user)


    # ------ availability ------
    @staticmethod
    def is_barber_available(salon_id: str, barber_id: str, start_at_iso: str, end_at_iso: str) -> Tuple[bool, Optional[str]]:
        """
        checks weekly availability (local wall-clock) + explicit unavailability (UTC) + existing overlaps
        \nreturns (True, None) if available; otherwise (False, reason)
        """
        tz = AppointmentService._get_salon_timezone(salon_id)

        # find weekly availability; convert iso times to local day and time
        dow_start, local_start = AppointmentService._to_local_components(start_at_iso, tz)
        dow_end,   local_end   = AppointmentService._to_local_components(end_at_iso, tz)

        # appointment must START and END on the same day
        if dow_start != dow_end:
            return False, "Requested slot crosses business day boundary"

        # check that at least one active availability window fully covers the interval
        avail = (
            supabase.table("barber_availability")
            .select("id")
            .eq("barber_id", barber_id)
            .eq("is_active", True)
            .eq("day_of_week", dow_start)
            .lte("start_time", local_start)   # window starts at/before requested start
            .gte("end_time", local_end)       # window ends at/after requested end
            .execute()
        )
        if not avail.data:
            return False, "Barber not available during requested hours"

        # check explicit unavailability — check UTC overlap
        unavail = (
            supabase.table("barber_unavailability")
            .select("id")
            .eq("barber_id", barber_id)
            .lt("start_datetime", end_at_iso)
            .gt("end_datetime", start_at_iso)
            .execute()
        )
        if unavail.data:
            return False, "Barber is marked unavailable at that time"

        # existing appointment overlap (UTC) — reuse has_overlap
        if AppointmentService.has_overlap(salon_id, barber_id, start_at_iso, end_at_iso):
            return False, "Appointment time overlaps with another booking"

        return True, None

    @staticmethod
    def get_available_slots(salon_id: str, barber_id: str, service_id: str, date_str: str):
        try:
            service, error = AppointmentService._get_service(service_id)
            if error:
                return None, error
            duration_minutes = int(service.get("duration_minutes") or 30)
            slot_length = timedelta(minutes=duration_minutes)

            tz_name = AppointmentService._get_salon_timezone(salon_id)
            tz = ZoneInfo(tz_name)
            try:
                base_date = datetime.fromisoformat(f"{date_str}T00:00:00")
            except ValueError:
                return None, "Invalid date format. Expected YYYY-MM-DD."
            day_local = base_date.replace(tzinfo=tz)
            day_start_local = datetime.combine(day_local.date(), time(0, 0), tz)
            day_end_local = day_start_local + timedelta(days=1)

            dow = day_local.weekday()
            availability = (
                supabase.table("barber_availability")
                .select("start_time,end_time,is_active")
                .eq("barber_id", barber_id)
                .eq("day_of_week", dow)
                .eq("is_active", True)
                .order("start_time", desc=False)
                .execute()
            )
            windows = availability.data or []
            if not windows:
                return [], None

            start_utc = day_start_local.astimezone(timezone.utc).isoformat()
            end_utc = day_end_local.astimezone(timezone.utc).isoformat()

            unavail_resp = (
                supabase.table("barber_unavailability")
                .select("start_datetime,end_datetime")
                .eq("barber_id", barber_id)
                .lt("start_datetime", end_utc)
                .gt("end_datetime", start_utc)
                .execute()
            )
            unavail = [
                (
                    datetime.fromisoformat(row["start_datetime"]),
                    datetime.fromisoformat(row["end_datetime"])
                )
                for row in (unavail_resp.data or [])
            ]

            appt_resp = (
                supabase.table("appointments")
                .select("start_at,end_at,status")
                .eq("barber_id", barber_id)
                .eq("salon_id", salon_id)
                .lt("start_at", end_utc)
                .gt("end_at", start_utc)
                .execute()
            )
            blocking_status = {"scheduled", "confirmed"}
            booked = [
                (
                    datetime.fromisoformat(row["start_at"]),
                    datetime.fromisoformat(row["end_at"])
                )
                for row in (appt_resp.data or [])
                if row.get("status") in blocking_status
            ]

            now_utc = datetime.now(timezone.utc)
            slots = []
            for window in windows:
                try:
                    start_time = time.fromisoformat(window["start_time"])
                    end_time = time.fromisoformat(window["end_time"])
                except Exception:
                    continue
                window_start = datetime.combine(day_local.date(), start_time, tz)
                window_end = datetime.combine(day_local.date(), end_time, tz)
                current = window_start
                while current + slot_length <= window_end:
                    slot_start_utc = current.astimezone(timezone.utc)
                    slot_end_utc = (current + slot_length).astimezone(timezone.utc)
                    if slot_start_utc < now_utc:
                        current += slot_length
                        continue
                    if any(u_start < slot_end_utc and u_end > slot_start_utc for u_start, u_end in unavail):
                        current += slot_length
                        continue
                    if any(b_start < slot_end_utc and b_end > slot_start_utc for b_start, b_end in booked):
                        current += slot_length
                        continue
                    slots.append({
                        "start_at": slot_start_utc.isoformat(),
                        "end_at": slot_end_utc.isoformat(),
                        "label": current.strftime("%I:%M %p").lstrip("0") or current.strftime("%H:%M"),
                    })
                    current += slot_length
            return slots, None
        except Exception as e:
            return None, str(e)
    
    # ------ reads ------
    @staticmethod
    def get_by_id(appointment_id: str, *, user: dict):
        # fetches a specific appointment by id
        try:
            response = (
                        supabase.table("appointments")
                        .select("*")
                        .eq("id", appointment_id)
                        .single()
                        .execute()
            )
            if getattr(response, "error", None) or not response.data:
                return None, "Appointment not found"
            if not AppointmentService._can_manage(user, response.data):
                return None, "Forbidden"
            enriched = AppointmentService._hydrate_appointments([response.data])
            return (enriched[0] if enriched else response.data), None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_customer(customer_id: str, 
                                     when: str = "all",
                                     status=None,
                                     page: int = 1,
                                     limit: int = 20):
        # fetches all appointments for a specific customer (supports upcoming/past/all)
        try:
            query = (
                        supabase.table("appointments")
                        .select("*")
                        .eq("customer_id", customer_id)
                        .order("start_at", desc=False)
            )
            query = AppointmentService._apply_filters(query, when, status)
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_barber(barber_id: str, 
                                   when: str = "all",
                                   status=None,
                                   page: int = 1,
                                   limit: int = 20):
        # fetches all appointments for a specific barber (supports upcoming/past/all)
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            query = (
                supabase.table("appointments")
                .select("*")
                .eq("barber_id", barber_id)
                .order("start_at", desc=False)
            )
            query = AppointmentService._apply_filters(query, when, status)
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_all_salon_appointments(salon_ids: List[str], 
                                   when: str = "all",
                                   status=None,
                                   page: int = 1,
                                   limit: int = 20):
        # fetches all appointments for a salon (supports upcoming/past/all)
        try:
            query = (
                supabase.table("appointments")
                .select("*")
                .in_("salon_id", salon_ids)
                .order("start_at", desc=False)
            )
            query = AppointmentService._apply_filters(query, when, status)
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None
        except Exception as e:
            return None, str(e)

    
    @staticmethod
    def get_admin_filtered(salon_id=None, 
                           barber_id=None, 
                           customer_id=None,
                           when="all", 
                           status=None, 
                           page=1, 
                           limit=20):
        """Admin-level query with optional filters."""
        query = supabase.table("appointments").select("*").order("start_at", desc=False)
        if salon_id:
            query = query.eq("salon_id", salon_id)
        if barber_id:
            query = query.eq("barber_id", barber_id)
        if customer_id:
            query = query.eq("customer_id", customer_id)
        query = AppointmentService._apply_filters(query, when, status)
        query = AppointmentService._paginate(query, page, limit)
        response = query.execute()
        if getattr(response,"error",None):
            return None, response.error.message
        data = AppointmentService._hydrate_appointments(response.data or [])
        return data, None

    @staticmethod
    def create_review(appointment_id: str, rating: int, comment: str, *, user: dict):
        if rating < 1 or rating > 5:
            return None, "Rating must be between 1 and 5"

        current, error = AppointmentService.get_by_id(appointment_id, user=user)
        if error:
            return None, error
        if current.get("customer_id") != user.get("sub"):
            return None, "Forbidden"
        if current.get("status") not in ("completed",):
            return None, "Only completed appointments can be reviewed"

        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "rating": rating,
            "comment": comment,
            "updated_at": timestamp,
        }
        existing = (
            supabase.table("reviews")
            .select("id")
            .eq("appointment_id", appointment_id)
            .single()
            .execute()
        )
        if existing.data:
            response = (
                supabase.table("reviews")
                .update(payload)
                .eq("appointment_id", appointment_id)
                .execute()
            )
        else:
            payload.update({
                "appointment_id": appointment_id,
                "salon_id": current.get("salon_id"),
                "user_id": user.get("sub"),
                "created_at": timestamp,
            })
            response = supabase.table("reviews").insert(payload).execute()

        if getattr(response, "error", None):
            return None, response.error.message

        review_row = (
            supabase.table("reviews")
            .select("id,rating,comment,created_at")
            .eq("appointment_id", appointment_id)
            .single()
            .execute()
        )
        return review_row.data, None
