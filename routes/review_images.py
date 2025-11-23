from flask import Blueprint, request, jsonify, g
from middleware.auth import login_required
from flasgger.utils import swag_from
from services.review_image_service import ReviewImageService
from .reviews import reviews_bp


@reviews_bp.post("/<review_id>/images")
@login_required()
@swag_from("../docs/reviews_upload_image.yml")
def upload_review_image(review_id):
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "Missing files"}), 400

        labels = request.form.getlist("labels") or None

        user_id = g.user["sub"]

        rows = ReviewImageService.upload_images(user_id, review_id, files, labels)
        return jsonify(rows), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reviews_bp.get("/<review_id>/images")
@swag_from("../docs/reviews_list_images.yml")
def list_review_images(review_id):
    try:
        images = ReviewImageService.list_images(review_id)
        return jsonify(images), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reviews_bp.delete("/images/<image_id>")
@login_required()
@swag_from("../docs/reviews_delete_image.yml")
def delete_review_image(image_id):
    try:
        user_id = g.user["sub"]
        result = ReviewImageService.delete_image(user_id, image_id)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
