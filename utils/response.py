from typing import Any, Dict, Optional, Tuple, Union
from flask import jsonify


JsonDict = Dict[str, Any]
FlaskResponse = Tuple[Any, int]


def success_response(
    data: Optional[Union[JsonDict, list]] = None,
    message: Optional[str] = None,
    status_code: int = 200,
    meta: Optional[JsonDict] = None,
) -> FlaskResponse:
    """
    Build a standardized success API response.
    """
    response: JsonDict = {
        "success": True,
    }
    if message is not None:
        response["message"] = message
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return jsonify(response), status_code


def error_response(
    message: str,
    status_code: int = 400,
    code: Optional[Union[int, str]] = None,
    details: Optional[Any] = None,
) -> FlaskResponse:
    """
    Build a standardized error API response.
    """
    error_obj: JsonDict = {
        "message": message,
    }
    if code is not None:
        error_obj["code"] = code
    if details is not None:
        error_obj["details"] = details
    return jsonify({"success": False, "error": error_obj}), status_code


def paginated_success(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: Optional[str] = None,
    status_code: int = 200,
    extra_meta: Optional[JsonDict] = None,
) -> FlaskResponse:
    """
    Success response with pagination metadata.
    """
    meta: JsonDict = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }
    if extra_meta:
        meta.update(extra_meta)
    return success_response(data=items, message=message, status_code=status_code, meta=meta)


