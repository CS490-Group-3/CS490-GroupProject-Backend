from config import supabase
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

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
    def has_overlap(salon_id: str, barber_id: str, start_at, end_at, exclude_id: Optional[str] = None) -> bool:
        # helper method to determine if appointments overlap; returns bool
        # HALF-OPEN overlap: existing.start < new_end AND existing.end > new_start
        # allows for the edge case where new appointment ends EXACTLY when another starts (or vice versa)
        query = (
            supabase.table("appointments")
            .select("id")
            .eq("salon_id", salon_id)
            .eq("barber_id", barber_id)
            .lt("start_at", end_at)
            .gt("end_at", start_at)
        )
        if exclude_id:
            query = query.neq("id", exclude_id)
        response = query.execute()
        return bool(response.data)

    # ------ main methods ------
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
            appointment_data["start_at"] = start_at.astimezone().isoformat()
            appointment_data["end_at"] = end_at.astimezone().isoformat()

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
        NOTE: If any of start_at/end_at/barber_id/salon_id change, re-check overlap.
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
            if response.error:
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
            if response.error:
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
            if response.error:
                return None, response.error.message
            return response.data, None
        except Exception as e:
            return None, str(e)