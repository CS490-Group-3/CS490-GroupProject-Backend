from config import supabase
from typing import Dict, Optional, Tuple, List
from datetime import time, datetime, timezone
from services.error_logging_service import ErrorLoggingService
from services.audit_logging_service import AuditLoggingService


class ScheduleService:
    @staticmethod
    def _format_time_12h(time_str: str) -> str:
        """
        Convert 24-hour time string (HH:MM:SS or HH:MM) to 12-hour format (H:MM AM/PM).
        
        Args:
            time_str: Time in 24-hour format (e.g., "22:00:00" or "09:30")
        
        Returns:
            Time in 12-hour format (e.g., "10:00 PM" or "9:30 AM")
        """
        try:
            # Parse the time string
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            
            # Convert to 12-hour format
            period = "AM" if hours < 12 else "PM"
            if hours == 0:
                hours_12 = 12
            elif hours == 12:
                hours_12 = 12
            else:
                hours_12 = hours % 12
            
            # Format with minutes
            if minutes == 0:
                return f"{hours_12} {period}"
            else:
                return f"{hours_12}:{minutes:02d} {period}"
        except (ValueError, IndexError):
            # If parsing fails, return original
            return time_str
    
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
            # Convert time objects to strings, handle None
            if start_time is None:
                start_time = "00:00:00"
            elif isinstance(start_time, time):
                start_time = start_time.strftime("%H:%M:%S")
            elif not isinstance(start_time, str):
                start_time = str(start_time)
            
            if end_time is None:
                end_time = "00:00:00"
            elif isinstance(end_time, time):
                end_time = end_time.strftime("%H:%M:%S")
            elif not isinstance(end_time, str):
                end_time = str(end_time)

            # validate within salon hours (only if is_active is True and times are valid)
            # For closed days (is_active=False), we allow 00:00:00 to 00:00:00 without validation
            if is_active and start_time and end_time and (start_time != "00:00:00" or end_time != "00:00:00"):
                ok, err = ScheduleService._is_within_salon_hours(barber_id, day_of_week, start_time, end_time)
                if not ok:
                    return None, err

            data = {
                "barber_id": barber_id,
                "day_of_week": day_of_week,
                "start_time": start_time,
                "end_time": end_time,
                "is_active": is_active
            }
            
            # Upsert logic: check if availability for the same day already exists
            availability_exists = supabase.table("barber_availability").select("id").eq("barber_id", barber_id).eq("day_of_week", day_of_week).execute()
            
            if getattr(availability_exists, "data", None) and len(availability_exists.data) > 0:
                # Update existing entry
                existing_id = availability_exists.data[0]["id"]
                
                # Get old values for audit log
                existing_full = supabase.table("barber_availability").select("*").eq("id", existing_id).single().execute()
                old_values = existing_full.data if getattr(existing_full, "data", None) else {}
                
                response = supabase.table("barber_availability").update(data).eq("id", existing_id).execute()
                if not getattr(response, "data", None):
                    return None, f"Supabase update failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
                
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='barber_availability',
                    record_id=existing_id,
                    action='UPDATE',
                    old_values=old_values,
                    new_values=data,
                    changed_by=None
                )
                
                return response.data[0], None
            else:
                # Create new entry
                response = supabase.table("barber_availability").insert(data).execute()
                if not getattr(response, "data", None):
                    return None, f"Supabase insert failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
                
                created_id = response.data[0]["id"]
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='barber_availability',
                    record_id=created_id,
                    action='INSERT',
                    new_values=data,
                    changed_by=None
                )
                
                return response.data[0], None
        
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            # fetch existing to resolve barber_id/day if not passed
            existing = (
                supabase.table("barber_availability")
                .select("barber_id,day_of_week,start_time,end_time")
                .eq("id", availability_id)
                .single()
                .execute()
            )
            if getattr(existing, "error", None) or not existing.data:
                return None, "Availability entry not found"

            barber_id = existing.data["barber_id"]
            day_of_week = update_data.get("day_of_week", existing.data["day_of_week"])
            start_time = update_data.get("start_time", existing.data["start_time"])
            end_time = update_data.get("end_time", existing.data["end_time"])

            # Get is_active from update_data, or use existing value if not provided
            is_active = update_data.get("is_active")
            if is_active is None:
                # If is_active is not in update_data, keep existing value
                is_active = existing.data.get("is_active", True)
            
            # CRITICAL: Always include is_active in update_data to ensure it gets updated
            update_data["is_active"] = is_active
            
            # CRITICAL: Only validate salon hours if is_active is explicitly True
            # If is_active is False, the barber is unavailable and we don't need to validate salon hours
            # This allows barbers to be unavailable on days the salon is open
            if is_active is False:
                # Barber is unavailable - no need to validate salon hours
                # Ensure times are set to 00:00:00 for consistency if not provided
                if "start_time" not in update_data or update_data.get("start_time") is None:
                    update_data["start_time"] = "00:00:00"
                if "end_time" not in update_data or update_data.get("end_time") is None:
                    update_data["end_time"] = "00:00:00"
            elif is_active is True and start_time and end_time and (start_time != "00:00:00" or end_time != "00:00:00"):
                # Barber is available - validate that their hours are within salon hours
                ok, err = ScheduleService._is_within_salon_hours(barber_id, day_of_week, start_time, end_time)
                if not ok:
                    return None, err
            
            # Get old values for audit log
            old_values = {
                'day_of_week': existing.data.get('day_of_week'),
                'start_time': existing.data.get('start_time'),
                'end_time': existing.data.get('end_time')
            }
            
            response = supabase.table("barber_availability").update(update_data).eq("id", availability_id).execute()
            if not getattr(response, "data", None):
                return None, f"Supabase update failed (status {getattr(response, 'status_code', 'unknown')}): {response}"
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='barber_availability',
                record_id=availability_id,
                action='UPDATE',
                old_values=old_values,
                new_values=update_data,
                changed_by=None  # Could get from context if needed
            )
            
            return response.data[0], None
        
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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
            
            # Check for actual errors
            if getattr(response, "error", None):
                return None, f"Supabase query failed: {response.error}"
            
            # Empty list is valid (barber has no availability entries yet)
            # Return empty list instead of None
            return response.data if response.data is not None else [], None
        
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def _trim_availability_to_salon_hours(barber_start: str, barber_end: str, salon_open: str, salon_close: str) -> tuple:
        """
        Trim barber availability to fit within salon hours.
        Returns (trimmed_start, trimmed_end) that fits within salon hours.
        
        Handles:
        - Normal hours (salon_open < salon_close)
        - Cross-midnight hours (salon_close < salon_open)
        - 24/7 salon (salon_open == salon_close)
        - 24/7 barber (barber_start == barber_end == "00:00:00") - trim to salon hours
        """
        # If salon is 24/7, barber can have any hours
        if salon_open == salon_close:
            return barber_start, barber_end
        
        # Special case: If barber has 00:00:00 to 00:00:00, they're available 24/7
        # This should be trimmed to salon hours
        if barber_start == "00:00:00" and barber_end == "00:00:00":
            return salon_open, salon_close
        
        # Normal hours: salon_open < salon_close (e.g., 09:00 to 18:00)
        if salon_open < salon_close:
            # Clamp barber start to be >= salon_open
            trimmed_start = barber_start if barber_start >= salon_open else salon_open
            # Clamp barber end to be <= salon_close
            trimmed_end = barber_end if barber_end <= salon_close else salon_close
            return trimmed_start, trimmed_end
        
        # Cross-midnight: salon_close < salon_open (e.g., 22:00 to 02:00)
        # Salon is open from salon_open to midnight, then midnight to salon_close
        # Barber availability can be:
        # 1. Entirely in late-night portion (barber_start >= salon_open, barber_end < salon_open)
        # 2. Entirely in early-morning portion (barber_start < salon_open, barber_end <= salon_close)
        # 3. Spans midnight (barber_start >= salon_open, barber_end <= salon_close)
        # 4. Outside salon hours (needs trimming)
        
        # Check if barber is in late-night portion (e.g., 23:00 to 23:30)
        if barber_start >= salon_open and barber_end < salon_open:
            # Barber is entirely in late-night - trim within that window
            trimmed_start = barber_start if barber_start >= salon_open else salon_open
            trimmed_end = barber_end if barber_end < salon_open else salon_open  # Don't go past midnight
            return trimmed_start, trimmed_end
        
        # Check if barber is in early-morning portion (e.g., 01:00 to 01:30)
        if barber_start < salon_open and barber_end <= salon_close:
            # Barber is entirely in early-morning - trim within that window
            trimmed_start = barber_start if barber_start >= "00:00:00" else "00:00:00"
            trimmed_end = barber_end if barber_end <= salon_close else salon_close
            return trimmed_start, trimmed_end
        
        # Check if barber spans midnight and is within salon hours (e.g., 23:00 to 01:00)
        if barber_start >= salon_open and barber_end <= salon_close:
            # Barber spans midnight and is within salon hours - no trimming needed
            return barber_start, barber_end
        
        # Barber is outside salon hours - trim to fit within salon's cross-midnight window
        # If barber starts before salon opens, clamp start to salon_open
        # If barber ends after salon closes, clamp end to salon_close
        if barber_start < salon_open:
            # Barber starts before salon opens - clamp to salon_open
            trimmed_start = salon_open
        else:
            # Barber starts at or after salon opens - keep it (but ensure it's >= salon_open)
            trimmed_start = barber_start if barber_start >= salon_open else salon_open
        
        if barber_end > salon_close and barber_end < salon_open:
            # Barber ends in late-night portion but after salon closes - clamp to salon_close
            trimmed_end = salon_close
        elif barber_end > salon_close:
            # Barber ends after salon closes (in early morning) - clamp to salon_close
            trimmed_end = salon_close
        else:
            # Barber ends at or before salon closes - keep it (but ensure it's <= salon_close)
            trimmed_end = barber_end if barber_end <= salon_close else salon_close
        
        return trimmed_start, trimmed_end
    
    @staticmethod
    def sync_barber_availability_to_salon_hours(salon_id: str = None, salon_hours_map: dict = None, barber_id: str = None):
        """
        Sync barber availability times to match current salon hours.
        This is called when salon hours are updated or when a barber is rehired at a different salon.
        
        Rules:
        - If salon closes a day: mark barber as unavailable (is_active=False)
        - If salon opens a day: 
          * If barber availability is already within salon hours: no change
          * If barber availability is outside salon hours: trim to fit within salon hours
          * PRESERVE is_active status (don't auto-activate barber)
        - If barber is unavailable (is_active=False): keep them unavailable even if salon opens
        
        Args:
            salon_id: Salon ID (required if barber_id not provided)
            salon_hours_map: Dictionary mapping day_of_week (0-6) to salon hour dict with:
                - open_time: str
                - close_time: str
                - is_closed: bool
            barber_id: Optional barber ID to sync only one barber (for rehiring case)
        
        Returns:
            Tuple of (success_count, error_count, errors_list)
        """
        try:
            # If barber_id is provided, sync only that barber (for rehiring case)
            # Otherwise, sync all barbers for the salon
            if barber_id:
                barber_ids = [barber_id]
            elif salon_id:
                # Get all barbers for this salon
                barbers_resp = supabase.table("barbers").select("id").eq("salon_id", salon_id).execute()
                if getattr(barbers_resp, "error", None) or not barbers_resp.data:
                    return 0, 0, []
                
                barber_ids = [b["id"] for b in barbers_resp.data]
            else:
                return 0, 0, ["Either salon_id or barber_id must be provided"]
            success_count = 0
            error_count = 0
            errors = []
            
            # For each barber, sync their availability
            for barber_id in barber_ids:
                try:
                    # Get current availability for this barber
                    avail_resp = supabase.table("barber_availability").select("*").eq("barber_id", barber_id).execute()
                    if getattr(avail_resp, "error", None):
                        error_count += 1
                        errors.append(f"Error fetching availability for barber {barber_id}: {avail_resp.error}")
                        continue
                    
                    existing_availability = {av["day_of_week"]: av for av in (avail_resp.data or [])}
                    
                    # Sync each day
                    for day in range(7):  # 0-6 for Sunday-Saturday
                        salon_hour = salon_hours_map.get(day)
                        if not salon_hour:
                            continue  # Skip if no salon hour for this day
                        
                        existing = existing_availability.get(day)
                        salon_is_closed = salon_hour.get("is_closed", False)
                        salon_open = salon_hour.get("open_time", "00:00:00")
                        salon_close = salon_hour.get("close_time", "00:00:00")
                        
                        if existing:
                            barber_is_active = existing.get("is_active", True)
                            barber_start = existing.get("start_time", "00:00:00")
                            barber_end = existing.get("end_time", "00:00:00")
                            
                            # If salon is closed, mark barber as unavailable
                            if salon_is_closed:
                                new_is_active = False
                                new_start_time = "00:00:00"
                                new_end_time = "00:00:00"
                            else:
                                # Salon is open
                                # PRESERVE is_active status - don't auto-activate barber
                                new_is_active = barber_is_active
                                
                                if barber_is_active:
                                    # Barber is available - check if times need trimming
                                    trimmed_start, trimmed_end = ScheduleService._trim_availability_to_salon_hours(
                                        barber_start, barber_end, salon_open, salon_close
                                    )
                                    
                                    # Always set the trimmed times (even if unchanged, ensures consistency)
                                    new_start_time = trimmed_start
                                    new_end_time = trimmed_end
                                else:
                                    # Barber is unavailable - keep them unavailable, but update times to salon hours for reference
                                    new_start_time = salon_open
                                    new_end_time = salon_close
                            
                            # Update if something changed
                            if (existing.get("start_time") != new_start_time or 
                                existing.get("end_time") != new_end_time or
                                existing.get("is_active") != new_is_active):
                                
                                update_resp = supabase.table("barber_availability").update({
                                    "start_time": new_start_time,
                                    "end_time": new_end_time,
                                    "is_active": new_is_active
                                }).eq("id", existing["id"]).execute()
                                
                                if getattr(update_resp, "error", None):
                                    error_count += 1
                                    errors.append(f"Error updating availability for barber {barber_id} day {day}: {update_resp.error}")
                                else:
                                    success_count += 1
                        else:
                            # No existing entry - create one
                            # If salon is closed, create with is_active=False
                            # If salon is open, create with is_active=False (don't auto-activate)
                            new_is_active = False  # Don't auto-activate barber when salon opens
                            new_start_time = "00:00:00" if salon_is_closed else salon_open
                            new_end_time = "00:00:00" if salon_is_closed else salon_close
                            
                            insert_resp = supabase.table("barber_availability").insert({
                                "barber_id": barber_id,
                                "day_of_week": day,
                                "start_time": new_start_time,
                                "end_time": new_end_time,
                                "is_active": new_is_active
                            }).execute()
                            
                            if getattr(insert_resp, "error", None):
                                error_count += 1
                                errors.append(f"Error creating availability for barber {barber_id} day {day}: {insert_resp.error}")
                            else:
                                success_count += 1
                
                except Exception as e:
                    error_count += 1
                    errors.append(f"Error syncing barber {barber_id}: {str(e)}")
                    ErrorLoggingService.log_exception(e, severity='medium')
            
            return success_count, error_count, errors
        
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return 0, 0, [str(e)]

    @staticmethod
    def _is_within_salon_hours(barber_id: str, day_of_week: int, start_time: str, end_time: str) -> Tuple[bool, Optional[str]]:
        """
        Ensure a barber availability window stays within the salon's hours for that day.
        """
        try:
            barber_resp = (
                supabase.table("barbers")
                .select("salon_id")
                .eq("id", barber_id)
                .single()
                .execute()
            )
            if getattr(barber_resp, "error", None) or not barber_resp.data:
                return False, "Barber not found"

            salon_id = barber_resp.data.get("salon_id")
            hours_resp = (
                supabase.table("salon_hours")
                .select("open_time,close_time,is_closed,day_of_week")
                .eq("salon_id", salon_id)
                .eq("day_of_week", day_of_week)
                .single()
                .execute()
            )
            hours = hours_resp.data if not getattr(hours_resp, "error", None) else None
            if not hours:
                return False, "Salon hours not configured for that day"
            # Note: We allow barber availability to be set to is_active=false even if salon is closed
            # The caller should check is_active before calling this function
            if hours.get("is_closed"):
                return False, "Salon is closed on that day. Barber availability cannot be set for closed days."

            salon_open = hours.get("open_time")
            salon_close = hours.get("close_time")
            if not (salon_open and salon_close):
                return False, "Salon hours missing for that day"

            # Handle different hour scenarios:
            # 1. 24/7 salon: open_time == close_time (always open)
            if salon_open == salon_close:
                return True, None
            
            # 2. Cross-midnight hours: close_time < open_time (e.g., 22:00 to 02:00)
            #    Salon is open from open_time to midnight, then midnight to close_time
            #    Availability is valid if it's within either portion or spans the boundary
            if salon_close < salon_open:
                # Case 1: Entirely in late-night portion (e.g., 23:00 to 23:30)
                if start_time >= salon_open and end_time < salon_open:
                    return True, None
                # Case 2: Entirely in early-morning portion (e.g., 01:00 to 01:30)
                if start_time < salon_open and end_time <= salon_close:
                    return True, None
                # Case 3: Spans midnight boundary (e.g., 23:00 to 01:00)
                if start_time >= salon_open and end_time <= salon_close:
                    return True, None
                # Format times for user-friendly error message
                open_12h = ScheduleService._format_time_12h(salon_open)
                close_12h = ScheduleService._format_time_12h(salon_close)
                return False, f"Barber hours must be within salon hours ({open_12h} - {close_12h} next day)"
            
            # 3. Normal hours: open_time < close_time (e.g., 09:00 to 18:00)
            #    Time is valid if: time >= open_time AND time <= close_time
            if start_time < salon_open or end_time > salon_close:
                # Format times for user-friendly error message
                open_12h = ScheduleService._format_time_12h(salon_open)
                close_12h = ScheduleService._format_time_12h(salon_close)
                return False, f"Barber hours must be within salon hours ({open_12h} - {close_12h})"
            return True, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)

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
            ErrorLoggingService.log_exception(e, severity='high')
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
            ErrorLoggingService.log_exception(e, severity='high')
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

            # Get old values for audit log
            old_values = {
                'start_datetime': existing.data.get('start_datetime'),
                'end_datetime': existing.data.get('end_datetime'),
                'reason': existing.data.get('reason')
            }
            
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
            
            # Log audit
            AuditLoggingService.log_audit(
                table_name='barber_unavailability',
                record_id=block_id,
                action='UPDATE',
                old_values=old_values,
                new_values=update_payload,
                changed_by=None  # Could get from context if needed
            )
            
            return response.data[0], None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
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

            # Get old values for audit log before deletion
            old_block = supabase.table("barber_unavailability").select("*").eq("id", block_id).maybe_single().execute()
            old_values = old_block.data if old_block.data else {}

            response = (
                supabase.table("barber_unavailability")
                .delete()
                .eq("id", block_id)
                .execute()
            )
            if getattr(response, "error", None):
                return False, f"Failed to delete block: {response.error}"
            
            # Log audit
            if old_values:
                AuditLoggingService.log_audit(
                    table_name='barber_unavailability',
                    record_id=block_id,
                    action='DELETE',
                    old_values=old_values,
                    changed_by=None  # Could get from context if needed
                )
            
            return True, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
