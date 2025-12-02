from config import supabase
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from services.audit_logging_service import AuditLoggingService


class ReviewResponseService:

    @staticmethod
    def create_response(user_id, review_id, message):
        result = (
            supabase.table("reviews")
            .select("*")
            .eq("id", review_id)
            .execute()
        )
        rows = result.data or []
        if len(rows) == 0:
            raise NotFound("Review not found")
        review = rows[0]

        salon_id = review["salon_id"]
        appointment_id = review["appointment_id"]

        appt_result = (
            supabase.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .execute()
        )
        appt_rows = appt_result.data or []
        if len(appt_rows) == 0:
            raise NotFound("Appointment not found")
        appt = appt_rows[0]

        barber_db_id = appt["barber_id"]

        salon_result = (
            supabase.table("salons")
            .select("owner_id")
            .eq("id", salon_id)
            .execute()
        )
        salon_rows = salon_result.data or []
        if len(salon_rows) == 0:
            raise NotFound("Salon not found")
        owner_id = salon_rows[0]["owner_id"]

        barber_result = (
            supabase.table("barbers")
            .select("user_id")
            .eq("id", barber_db_id)
            .execute()
        )
        barber_rows = barber_result.data or []
        if len(barber_rows) == 0:
            raise NotFound("Assigned barber not found")
        assigned_barber_user_id = barber_rows[0]["user_id"]

        if user_id not in (owner_id, assigned_barber_user_id):
            raise Forbidden("Only salon owners or the assigned barber can respond to reviews")

        existing = (
            supabase.table("review_responses")
            .select("id")
            .eq("review_id", review_id)
            .execute()
        ).data or []
        if len(existing) > 0:
            raise BadRequest("This review already has a response")

        response = {
            "review_id": review_id,
            "salon_id": salon_id,
            "response_text": message
        }

        inserted = (
            supabase.table("review_responses")
            .insert(response)
            .execute()
        ).data[0]
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='review_responses',
            record_id=inserted['id'],
            action='INSERT',
            new_values=response,
            changed_by=user_id
        )

        return inserted

    @staticmethod
    def delete_response(user_id, response_id):
        result = (
            supabase.table("review_responses")
            .select("*")
            .eq("id", response_id)
            .execute()
        )
        rows = result.data or []
        if len(rows) == 0:
            raise NotFound("Response not found")
        resp = rows[0]

        if resp["responder_id"] != user_id:
            raise Forbidden("You can only delete your own response")

        # Get old values for audit log
        old_values = {
            'review_id': resp.get('review_id'),
            'salon_id': resp.get('salon_id'),
            'response_text': resp.get('response_text'),
            'responder_id': resp.get('responder_id')
        }

        supabase.table("review_responses").delete().eq("id", response_id).execute()
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='review_responses',
            record_id=response_id,
            action='DELETE',
            old_values=old_values,
            changed_by=user_id
        )

        return {"message": "Response deleted"}

