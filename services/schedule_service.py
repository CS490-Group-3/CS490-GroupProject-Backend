from config import supabase
from typing import Dict, Optional, Tuple, List
from datetime import time, datetime, timezone


class ScheduleService:
    @staticmethod
    def _to_utc_iso(dt_or_str):
        """
        Normalize incoming datetime (string or datetime) to an ISO UTC string.
        """
        if isinstance(dt_or_str, str):
            dt = datetime.fromisoformat(dt_or_str.replace("Z", "+00:00"))
        else:
            dt = dt_or_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def check_barber_exists(barber_id: str) -> bool:
        """
        Check if a barber exists in the users table.
        
        Args:
            barber_id (str): ID of the barber to check.
        Returns:
            bool: True if barber exists, False otherwise.
        """
        try:
            print("Checking if barber exists with ID:", barber_id)
            response = supabase.table("barbers").select("id").eq("id", barber_id).execute()
            if not response:
                return False
            return len(response.data) > 0
        except Exception:
            return False
    @staticmethod
    def create_availability(
        barber_id: str,
        day_of_week: int,
        start_time: str | time,
        end_time: str | time,
        is_active: bool = True
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a new barber availability entry in the database.
        
        Args:
            barber_id (str): ID of the barber.
            day_of_week (int): Day of the week (0=Sunday ... 6=Saturday).
            start_time (str): Start time in HH:MM format.
            end_time (str): End time in HH:MM format.
            is_active (bool): Whether the availability is active.
        
        Returns:
            Tuple containing the created availability dict or None, and an error message or None.
        """
        try:
            if isinstance(start_time, time):
                start_time = start_time.strftime("%H:%M:%S")
            if isinstance(end_time, time):
                end_time = end_time.strftime("%H:%M:%S")
            data = {
                "barber_id": barber_id,
                "day_of_week": day_of_week,
                "start_time": start_time,
                "end_time": end_time,
                "is_active": is_active
            }
            availability_exists = supabase.table("barber_availability").select("id").eq("barber_id", barber_id).eq("day_of_week", day_of_week).execute()
            
            # Check if availability for the same day already exists if it does not exist, create new entry
            if not getattr(availability_exists, "data", None):
                response = supabase.table("barber_availability").insert(data).execute()
                if not getattr(response, "data", None):
                    return None, f"Supabase insert failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
            
                return response.data[0], None
            # If it exists, return error
            return None, f"Availability for barber {barber_id} on day {day_of_week} already exists."
        
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def update_availability(
        availability_id: str,
        update_data: Dict
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update an existing barber availability entry in the database.
        
        Args:
            availability_id (str): ID of the availability entry to update.
            update_data (Dict): Dictionary of fields to update.
        
        Returns:
            Tuple containing the updated availability dict or None, and an error message or None.
        """
        try:
            
            response = supabase.table("barber_availability").update(update_data).eq("id", availability_id).execute()
            if not getattr(response, "data", None):
                return None, f"Supabase insert failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
            
            return response.data[0], None
        
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_availability(
        barber_id: str
    ) -> Tuple[Optional[list], Optional[str]]:
        """
        Retrieve all availability entries for a given barber.
        
        Args:
            barber_id (str): ID of the barber.
        Returns:
            Tuple containing a list of availability entries or None, and an error message or None.
        """
        try:
            response = supabase.table("barber_availability").select("*").eq("barber_id", barber_id).execute()
            if not getattr(response, "data", None):
                return None, f"Supabase insert failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
            
            return response.data, None
        
        except Exception as e:
            return None, str(e)

    # -------- unavailability / blocking -----------
    @staticmethod
    def list_unavailability(
        barber_id: str,
        start_from: Optional[datetime] = None,
        end_before: Optional[datetime] = None,
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        """
        Fetch blocked (unavailability) entries for a barber.
        """
        try:
            query = (
                supabase.table("barber_unavailability")
                .select("*")
                .eq("barber_id", barber_id)
                .order("start_datetime", desc=False)
            )
            if start_from:
                query = query.gte("end_datetime", ScheduleService._to_utc_iso(start_from))
            if end_before:
                query = query.lt("start_datetime", ScheduleService._to_utc_iso(end_before))

            response = query.execute()
            return response.data or [], None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def create_unavailability(
        barber_id: str,
        start_datetime,
        end_datetime,
        reason: Optional[str] = None,
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Block off a specific time window for a barber.
        """
        try:
            start_iso = ScheduleService._to_utc_iso(start_datetime)
            end_iso = ScheduleService._to_utc_iso(end_datetime)
            if start_iso >= end_iso:
                return None, "start_datetime must be before end_datetime"
            # prevent overlapping with existing blocked windows
            overlap = (
                supabase.table("barber_unavailability")
                .select("id")
                .eq("barber_id", barber_id)
                .lt("start_datetime", end_iso)
                .gt("end_datetime", start_iso)
                .execute()
            )
            if overlap.data:
                return None, "Requested block overlaps an existing blocked time"
            # prevent blocking on top of scheduled/confirmed appointments
            appointments = (
                supabase.table("appointments")
                .select("id")
                .eq("barber_id", barber_id)
                .in_("status", ["scheduled", "confirmed"])
                .lt("start_at", end_iso)
                .gt("end_at", start_iso)
                .execute()
            )
            if appointments.data:
                return None, "There are scheduled appointments in that window. Cancel/reschedule them first."

            payload = {
                "barber_id": barber_id,
                "start_datetime": start_iso,
                "end_datetime": end_iso,
                "reason": reason,
            }
            response = supabase.table("barber_unavailability").insert(payload).execute()
            if not getattr(response, "data", None):
                return None, f"Supabase insert failed (status {getattr(response, 'status_code', 'unknown')}): {response}"

            return response.data[0], None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_unavailability(
        block_id: str,
        barber_id: str,
        updates: Dict,
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Update an existing blocked window.
        """
        try:
            existing = (
                supabase.table("barber_unavailability")
                .select("*")
                .eq("id", block_id)
                .single()
                .execute()
            )
            if getattr(existing, "error", None) or not existing.data:
                return None, "Blocked time not found"
            if existing.data.get("barber_id") != barber_id:
                return None, "Forbidden"

            start_iso = updates.get("start_datetime")
            end_iso = updates.get("end_datetime")
            if start_iso:
                start_iso = ScheduleService._to_utc_iso(start_iso)
            else:
                start_iso = existing.data["start_datetime"]
            if end_iso:
                end_iso = ScheduleService._to_utc_iso(end_iso)
            else:
                end_iso = existing.data["end_datetime"]

            if start_iso >= end_iso:
                return None, "start_datetime must be before end_datetime"

            reason = updates.get("reason", existing.data.get("reason"))
            # prevent overlap with other blocks (excluding this one)
            overlap = (
                supabase.table("barber_unavailability")
                .select("id")
                .eq("barber_id", barber_id)
                .neq("id", block_id)
                .lt("start_datetime", end_iso)
                .gt("end_datetime", start_iso)
                .execute()
            )
            if overlap.data:
                return None, "Updated block overlaps another blocked time"
            # prevent conflicts with scheduled appointments
            appointments = (
                supabase.table("appointments")
                .select("id")
                .eq("barber_id", barber_id)
                .in_("status", ["scheduled", "confirmed"])
                .lt("start_at", end_iso)
                .gt("end_at", start_iso)
                .execute()
            )
            if appointments.data:
                return None, "There are scheduled appointments in that window. Cancel/reschedule them first."

            update_payload = {
                "start_datetime": start_iso,
                "end_datetime": end_iso,
                "reason": reason,
            }

            response = (
                supabase.table("barber_unavailability")
                .update(update_payload)
                .eq("id", block_id)
                .execute()
            )
            if not getattr(response, "data", None):
                return None, f"Supabase update failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
            return response.data[0], None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def delete_unavailability(block_id: str, barber_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete an existing blocked window.
        """
        try:
            existing = (
                supabase.table("barber_unavailability")
                .select("barber_id")
                .eq("id", block_id)
                .single()
                .execute()
            )
            if getattr(existing, "error", None) or not existing.data:
                return False, "Blocked time not found"
            if existing.data.get("barber_id") != barber_id:
                return False, "Forbidden"

            response = (
                supabase.table("barber_unavailability")
                .delete()
                .eq("id", block_id)
                .execute()
            )
            if getattr(response, "error", None):
                return False, f"Failed to delete block: {response.error}"
            return True, None
        except Exception as e:
            return False, str(e)
