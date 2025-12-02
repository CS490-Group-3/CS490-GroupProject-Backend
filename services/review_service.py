from config import supabase
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from services.audit_logging_service import AuditLoggingService


class ReviewService:
    @staticmethod
    def create_review(user_id, appointment_id, rating, title, comment):
        # Validate appointment exists and belongs to user
        appt = (
            supabase.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .single()
            .execute()
            .data
        )

        if not appt:
            raise NotFound("Appointment not found")

        if appt["customer_id"] != user_id:
            raise Forbidden("You cannot review an appointment you did not book")

        if appt["status"] != "completed":
            raise BadRequest("Appointment must be completed before reviewing it")

        # Ensure no existing review
        existing = (
            supabase.table("reviews")
            .select("id")
            .eq("appointment_id", appointment_id)
            .execute()
            .data
        )

        if existing:
            raise BadRequest("This appointment already has a review")

        # Insert review
        review = {
            "user_id": user_id,
            "appointment_id": appointment_id,
            "salon_id": appt["salon_id"],
            "rating": rating,
            "title": title,
            "comment": comment,
        }

        response = (
            supabase.table("reviews")
            .insert(review)
            .execute()
        )
        
        created_review = response.data[0]
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='reviews',
            record_id=created_review['id'],
            action='INSERT',
            new_values=review,
            changed_by=user_id
        )
        
        return created_review

    @staticmethod
    def get_review(review_id):
        review = (
            supabase.table("reviews")
            .select("*")
            .eq("id", review_id)
            .execute()
        )
        rows = review.data or []

        if len(rows) == 0:
            raise NotFound("Review not found")

        return rows[0]


    @staticmethod
    def update_review(user_id, review_id, rating, title, comment):
        review = ReviewService.get_review(review_id)

        if review["user_id"] != user_id:
            raise Forbidden("You can only edit your own reviews")

        # Get old values for audit log
        old_values = {
            'rating': review.get('rating'),
            'title': review.get('title'),
            'comment': review.get('comment')
        }

        update = {
            "rating": rating,
            "title": title,
            "comment": comment
        }

        response = (
            supabase.table("reviews")
            .update(update)
            .eq("id", review_id)
            .execute()
        )
        
        updated_review = response.data[0]
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='reviews',
            record_id=review_id,
            action='UPDATE',
            old_values=old_values,
            new_values=update,
            changed_by=user_id
        )
        
        return updated_review

    @staticmethod
    def delete_review(user_id, review_id):
        review = ReviewService.get_review(review_id)

        if review["user_id"] != user_id:
            raise Forbidden("You can only delete your own reviews")

        # Get old values for audit log before deletion
        old_values = {
            'user_id': review.get('user_id'),
            'appointment_id': review.get('appointment_id'),
            'salon_id': review.get('salon_id'),
            'rating': review.get('rating'),
            'title': review.get('title'),
            'comment': review.get('comment')
        }

        supabase.table("reviews").delete().eq("id", review_id).execute()
        
        # Log audit
        AuditLoggingService.log_audit(
            table_name='reviews',
            record_id=review_id,
            action='DELETE',
            old_values=old_values,
            changed_by=user_id
        )

        return {"message": "Review deleted successfully"}

    @staticmethod
    def get_reviews_for_salon(salon_id, rating=None):
        query = (
            supabase.table("reviews")
            .select("*")
            .eq("salon_id", salon_id)
        )
        if rating is not None:
            rating_str = str(rating).lower().strip()
            if rating_str != "all":
                try:
                    rating_value = int(rating_str)
                    if 1 <= rating_value <= 5:
                        query = query.eq("rating", rating_value)
                except ValueError:
                    pass 
        reviews = query.order("created_at", desc=True).execute().data

        # Fetch responses for all reviews
        if reviews:
            review_ids = [r["id"] for r in reviews]
            responses_resp = (
                supabase.table("review_responses")
                .select("*")
                .in_("review_id", review_ids)
                .execute()
            )
            responses = {r["review_id"]: r for r in (responses_resp.data or [])}
            
            # Attach responses to reviews
            for review in reviews:
                review["response"] = responses.get(review["id"])
        
        return reviews

    @staticmethod
    def get_full_review(review_id):
        review = ReviewService.get_review(review_id)

        response_result = (supabase.table("review_responses").select("*").eq("review_id", review_id).execute())

        response = response_result.data[0] if response_result.data else None


        images_result = (supabase.table("review_images").select("*").eq("review_id", review_id).execute())


        images = images_result.data or []

        review["response"] = response
        review["images"] = images

        return review
