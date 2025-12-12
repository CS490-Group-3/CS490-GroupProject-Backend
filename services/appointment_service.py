from config import supabase
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from services.auth_service import AuthService
from services.error_logging_service import ErrorLoggingService
from services.audit_logging_service import AuditLoggingService
from services.loyalty_service import LoyaltyService
import uuid

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
            .select("id,salon_id,is_active")
            .eq("id", barber_id).single().execute()
        )
        if getattr(response, "error", None) or not response.data:
            return None, "Barber not found"
        # Check if barber is active
        if not response.data.get("is_active", True):
            return None, "Barber is not active"
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
        # Python weekday(): Monday=0 .. Sunday=6. DB uses Sunday=0 .. Saturday=6.
        dow = (local.weekday() + 1) % 7  # shift so Sunday=0
        return dow, local.strftime("%H:%M:%S")

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
    def _auto_complete_past_appointments(rows: List[dict]) -> List[dict]:
        """
        Automatically mark appointments as completed if they're past their end time.
        This runs on-demand when appointments are fetched (no cron jobs needed).
        Updates the rows in place and returns them.
        """
        if not rows:
            return rows
        
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            from services.loyalty_service import LoyaltyService
            
            appointments_to_complete = []
            
            # Check each appointment row
            for row in rows:
                status = row.get("status", "").lower()
                end_at = row.get("end_at")
                apt_id = row.get("id")
                
                # Only auto-complete if:
                # - Status is "scheduled" or "confirmed" (NOT cancelled, no_show, denied, or already completed)
                # - Has an end_at time
                # - End time has passed
                # 
                # IMPORTANT: We do NOT touch appointments that are:
                # - "cancelled" - already cancelled, leave it alone
                # - "no_show" - barber already marked as no-show, leave it alone
                # - "denied" - appointment was denied, leave it alone
                # - "completed" - already completed, leave it alone
                if (status in ["scheduled", "confirmed"] and 
                    end_at and 
                    apt_id):
                    
                    try:
                        # Parse end_at to datetime
                        if isinstance(end_at, str):
                            end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
                        else:
                            end_dt = end_at
                        
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=timezone.utc)
                        else:
                            end_dt = end_dt.astimezone(timezone.utc)
                        
                        # Check if end time has passed
                        if end_dt < now:
                            appointments_to_complete.append(apt_id)
                    except Exception:
                        # If we can't parse the date, skip this appointment
                        continue
            
            # Batch update all appointments that need to be completed
            if appointments_to_complete:
                update_response = (
                    supabase.table("appointments")
                    .update({
                        "status": "completed",
                        "updated_at": now_iso
                    })
                    .in_("id", appointments_to_complete)
                    .execute()
                )
                
                if not getattr(update_response, "error", None) and update_response.data:
                    # Update the rows in place
                    for row in rows:
                        if row.get("id") in appointments_to_complete:
                            row["status"] = "completed"
                            row["updated_at"] = now_iso
                    
                    # Award loyalty points for each completed appointment
                    for apt_id in appointments_to_complete:
                        try:
                            LoyaltyService.award_points_for_completed_appointment(apt_id)
                        except Exception as e:
                            # Log but don't fail - points can be awarded later if needed
                            ErrorLoggingService.log_exception(e, severity='medium')
        except Exception as e:
            # Don't fail the whole request if auto-completion fails
            ErrorLoggingService.log_exception(e, severity='medium')
        
        return rows
    
    @staticmethod
    def _hydrate_appointments(rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        
        # Auto-complete appointments that are past their end time
        rows = AppointmentService._auto_complete_past_appointments(rows)

        salon_ids = {row["salon_id"] for row in rows if row.get("salon_id")}
        service_ids = {row["service_id"] for row in rows if row.get("service_id")}
        barber_ids = {row["barber_id"] for row in rows if row.get("barber_id")}
        customer_ids = {row["customer_id"] for row in rows if row.get("customer_id")}
        appointment_ids = [row["id"] for row in rows if row.get("id")]
        
        # Fetch payment information for appointments
        payments = {}
        if appointment_ids:
            payment_resp = (
                supabase.table("payments")
                .select("id, appointment_id, payment_status, amount, created_at")
                .in_("appointment_id", appointment_ids)
                .execute()
            )
            for payment in (payment_resp.data or []):
                apt_id = payment.get("appointment_id")
                if apt_id:
                    # Store the most recent payment for each appointment
                    if apt_id not in payments or payment.get("created_at", "") > payments[apt_id].get("created_at", ""):
                        payments[apt_id] = {
                            "id": payment.get("id"),
                            "payment_status": payment.get("payment_status"),
                            "amount": payment.get("amount"),
                            "created_at": payment.get("created_at")
                        }

        salons = {}
        if salon_ids:
            resp = (
                supabase.table("salons")
                .select("id,name,address,city,state,zip_code,phone,logo_url,timezone")
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
                    "timezone": row.get("timezone"),
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
                # First try user_profiles; if none found, fall back to user_details view
                try:
                    prof = (
                        supabase.table("user_profiles")
                        .select("user_id,first_name,last_name,profile_image_url")
                        .in_("user_id", user_ids)
                        .execute()
                    )
                    if prof.data:
                        profiles = {row["user_id"]: row for row in (prof.data or [])}
                    else:
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
                .select("appointment_id,rating,comment,id,user_id")
                .in_("appointment_id", appointment_ids)
                .execute()
            )
            review_ids = [row["id"] for row in (rev_resp.data or []) if row.get("id")]
            responses_map = {}
            if review_ids:
                responses_resp = (
                    supabase.table("review_responses")
                    .select("*")
                    .in_("review_id", review_ids)
                    .execute()
                )
                responses_map = {r["review_id"]: r for r in (responses_resp.data or [])}
            
            # Fetch review images and generate signed URLs
            images_map = {}
            if review_ids:
                try:
                    images_resp = (
                        supabase.table("review_images")
                        .select("*")
                        .in_("review_id", review_ids)
                        .execute()
                    )
                    if images_resp.data:
                        from datetime import timedelta
                        for img in images_resp.data:
                            review_id = img.get("review_id")
                            if review_id:
                                # Generate signed URL if file_url exists
                                file_url = img.get("file_url")
                                if file_url and not img.get("signed_url"):
                                    try:
                                        signed_resp = supabase.storage.from_("review-images").create_signed_url(
                                            file_url,
                                            int(timedelta(days=7).total_seconds())
                                        )
                                        if signed_resp and not (hasattr(signed_resp, 'error') and signed_resp.error):
                                            img["signed_url"] = signed_resp.get("signedURL") or signed_resp.get("signed_url")
                                    except Exception:
                                        # If signed URL generation fails, continue without it
                                        pass
                                
                                if review_id not in images_map:
                                    images_map[review_id] = []
                                images_map[review_id].append(img)
                except Exception:
                    # If review_images table doesn't exist or error, continue without images
                    pass
            
            # Fetch user profiles for reviews
            review_user_ids = [row.get("user_id") for row in (rev_resp.data or []) if row.get("user_id")]
            review_profiles = {}
            if review_user_ids:
                try:
                    prof_resp = (
                        supabase.table("user_details")
                        .select("id,first_name,last_name")
                        .in_("id", review_user_ids)
                        .execute()
                    )
                    if prof_resp.data:
                        review_profiles = {row["id"]: row for row in prof_resp.data}
                except Exception:
                    pass
            
            for row in rev_resp.data or []:
                review_id = row.get("id")
                user_id = row.get("user_id")
                
                # Get user name
                user_name = "Guest"
                if user_id and user_id in review_profiles:
                    profile = review_profiles[user_id]
                    first_name = profile.get("first_name", "").strip()
                    last_name = profile.get("last_name", "").strip()
                    full_name = f"{first_name} {last_name}".strip()
                    if full_name:
                        user_name = full_name
                
                review_data = {
                    "id": review_id,
                    "stars": row.get("rating"),
                    "text": row.get("comment"),
                    "rating": row.get("rating"),
                    "user": {
                        "name": user_name
                    }
                }
                # Attach response if it exists
                if review_id in responses_map:
                    review_data["response"] = responses_map[review_id]
                # Attach images if they exist
                if review_id in images_map:
                    review_data["images"] = images_map[review_id]
                reviews_map[row["appointment_id"]] = review_data

        customers = {}
        if customer_ids:
            try:
                # First try user_profiles; if no rows, fall back to user_details view
                cust_resp = (
                    supabase.table("user_profiles")
                    .select("user_id,first_name,last_name,profile_image_url")
                    .in_("user_id", list(customer_ids))
                    .execute()
                )
                if not cust_resp.data:
                    cust_resp = (
                        supabase.table("user_details")
                        .select("id,first_name,last_name,profile_image_url")
                        .in_("id", list(customer_ids))
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

        # Check for "barber_running_late" notifications for each appointment
        running_late_map = {}
        if appointment_ids:
            try:
                late_notifs = (
                    supabase.table("notifications")
                    .select("related_id")
                    .in_("related_id", appointment_ids)
                    .eq("notification_type", "barber_running_late")
                    .execute()
                )
                for notif in (late_notifs.data or []):
                    if notif.get("related_id"):
                        running_late_map[notif["related_id"]] = True
            except Exception:
                pass  # If notification check fails, just continue without it

        hydrated = []
        for row in rows:
            enriched = dict(row)
            enriched["salon"] = salons.get(row.get("salon_id"))
            enriched["service"] = services.get(row.get("service_id"))
            enriched["barber"] = barbers.get(row.get("barber_id"))
            enriched["customer"] = customers.get(row.get("customer_id"))
            if row.get("id") in reviews_map:
                enriched["review"] = reviews_map[row["id"]]
            # Add flag if barber is running late
            enriched["barber_running_late"] = running_late_map.get(row.get("id"), False)
            # Add payment information
            payment_info = payments.get(row.get("id"))
            enriched["loyalty_points_earned"] = 0
            enriched["loyalty_points_pending"] = 0
            
            if payment_info:
                enriched["payment"] = payment_info
                enriched["payment_status"] = payment_info.get("payment_status")
                
                # Get loyalty points earned for this appointment (if completed)
                payment_id = payment_info.get("id")
                if payment_id:
                    try:
                        from services.loyalty_service import LoyaltyService
                        loyalty_trans_response = supabase.table("loyalty_transactions")\
                            .select("id, points, transaction_type, description")\
                            .eq("payment_id", payment_id)\
                            .eq("transaction_type", "earned")\
                            .execute()
                        
                        if loyalty_trans_response and not getattr(loyalty_trans_response, "error", None):
                            transactions = loyalty_trans_response.data or []
                            points_earned = sum([t.get("points", 0) for t in transactions if t.get("points", 0) > 0])
                            enriched["loyalty_points_earned"] = points_earned
                    except Exception:
                        pass
                
                # Calculate pending points for scheduled appointments (not completed yet)
                if row.get("status") in ["scheduled", "confirmed"] and payment_info.get("payment_status") == "completed":
                    try:
                        salon_id = row.get("salon_id")
                        payment_amount = float(payment_info.get("amount", 0))
                        if salon_id and payment_amount > 0:
                            points_pending, _ = LoyaltyService.calculate_potential_points(payment_amount, salon_id)
                            enriched["loyalty_points_pending"] = points_pending
                    except Exception:
                        pass
            elif row.get("status") in ["scheduled", "confirmed"]:
                # Calculate pending points even if no payment info yet (for display purposes)
                try:
                    from services.loyalty_service import LoyaltyService
                    salon_id = row.get("salon_id")
                    service = services.get(row.get("service_id"))
                    if service and service.get("price"):
                        payment_amount = float(service.get("price", 0))
                        if salon_id and payment_amount > 0:
                            points_pending, _ = LoyaltyService.calculate_potential_points(payment_amount, salon_id)
                            enriched["loyalty_points_pending"] = points_pending
                except Exception:
                    pass
            else:
                enriched["payment"] = None
                enriched["payment_status"] = None
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
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='appointments',
                record_id=created_id,
                action='INSERT',
                new_values=payload,
                changed_by=uid
            )
            
            return AppointmentService.get_by_id(created_id, user=user)

        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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

            # Get old values for audit log
            old_values = {k: current.get(k) for k in update_data.keys()}
            
            response = supabase.table("appointments").update(update_data).eq("id", appointment_id).execute()
            if getattr(response, "error", None):
                return None, response.error.message
            if not response.data:
                return None, "Nothing updated"
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='appointments',
                record_id=appointment_id,
                action='UPDATE',
                old_values=old_values,
                new_values=update_data,
                changed_by=user.get('sub')
            )
            
            return AppointmentService.get_by_id(appointment_id, user=user)
        
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            
            # Get old status for audit log
            old_status = current.get("status")
            
            update = {
                "status": "cancelled",
                "cancellation_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Update failed"
            
            # Refund payment and handle loyalty points
            try:
                from services.payment_service import PaymentService
                
                # Find payment for this appointment
                payment_response = supabase.table("payments")\
                    .select("id, payment_status, loyalty_points_used, user_id, salon_id")\
                    .eq("appointment_id", appointment_id)\
                    .eq("payment_status", "completed")\
                    .maybe_single()\
                    .execute()
                
                if payment_response.data:
                    payment = payment_response.data
                    payment_id = payment["id"]
                    loyalty_points_used = payment.get("loyalty_points_used", 0)
                    user_id = payment.get("user_id")
                    salon_id = payment.get("salon_id")
                    
                    # Refund the payment
                    refund_success, refund_error = PaymentService.refund_payment(payment_id, reason=f"Appointment cancelled: {reason or 'No reason provided'}")
                    if not refund_success and refund_error:
                        ErrorLoggingService.log_exception(
                            Exception(f"Failed to refund payment {payment_id}: {refund_error}"),
                            severity='high'
                        )
                    
                    # Refund redeemed loyalty points (add them back to balance)
                    if loyalty_points_used > 0 and user_id and salon_id:
                        try:
                            # Get current balance
                            balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
                            if not error and balance:
                                current_balance = balance.get("points_balance", 0)
                                new_balance = current_balance + loyalty_points_used
                                
                                # Update balance
                                supabase.table("loyalty_balances")\
                                    .update({
                                        "points_balance": new_balance,
                                        "lifetime_points_redeemed": max(0, balance.get("lifetime_points_redeemed", 0) - loyalty_points_used),
                                        "updated_at": datetime.now(timezone.utc).isoformat()
                                    })\
                                    .eq("id", balance["id"])\
                                    .execute()
                                
                                # Create refund transaction record
                                transaction_data = {
                                    "id": str(uuid.uuid4()),
                                    "user_id": user_id,
                                    "salon_id": salon_id,
                                    "transaction_type": "earned",  # Points returned
                                    "points": loyalty_points_used,
                                    "appointment_id": appointment_id,
                                    "payment_id": payment_id,
                                    "description": f"Points refunded due to appointment cancellation"
                                }
                                supabase.table("loyalty_transactions")\
                                    .insert(transaction_data)\
                                    .execute()
                        except Exception as e:
                            ErrorLoggingService.log_exception(
                                Exception(f"Failed to refund loyalty points for cancelled appointment {appointment_id}: {str(e)}"),
                                severity='medium'
                            )
                
                # Remove loyalty points that were earned for this appointment
                # Points are awarded when payment is completed, so we need to reverse them on cancellation
                trans_response = supabase.table("loyalty_transactions")\
                    .select("id, points, user_id, salon_id")\
                    .eq("appointment_id", appointment_id)\
                    .eq("transaction_type", "earned")\
                    .execute()
                
                if trans_response.data:
                    for trans in trans_response.data:
                        # Skip if this is the refund transaction we just created
                        if "refunded" in trans.get("description", "").lower():
                            continue
                            
                        user_id = trans["user_id"]
                        salon_id = trans["salon_id"]
                        points = trans["points"]
                        
                        # Get current balance
                        balance, error = LoyaltyService.get_user_loyalty_balance(user_id, salon_id)
                        if error or not balance:
                            continue
                        
                        current_balance = balance.get("points_balance", 0)
                        new_balance = max(0, current_balance - points)  # Don't go negative
                        
                        # Update balance
                        supabase.table("loyalty_balances")\
                            .update({
                                "points_balance": new_balance,
                                "lifetime_points_earned": max(0, balance.get("lifetime_points_earned", 0) - points),
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            })\
                            .eq("id", balance["id"])\
                            .execute()
                        
                        # Create reversal transaction record
                        # Use "expired" type with negative points to indicate points removed
                        transaction_data = {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "salon_id": salon_id,
                            "transaction_type": "expired",
                            "points": -points,  # Negative to show deduction
                            "appointment_id": appointment_id,
                            "balance_after": new_balance,
                            "description": f"Points removed due to appointment cancellation"
                        }
                        supabase.table("loyalty_transactions")\
                            .insert(transaction_data)\
                            .execute()
            except Exception as e:
                # Log but don't fail appointment cancellation
                ErrorLoggingService.log_exception(
                    Exception(f"Failed to process refunds for cancelled appointment {appointment_id}: {str(e)}"),
                    severity='medium'
                )
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='appointments',
                record_id=appointment_id,
                action='UPDATE',
                old_values={'status': old_status},
                new_values={'status': 'cancelled', 'cancellation_reason': reason},
                changed_by=user.get('sub')
            )
            
            return AppointmentService.get_by_id(appointment_id, user=user)
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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

            barber = supabase.table("barbers").select("salon_id,is_active").eq("id", barber_id).single().execute()
            if getattr(barber,"error",None) or not barber.data or str(barber.data["salon_id"]) != str(salon_id):
                return None, "Barber must belong to the specified salon"
            if not barber.data.get("is_active", True):
                return None, "Barber is not active"

            # validate availability
            ok, msg = AppointmentService.is_barber_available(salon_id, barber_id, new_start_at, new_end_at)
            if not ok:
                return None, msg

            # Get old values for audit log
            old_values = {
                'salon_id': current.get('salon_id'),
                'barber_id': current.get('barber_id'),
                'start_at': current.get('start_at'),
                'end_at': current.get('end_at'),
                'status': current.get('status')
            }
            
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
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='appointments',
                record_id=appointment_id,
                action='UPDATE',
                old_values=old_values,
                new_values=update,
                changed_by=user.get('sub')
            )
            
            return AppointmentService.get_by_id(appointment_id, user=user)
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def mark_completed_or_no_show(appointment_id: str, status: str, *, user: dict):
        if status not in ("completed", "no_show"):
            return None, "Invalid status"

        current, error = AppointmentService.get_by_id(appointment_id, user=user)
        if error:
            return None, error
        
        if not current or not isinstance(current, dict):
            return None, "Appointment not found or invalid"

        role = user.get("role")
        uid = user.get("sub")
        if role == "admin":
            pass
        elif role == "salon_owner":
            salons = supabase.table("salons").select("id").eq("owner_id", uid).execute()
            owned = {s["id"] for s in (salons.data or [])}
            if current.get("salon_id") not in owned:
                return None, "Forbidden"
        elif role == "barber":
            barber_id, _ = AuthService.get_barber_id(uid)
            if not barber_id or current.get("barber_id") != barber_id:
                return None, "Forbidden"
        else:
            return None, "Forbidden"

        # Handle loyalty points based on status change
        from services.loyalty_service import LoyaltyService
        
        # Get current status before update to detect transitions
        old_status = current.get("status", "").lower()
        new_status = status.lower()
        
        # If marking as no-show, remove any loyalty points that were awarded
        if new_status == "no_show" and old_status != "no_show":
            # Find and remove loyalty transactions for this appointment
            try:
                loyalty_trans_response = supabase.table("loyalty_transactions")\
                    .select("id, points, user_id, salon_id")\
                    .eq("appointment_id", appointment_id)\
                    .eq("transaction_type", "earned")\
                    .execute()
                
                if getattr(loyalty_trans_response, "error", None):
                    # Log error but continue with status update
                    ErrorLoggingService.log_exception(
                        Exception(f"Error fetching loyalty transactions: {loyalty_trans_response.error.message}"),
                        severity='medium'
                    )
                elif loyalty_trans_response and loyalty_trans_response.data:
                    transactions = loyalty_trans_response.data or []
                    # Only remove points from "earned" transactions that haven't been removed yet
                    # Check if there are any removal transactions (redeemed with no-show description) to avoid double-removal
                    removed_check = supabase.table("loyalty_transactions")\
                        .select("id, description")\
                        .eq("appointment_id", appointment_id)\
                        .eq("transaction_type", "redeemed")\
                        .ilike("description", "%no-show%")\
                        .execute()  # Check for no-show removals
                    
                    already_removed = len(removed_check.data or []) > 0
                    
                    if not already_removed and transactions:
                        for trans in transactions:
                            trans_id = trans.get("id")
                            points = trans.get("points", 0)
                            user_id = trans.get("user_id")
                            salon_id = trans.get("salon_id")
                            
                            if trans_id and points > 0 and user_id and salon_id:
                                # Remove the points using the dedicated method
                                success, error = LoyaltyService.remove_points_for_no_show(
                                    user_id=user_id,
                                    salon_id=salon_id,
                                    points=points,
                                    appointment_id=appointment_id,
                                    description=f"Points removed due to no-show (original transaction: {trans_id})"
                                )
                                if not success:
                                    # Log error but continue - status update should still succeed
                                    ErrorLoggingService.log_exception(
                                        Exception(f"Failed to remove loyalty points: {error}"),
                                        severity='medium'
                                    )
            except Exception as e:
                # Log but don't fail - the status update should still succeed
                # We want to mark the appointment as no-show even if loyalty point removal fails
                ErrorLoggingService.log_exception(e, severity='high')
                # Don't return error - let the status update proceed
        
        # Update appointment status
        update = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
        if getattr(response, "error", None) or not response.data:
            return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Update failed"
        
        # Award loyalty points when appointment is marked as completed
        # This handles both initial completion and re-completion after no-show
        if new_status == "completed" and old_status != "completed":
            # award_points_for_completed_appointment will check for existing transactions
            # and handle re-awarding if points were previously removed
            LoyaltyService.award_points_for_completed_appointment(appointment_id)
        
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
            service_length = timedelta(minutes=duration_minutes)
            step = timedelta(minutes=15)  # expose 15-min selectable grid

            tz_name = AppointmentService._get_salon_timezone(salon_id)
            tz = ZoneInfo(tz_name)
            try:
                base_date = datetime.fromisoformat(f"{date_str}T00:00:00")
            except ValueError:
                return None, "Invalid date format. Expected YYYY-MM-DD."
            day_local = base_date.replace(tzinfo=tz)
            day_start_local = datetime.combine(day_local.date(), time(0, 0), tz)
            day_end_local = day_start_local + timedelta(days=1)

            dow = (day_local.weekday() + 1) % 7  # shift to Sunday=0 .. Saturday=6
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
                while current + service_length <= window_end:
                    slot_start_utc = current.astimezone(timezone.utc)
                    slot_end_utc = (current + service_length).astimezone(timezone.utc)
                    if slot_start_utc < now_utc:
                        current += step
                        continue
                    if any(u_start < slot_end_utc and u_end > slot_start_utc for u_start, u_end in unavail):
                        current += step
                        continue
                    if any(b_start < slot_end_utc and b_end > slot_start_utc for b_start, b_end in booked):
                        current += step
                        continue
                    slots.append({
                        "start_at": slot_start_utc.isoformat(),
                        "end_at": slot_end_utc.isoformat(),
                        "label": current.strftime("%I:%M %p").lstrip("0") or current.strftime("%H:%M"),
                    })
                    current += step
            return slots, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_customer(customer_id: str, 
                                     when: str = "all",
                                     status=None,
                                     page: int = 1,
                                     limit: int = 100,
                                     sort_order: str = "asc"):
        # fetches all appointments for a specific customer (supports upcoming/past/all)
        try:
            # Get total count first (without pagination)
            # For past appointments, exclude cancelled from count
            count_query = (
                supabase.table("appointments")
                .select("id", count="exact")
                .eq("customer_id", customer_id)
            )
            count_query = AppointmentService._apply_filters(count_query, when, status)
            # Exclude cancelled appointments from past count
            if when == "past":
                count_query = count_query.neq("status", "cancelled")
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else 0
            
            # Get paginated data
            query = (
                supabase.table("appointments")
                .select("*")
                .eq("customer_id", customer_id)
            )
            query = AppointmentService._apply_filters(query, when, status)
            # Exclude cancelled appointments from past results
            if when == "past":
                query = query.neq("status", "cancelled")
            
            # For upcoming: always closest first (ascending). For past: use sort_order
            if when == "upcoming":
                query = query.order("start_at", desc=False)  # Closest first
            else:
                query = query.order("start_at", desc=(sort_order.lower() == "desc"))
            
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message, 0
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None, total_count
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e), 0
        
    @staticmethod
    def get_appointments_by_barber(barber_id: str, 
                                   when: str = "all",
                                   status=None,
                                   page: int = 1,
                                   limit: int = 100,
                                   sort_order: str = "asc"):
        # fetches all appointments for a specific barber (supports upcoming/past/all)
        try:
            # Get total count first
            count_query = (
                supabase.table("appointments")
                .select("id", count="exact")
                .eq("barber_id", barber_id)
            )
            count_query = AppointmentService._apply_filters(count_query, when, status)
            # Exclude cancelled appointments from past count
            if when == "past":
                count_query = count_query.neq("status", "cancelled")
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else 0
            
            # Get paginated data
            query = (
                supabase.table("appointments")
                .select("*")
                .eq("barber_id", barber_id)
            )
            query = AppointmentService._apply_filters(query, when, status)
            # Exclude cancelled appointments from past results
            if when == "past":
                query = query.neq("status", "cancelled")
            
            # For upcoming: always closest first (ascending). For past: use sort_order
            if when == "upcoming":
                query = query.order("start_at", desc=False)  # Closest first
            else:
                query = query.order("start_at", desc=(sort_order.lower() == "desc"))
            
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message, 0
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None, total_count
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e), 0
        
    @staticmethod
    def get_all_salon_appointments(salon_ids: List[str], 
                                   when: str = "all",
                                   status=None,
                                   page: int = 1,
                                   limit: int = 100,
                                   customer_id: Optional[str] = None,
                                   sort_order: str = "asc"):
        # fetches all appointments for a salon (supports upcoming/past/all)
        # If customer_id is provided, filters by customer
        try:
            # Get total count first
            count_query = (
                supabase.table("appointments")
                .select("id", count="exact")
                .in_("salon_id", salon_ids)
            )
            if customer_id:
                count_query = count_query.eq("customer_id", customer_id)
            count_query = AppointmentService._apply_filters(count_query, when, status)
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else 0
            
            # Get paginated data
            query = (
                supabase.table("appointments")
                .select("*")
                .in_("salon_id", salon_ids)
            )
            if customer_id:
                query = query.eq("customer_id", customer_id)
            query = AppointmentService._apply_filters(query, when, status)
            
            # For upcoming: always closest first (ascending). For past: use sort_order
            if when == "upcoming":
                query = query.order("start_at", desc=False)  # Closest first
            else:
                query = query.order("start_at", desc=(sort_order.lower() == "desc"))
            
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message, 0
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None, total_count
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e), 0

    
    @staticmethod
    def get_admin_filtered(salon_id=None, 
                           barber_id=None, 
                           customer_id=None,
                           when="all", 
                           status=None, 
                           page=1, 
                           limit=100,
                           sort_order: str = "asc"):
        """Admin-level query with optional filters."""
        try:
            # Get total count first
            count_query = supabase.table("appointments").select("id", count="exact")
            if salon_id:
                count_query = count_query.eq("salon_id", salon_id)
            if barber_id:
                count_query = count_query.eq("barber_id", barber_id)
            if customer_id:
                count_query = count_query.eq("customer_id", customer_id)
            count_query = AppointmentService._apply_filters(count_query, when, status)
            count_response = count_query.execute()
            total_count = count_response.count if hasattr(count_response, "count") else 0
            
            # Get paginated data
            query = supabase.table("appointments").select("*")
            if salon_id:
                query = query.eq("salon_id", salon_id)
            if barber_id:
                query = query.eq("barber_id", barber_id)
            if customer_id:
                query = query.eq("customer_id", customer_id)
            query = AppointmentService._apply_filters(query, when, status)
            
            # For upcoming: always closest first (ascending). For past: use sort_order
            if when == "upcoming":
                query = query.order("start_at", desc=False)  # Closest first
            else:
                query = query.order("start_at", desc=(sort_order.lower() == "desc"))
            
            query = AppointmentService._paginate(query, page, limit)
            response = query.execute()
            if getattr(response, "error", None):
                return None, response.error.message, 0
            data = AppointmentService._hydrate_appointments(response.data or [])
            return data, None, total_count
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e), 0
