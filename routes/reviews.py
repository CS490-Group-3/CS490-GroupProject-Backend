from flask import Blueprint, request, jsonify, g
from middleware.auth import login_required
from flasgger.utils import swag_from
from services.review_service import ReviewService

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")


@reviews_bp.post("/")
@login_required()
@swag_from("../docs/reviews_create.yml")
def create_review():
    body = request.json

    result = ReviewService.create_review(
        user_id=g.user["sub"],
        appointment_id=body["appointment_id"],
        rating=body["rating"],
        title=body.get("title"),
        comment=body.get("comment")
    )

    return jsonify(result), 201


@reviews_bp.get("/<review_id>")
@login_required()
@swag_from("../docs/reviews_get_single.yml")
def get_review(review_id):
    try:
        full = ReviewService.get_full_review(review_id)
        return jsonify(full), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reviews_bp.patch("/<review_id>")
@login_required()
@swag_from("../docs/reviews_update.yml")
def update_review(review_id):
    body = request.json

    updated = ReviewService.update_review(
        user_id=g.user["sub"],
        review_id=review_id,
        rating=body["rating"],
        title=body.get("title"),
        comment=body.get("comment")
    )

    return jsonify(updated), 200


@reviews_bp.delete("/<review_id>")
@login_required()
@swag_from("../docs/reviews_delete.yml")
def delete_review(review_id):
    result = ReviewService.delete_review(g.user["sub"], review_id)
    return jsonify(result), 200


@reviews_bp.get("/salon/<salon_id>")
@login_required()
@swag_from("../docs/reviews_list_salon.yml")
def get_salon_reviews(salon_id):
    reviews = ReviewService.get_reviews_for_salon(salon_id)
    return jsonify(reviews), 200

