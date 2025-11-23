"""
Customer Image Service for managing customer-uploaded images.
"""
from config import supabase
from services.upload_file import StorageService
from werkzeug.exceptions import BadRequest, Forbidden
from typing import List, Dict
from datetime import timedelta


class CustomerImageService:

    @staticmethod
    def upload_images(user_id: str, salon_id: str = None, files: List = None, captions: List[str] = None):
        """
        Upload customer images.
        
        Args:
            user_id: Customer's user ID
            salon_id: Optional salon ID to associate image with
            files: List of file objects
            captions: Optional list of captions (one per file)
        
        Returns:
            Dict with uploaded images
        """
        if not files:
            raise BadRequest("No files provided")

        if captions and len(captions) != len(files):
            raise BadRequest("Captions count does not match number of files")

        inserted_rows = []

        for idx, file in enumerate(files):
            # Upload to storage
            result = StorageService.upload_customer_image(file, user_id, salon_id)

            # Create database record
            record = {
                "customer_id": user_id,
                "image_url": result["filepath"],  # Store filepath, not signed URL (signed URLs expire)
                "salon_id": salon_id,
                "caption": captions[idx] if captions else None,
            }

            row = (
                supabase.table("customer_images")
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
    def list_images(customer_id: str, salon_id: str = None):
        """
        List customer images.
        
        Args:
            customer_id: Customer's user ID
            salon_id: Optional salon ID to filter by
        
        Returns:
            List of image records with signed URLs
        """
        query = supabase.table("customer_images").select("*").eq("customer_id", customer_id)
        
        if salon_id:
            query = query.eq("salon_id", salon_id)
        
        images = query.order("uploaded_at", desc=True).execute().data

        # Generate signed URLs for each image
        for img in images:
            filepath = img.get("image_url")  # This is actually the filepath
            if filepath:
                try:
                    # Generate fresh signed URL
                    signed = supabase.storage.from_("customer-images").create_signed_url(
                        filepath,
                        int(timedelta(days=7).total_seconds())
                    )
                    if hasattr(signed, "error") and signed.error:
                        img["signed_url"] = None
                    else:
                        img["signed_url"] = signed["signedURL"]
                except Exception:
                    img["signed_url"] = None
            else:
                img["signed_url"] = None

        return images

    @staticmethod
    def delete_image(user_id: str, image_id: str):
        """
        Delete a customer image.
        
        Args:
            user_id: Customer's user ID (for authorization)
            image_id: Image ID to delete
        
        Returns:
            Success message
        """
        # Verify image exists and belongs to user
        image = (
            supabase.table("customer_images")
            .select("*")
            .eq("id", image_id)
            .single()
            .execute()
            .data
        )

        if not image:
            raise BadRequest("Image not found")

        if image["customer_id"] != user_id:
            raise Forbidden("You can only delete your own images")

        # Delete from database
        supabase.table("customer_images").delete().eq("id", image_id).execute()

        return {"message": "Image deleted successfully"}

