from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
from datetime import time
class ScheduleService:
    
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