from config import supabase
from services.upload_file import StorageService
from werkzeug.exceptions import BadRequest, Forbidden   # same style as your project

class ReviewImageService:

    @staticmethod
    def upload_image(user_id, review_id, file):

        review = (
            supabase.table("reviews")
            .select("*")
            .eq("id", review_id)
            .single()
            .execute()
            .data
        )

        if not review:
            raise BadRequest("Review not found")

        if review["user_id"] != user_id:
            raise Forbidden("You can only upload images for your own reviews")

        result = StorageService.upload_review_image(file, review_id, user_id)

        record = {
            "review_id": review_id,
            "file_url": result["filepath"],
            "uploaded_by": user_id
        }

        row = (
            supabase.table("review_images")
            .insert(record)
            .execute()
            .data[0]
        )

        row["signed_url"] = result["signed_url"] 

        return row



    @staticmethod
    def list_images(review_id):
        images = (
            supabase.table("review_images")
            .select("*")
            .eq("review_id", review_id)
            .execute()
            .data
        )

        return images


    @staticmethod
    def delete_image(user_id, image_id):
        img = (
            supabase.table("review_images")
            .select("*")
            .eq("id", image_id)
            .single()
            .execute()
            .data
        )

        if not img:
            raise NotFound("Image not found")

        if img["uploaded_by"] != user_id:
            raise Forbidden("You may only delete your own review images")

        supabase.storage.from_("review-images").remove(img["file_url"])

        supabase.table("review_images").delete().eq("id", image_id).execute()

        return {"message": "Image deleted successfully"}
