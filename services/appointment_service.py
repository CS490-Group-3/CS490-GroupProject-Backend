from config import supabase
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class AppointmentService:
    # ------ helpers ------
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
        convert UTC ISO string -> (day of week: int 0 (Sun) ... 6 (Mon), local time: str 'HH:MM:SS').
        """
        dt_utc = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        local = dt_utc.astimezone(ZoneInfo(tz_name))
        # Python: Monday=0 ... Sunday=6. Our DB uses 0..6 too.
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
            .eq("status", "scheduled")
            .lt("start_at", end_at)
            .gt("end_at", start_at)
        )
        if exclude_id:
            query = query.neq("id", exclude_id)
        response = query.execute()
        return bool(response.data)

    # ------ booking methods ------
    @staticmethod
    def create_appointment(appointment_data: Dict):
        # creates an appointment.
        """
        Expects UTC datetimes:
          appointment_data = {
            'customer_id','barber_id','service_id','salon_id',
            'start_at' (ISO or datetime),  'end_at' (optional),
            'notes' (optional)
          }
        """
        try:
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

            appointment_data.setdefault("status", "scheduled")

            payload = {
                "customer_id": appointment_data["customer_id"],
                "barber_id":   appointment_data["barber_id"],
                "service_id":  appointment_data["service_id"],
                "salon_id":    appointment_data["salon_id"],
                "start_at":    appointment_data["start_at"],
                "end_at":      appointment_data["end_at"],
                "status":      appointment_data["status"],
                "notes":       appointment_data.get("notes"),
            }

            response = supabase.table("appointments").insert(payload).execute()
            if getattr(response, "error", None):
                return None, response.error.message
            return response.data[0], None

        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_appointment(appointment_id, update_data):
        """
        updates appointment (supports reschedule status)
        \nNOTE: If any of start_at/end_at/barber_id/salon_id change, re-check overlap.
        """
        try:
            # fetch the current row
            current = supabase.table("appointments").select("*").eq("id", appointment_id).single().execute()
            if getattr(current, "error", None) or not current.data:
                return None, "Appointment not found"
            row = current.data

            new_salon  = update_data.get("salon_id",  row["salon_id"])
            new_barber = update_data.get("barber_id", row["barber_id"])
            new_start  = update_data.get("start_at",  row["start_at"])
            new_end    = update_data.get("end_at",    row["end_at"])

            # check overlap if any time/barber/salon changed
            if any(k in update_data for k in ("start_at","end_at","barber_id","salon_id")):
                if AppointmentService.has_overlap(new_salon, new_barber, new_start, new_end, exclude_id=appointment_id):
                    return None, "Rescheduled time overlaps with another appointment."

            response = supabase.table("appointments").update(update_data).eq("id", appointment_id).execute()
            if getattr(response, "error", None):
                return None, response.error.message
            if not response.data:
                return None, "Nothing updated"
            return response.data[0], None
        
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def cancel_appointment(appointment_id: str, reason: Optional[str] = None):
        # can add cancelled_by parameter in future for auditing purposes
        """
        set status=cancelled, capture optional reason.
        """
        try:
            update = {
                "status": "cancelled",
                "cancellation_reason": reason,
                "updated_at": datetime.utcnow().isoformat(),
            }
            response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Appointment not found"
            return response.data[0], None
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def reschedule_appointment(appointment_id: str, salon_id: str, barber_id: str, new_start_at, new_end_at=None):
        """
        reschedule with proper validation:
          - parse ISO -> datetime if needed
          - compute end from service duration if not provided (we need service_id from row)
          - availability + overlap checks
          - set status=rescheduled
        """
        try:
            # fetch current row (need service_id + duration)
            current = supabase.table("appointments").select("*").eq("id", appointment_id).single().execute()
            if getattr(current, "error", None) or not current.data:
                return None, "Appointment not found"
            row = current.data

            # convert incoming datetimes if str
            if isinstance(new_start_at, str):
                sdt = datetime.fromisoformat(new_start_at.replace("Z", "+00:00"))
            else:
                sdt = new_start_at
            if new_end_at is None:
                # compute end time from service duration if not provided
                service = supabase.table("services").select("duration_minutes").eq("id", row["service_id"]).single().execute()
                if getattr(service, "error", None) or not service.data:
                    return None, "Service not found to compute duration"
                new_end_at = (sdt + timedelta(minutes=int(service.data["duration_minutes"]))).isoformat()
                new_start_at = sdt.isoformat()
            else:
                if isinstance(new_end_at, str):
                    edt = datetime.fromisoformat(new_end_at.replace("Z", "+00:00"))
                else:
                    edt = new_end_at
                new_start_at = sdt.isoformat()
                new_end_at   = edt.isoformat()

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
                "status": "rescheduled",
                "updated_at": datetime.utcnow().isoformat(),
            }
            response = supabase.table("appointments").update(update).eq("id", appointment_id).execute()
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Nothing updated"
            return response.data[0], None
        except Exception as e:
            return None, str(e)
    
    # ------ workflow ------
    @staticmethod
    def confirm_or_deny(appointment_id: str, action: str):
        """
        action: 'confirm' or 'deny'
        """
        try:
            if action not in ("confirm", "deny"):
                return None, "Invalid action"
            status = "scheduled" if action == "confirm" else "denied"
            response = (
                supabase.table("appointments")
                .update({"status": status, "updated_at": datetime.utcnow().isoformat()})
                .eq("id", appointment_id)
                .execute()
            )
            if getattr(response, "error", None) or not response.data:
                return None, getattr(response, "error", None).message if getattr(response, "error", None) else "Appointment not found"
            return response.data[0], None
        except Exception as e:
            return None, str(e)
    
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
    
    # ------ reads ------
    @staticmethod
    def get_by_id(appointment_id: str):
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
            return response.data, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_customer(customer_id):
        # fetches all appointments for a specific customer
        try:
            response = (
                        supabase.table("appointments")
                        .select("*")
                        .eq("customer_id", customer_id)
                        .order("start_at", desc=False)
                        .execute()
            )
            if getattr(response, "error", None):
                return None, response.error.message
            return response.data, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_barber(barber_id):
        # fetches all appointments for a specific barber
        try:
            response = (
                        supabase.table("appointments")
                        .select("*")
                        .eq("barber_id", barber_id)
                        .order("start_at", desc=False)
                        .execute()
            )
            if getattr(response, "error", None):
                return None, response.error.message
            return response.data, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_all_salon_appointments(salon_ids):
        # fetches all appointments for a salon
        try:
            response = (
                        supabase.table("appointments")
                        .select("*")
                        .in_("salon_id", salon_ids)
                        .order("start_at", desc=False)
                        .execute()
            )
            if getattr(response, "error", None):
                return None, response.error.message
            return response.data, None
        except Exception as e:
            return None, str(e)
    
    # ------ history ------
    @staticmethod
    def get_booking_history(user_id: str):
        """
        Returns a user's appointments ordered by start time.
        """
        try:
            response = (
                supabase.table("appointments")
                .select("*")
                .eq("customer_id", user_id)
                .order("start_at", desc=False)
                .execute()
            )
            if getattr(response, "error", None):
                return None, response.error.message
            return response.data or [], None
        except Exception as e:
            return None, str(e)