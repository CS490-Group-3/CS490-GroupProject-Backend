from config import supabase
from services.upload_file import StorageService
from werkzeug.exceptions import BadRequest, Forbidden, NotFound


class ReviewImageService:

    @staticmethod
    def upload_images(user_id, review_id, files, labels=None):
        # 1. Validate review exists
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

        # 2. Optional labels (before, after, etc.)
        if labels and len(labels) != len(files):
            raise BadRequest("Labels count does not match number of files")

        inserted_rows = []

        for idx, file in enumerate(files):
            result = StorageService.upload_review_image(file, review_id, user_id)

            record = {
                "review_id": review_id,
                "file_url": result["filepath"],
                "uploaded_by": user_id,
                "label": labels[idx] if labels else None,
            }

            row = (
                supabase.table("review_images")
                .insert(record)
                .execute()
                .data[0]
            )

            row["signed_url"] = result["signed_url"]
            inserted_rows.append(row)

        return {
            "message": "Images uploaded successfully",
            "count": len(inserted_rows),
            "images": inserted_rows
        }


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

