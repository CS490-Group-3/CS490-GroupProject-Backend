from flask import Blueprint, request, jsonify, g
from middleware.auth import login_required
from middleware.error_logging import auto_log_errors
from flasgger.utils import swag_from
from services.review_response_service import ReviewResponseService
from .reviews import reviews_bp


@reviews_bp.post("/<review_id>/response")
@auto_log_errors
@login_required()
@swag_from("../docs/review_response_create.yml")
def respond_to_review(review_id):
    body = request.json
    result = ReviewResponseService.create_response(
        user_id=g.user["sub"],
        review_id=review_id,
        message=body["message"]
    )
    return jsonify(result), 201


@reviews_bp.delete("/response/<response_id>")
@auto_log_errors
@login_required()
@swag_from("../docs/review_response_delete.yml")
def delete_response(response_id):
    result = ReviewResponseService.delete_response(g.user["sub"], response_id)
    return jsonify(result), 200

