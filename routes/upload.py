from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
from services.upload_file import StorageService
from middleware.auth import login_required  
from flasgger.utils import swag_from

upload_bp = Blueprint("upload", __name__, url_prefix="/api/uploads")

@upload_bp.route("/<file_type>", methods=["POST"])
@login_required()
@swag_from("../docs/upload_file.yml")
def upload_file(file_type):
    try:
        user_id = g.user["sub"]
        salon_id = request.form.get("salon_id")
        file = request.files.get("file")

        if file_type not in ["logo", "license"]:
            return jsonify({"error": "Invalid file type"}), 400
        if not file or not salon_id:
            return jsonify({"error": "Missing file or salon_id"}), 400

        file.filename = secure_filename(file.filename)
        url = StorageService.upload_file(file, salon_id, file_type)

        return jsonify({
            "message": "File uploaded successfully",
            "url": url,
            "file_type": file_type
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@upload_bp.route("/refresh", methods=["POST"])
@login_required()
@swag_from("../docs/upload_refresh.yml")
def refresh_signed_url():
    try:
        data = request.get_json() or {}
        filepath = data.get("filepath")

        if not filepath:
            return jsonify({"error": "Missing 'filepath'"}), 400

        new_url = StorageService.regenerate_signed_url(filepath)
        return jsonify({
            "message": "Signed URL refreshed successfully",
            "signed_url": new_url
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

