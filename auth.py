import os
from functools import wraps
from flask import Flask, request, jsonify, g
import jwt 

# CONFIG: read JWT secret from environment
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
ISSUER = os.environ.get("SUPABASE_URL")
app = Flask(__name__)

def verify_supabase_jwt(token: str):
    """
    Verifies HS256-signed Supabase JWT.
    Returns the decoded payload on success, or raises jwt exceptions on failure.
    """
    options = {
        "require": ["exp", "iat", "sub"],  # require these claims
        "verify_exp": True,
    }

    decoded = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options=options,
        # audience="authenticated"
        # issuer=ISSUER
    )
    return decoded

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = verify_supabase_jwt(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": "Invalid token", "detail": str(e)}), 401

        g.user = {
            "sub": payload.get("sub"),
            "email": payload.get("email"),
            "claims": payload,
        }

        return f(*args, **kwargs)

    return decorated