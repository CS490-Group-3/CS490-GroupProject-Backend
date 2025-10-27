"""
Authentication middleware and decorators.
Provides @login_required and @role_required decorators for protecting routes.
"""
from functools import wraps
from flask import request, jsonify, g
import jwt
import os
from typing import List, Optional
from services.auth_service import AuthService

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_JWT_SECRET:
    raise ValueError("SUPABASE_JWT_SECRET must be set in environment variables")


def verify_jwt_token(token: str) -> dict:
    """
    Verify JWT token locally (fast verification).
    
    Args:
        token: JWT access token
    
    Returns:
        Decoded JWT payload
    
    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    options = {
        "require": ["exp", "iat", "sub"],
        "verify_exp": True,
    }
    
    decoded = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options=options,
        audience="authenticated"
    )
    
    return decoded


def get_current_user() -> Optional[dict]:
    """
    Get current authenticated user from Flask's g object.
    
    Returns:
        User dict or None if not authenticated
    """
    return getattr(g, 'user', None)


def login_required(verify_with_supabase: bool = False):
    """
    Decorator to protect routes that require authentication.
    
    Args:
        verify_with_supabase: If True, verify token with Supabase API (slower but more secure)
    
    Usage:
        @app.route('/protected')
        @login_required()
        def protected_route():
            user = get_current_user()
            return jsonify({"user_id": user['sub']})
    
        @app.route('/critical')
        @login_required(verify_with_supabase=True)
        def critical_route():
            # For critical operations, verify with Supabase
            return jsonify({"message": "success"})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get("Authorization", "")
            
            if not auth_header.startswith("Bearer "):
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Missing or invalid Authorization header"
                }), 401
            
            token = auth_header.split(" ", 1)[1].strip()
            
            try:
                # Fast local JWT verification
                payload = verify_jwt_token(token)
                
                # For critical operations, verify with Supabase API
                if verify_with_supabase:
                    user_data, error = AuthService.get_user_from_token(token)
                    if error:
                        return jsonify({
                            "error": "Unauthorized",
                            "message": "Invalid or expired token"
                        }), 401
                    
                    # Use full user data from Supabase
                    g.user = user_data
                else:
                    # Use JWT payload for faster verification
                    user_metadata = payload.get('user_metadata', {})
                    app_metadata = payload.get('app_metadata', {})
                    
                    g.user = {
                        "sub": payload.get("sub"),  # User ID
                        "email": payload.get("email"),
                        "role": user_metadata.get("role") or app_metadata.get("role", "customer"),
                        "first_name": user_metadata.get("first_name", ""),
                        "last_name": user_metadata.get("last_name", ""),
                        "phone": user_metadata.get("phone"),
                        "claims": payload
                    }
                
                return f(*args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Token has expired"
                }), 401
            except jwt.InvalidTokenError as e:
                return jsonify({
                    "error": "Unauthorized",
                    "message": f"Invalid token: {str(e)}"
                }), 401
            except Exception as e:
                return jsonify({
                    "error": "Internal Server Error",
                    "message": str(e)
                }), 500
        
        return decorated_function
    return decorator


def role_required(allowed_roles: List[str], verify_with_supabase: bool = False):
    """
    Decorator to protect routes that require specific roles.
    
    Args:
        allowed_roles: List of roles that can access this route
        verify_with_supabase: If True, verify token with Supabase API
    
    Usage:
        @app.route('/admin')
        @role_required(['admin'])
        def admin_only():
            return jsonify({"message": "Admin access"})
        
        @app.route('/salon-management')
        @role_required(['admin', 'salon_owner'])
        def salon_management():
            return jsonify({"message": "Salon management"})
    """
    def decorator(f):
        @wraps(f)
        @login_required(verify_with_supabase=verify_with_supabase)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            if not user:
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Authentication required"
                }), 401
            
            user_role = user.get('role', 'customer')
            
            if user_role not in allowed_roles:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"This endpoint requires one of the following roles: {', '.join(allowed_roles)}"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def admin_required(verify_with_supabase: bool = False):
    """
    Convenience decorator for admin-only routes.
    Equivalent to @role_required(['admin'])
    
    """
    return role_required(['admin'], verify_with_supabase=verify_with_supabase)

