from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError

class AppointmentService:
    @staticmethod
    def has_overlap(salon_id, barber_id, appt_date, start, end):
        response = supabase.table("appointments").select("id").eq("salon_id", salon_id).eq("barber_id", barber_id).eq("appointment_date", appt_date).or_(f"start_time.lt.{end},end_time.gt.{start}").execute()
    
        return len(response.data) > 0
    @staticmethod
    def create_appointment(appointment_data):
        # Logic to create an appointment
        try:
            if AppointmentService.has_overlap(
                salon_id=appointment_data["salon_id"],
                barber_id=appointment_data["barber_id"],
                appt_date=appointment_data["appointment_date"],
                start=appointment_data["start_time"],
                end=appointment_data["end_time"]
            ):
                return None, "Appointment time overlaps with an existing appointment."
            response = supabase.table("appointments").insert(appointment_data).execute()
            if response.error:
                return None, response.error.message
            
            created_appointment = response.data[0]
            return created_appointment, None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_appointment(appointment_id, update_data):
        # Logic to update an existing appointment
        try:
            response = supabase.table("appointments").update(update_data).eq("id", appointment_id).execute()
            if response.error:
                return None, response.error.message
            
            updated_appointment = response.data[0]
            return updated_appointment, None
        except Exception as e:
            return None, str(e)
        
    @staticmethod
    def get_appointments_by_customer(customer_id):
        # Logic to fetch appointments for a specific customer
        try:
            response = supabase.table("appointments").select("*").eq("customer_id", customer_id).execute()
            if response.error:
                return None, response.error.message
            
            appointments = [record for record in response.data]
            return appointments, None
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_appointments_by_barber(barber_id):
        # Logic to fetch appointments for a specific barber
        try:
            response = supabase.table("appointments").select("*").eq("barber_id", barber_id).execute()
            if response.error:
                return None, response.error.message
            
            appointments = [record for record in response.data]
            return appointments, None
        except Exception as e:
            return None, str(e)
    @staticmethod
    def get_all_salon_appointments(salon_ids):
        # Logic to fetch all appointments
        try:
            response = supabase.table("appointments").select("*").in_("salon_id", salon_ids).execute()
            if response.error:
                return None, response.error.message
            
            appointments = [record for record in response.data]
            return appointments, None
        except Exception as e:
            return None, str(e)