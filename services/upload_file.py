import os
import uuid
from config import supabase
from flask import request
from datetime import timedelta



class StorageService:
    @staticmethod
    def upload_file(file, salon_id, file_type):
        """
        Upload file to Supabase Storage and return a signed URL.
        file_type: 'license' or 'logo'
        """
        bucket_map = {
            "license": "salon-documents",
            "logo": "salon-logos"
        }

        # Pick correct bucket or default
        bucket_name = bucket_map.get(file_type, "salon-documents")

        filename = f"{salon_id}/{file_type}/{file.filename}"
        file_bytes = file.read()

        res = supabase.storage.from_(bucket_name).upload(filename, file_bytes)
        if hasattr(res, "error") and res.error:
            raise Exception(res.error.message)

        # Generate signed URL (valid for 7 days)
        signed = supabase.storage.from_(bucket_name).create_signed_url(
            filename,
            int(timedelta(days=7).total_seconds())
        )
        if hasattr(signed, "error") and signed.error:
            raise Exception(signed.error.message)

        return signed["signedURL"]


    @staticmethod
    def regenerate_signed_url(filepath: str, expires_in_days: int = 7):
        try:
            seconds = int(timedelta(days=expires_in_days).total_seconds())
            res = supabase.storage.from_(BUCKET_NAME).create_signed_url(filepath, seconds)

            if hasattr(res, "error") and res.error:
                raise Exception(res.error.message)

            return res["signedURL"]
        except Exception as e:
            raise Exception(f"Failed to regenerate signed URL: {e}")
