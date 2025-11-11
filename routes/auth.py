"""
Authentication routes using Supabase Auth.
"""
from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from models.user import (
    UserSignupRequest, 
    UserLoginRequest, 
    UserProfileUpdate,
    UserRoleUpdate
)
from services.auth_service import AuthService
from middleware import login_required, role_required, get_current_user
from utils.response import success_response, error_response

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User signup endpoint.
    Creates new user via Supabase Auth and profile in user_profiles.
    """
    try:
        # Validate request data
        data = UserSignupRequest(**request.get_json())
        
        # Call auth service
        result, error = AuthService.signup(
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=data.role
        )
        
        if error:
            return error_response(message=error, status_code=400, code="signup_failed")
        
        return success_response(
            message="User created successfully. Please check your email to verify your account.",
            data={"user": result},
            status_code=201
        )
        
    except ValidationError as e:
        return error_response(message="Validation failed", status_code=400, code="validation_error", details=e.errors())
    except Exception as e:
        return error_response(message="Internal server error", status_code=500, code="internal_error")


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login endpoint.
    Returns JWT access token and user data.
    """
    try:
        # Validate request data
        data = UserLoginRequest(**request.get_json())
        
        # Call auth service
        result, error = AuthService.login(data.email, data.password)
        
        if error:
            return error_response(message=error, status_code=401, code="invalid_credentials")
        
        return success_response(
            message="Login successful",
            data={
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "expires_in": result["expires_in"],
                "user": result["user"]
            },
            status_code=200
        )
        
    except ValidationError as e:
        return error_response(message="Validation failed", status_code=400, code="validation_error", details=e.errors())
    except Exception:
        return error_response(message="Login failed", status_code=500, code="internal_error")


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    User logout endpoint.
    Invalidates current session.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response(message="Missing or invalid token", status_code=401, code="unauthorized")
        
        token = auth_header.split(' ')[1]
        
        # Call auth service
        success, error = AuthService.logout(token)
        
        if error:
            return error_response(message=error, status_code=500, code="logout_failed")
        
        return success_response(message="Logged out successfully", status_code=200)
        
    except Exception:
        return error_response(message="Logout failed", status_code=500, code="internal_error")


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token.
    
    Body:
    {
        "refresh_token": "refresh_token_string"
    }
    """
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return error_response(message="Refresh token is required", status_code=400, code="validation_error")
        
        # Call auth service
        result, error = AuthService.refresh_token(refresh_token)
        
        if error:
            return error_response(message=error, status_code=401, code="invalid_refresh_token")
        
        return success_response(
            message="Token refreshed successfully",
            data={
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "expires_in": result["expires_in"],
                "token_type": result["token_type"],
            },
            status_code=200
        )
        
    except Exception:
        return error_response(message="Token refresh failed", status_code=500, code="internal_error")


@auth_bp.route('/me', methods=['GET'])
@login_required()
def get_current_user_route():
    """
    Get current authenticated user's data.
    """
    try:
        user = get_current_user()
        return success_response(data={"user": user}, status_code=200)
    except Exception:
        return error_response(message="Failed to fetch user", status_code=500, code="internal_error")


@auth_bp.route('/profile', methods=['PUT'])
@login_required()
def update_profile():
    """
    Update current user's profile.
    """
    try:
        user = get_current_user()
        
        # Validate request data
        data = UserProfileUpdate(**request.get_json())
        
        # Update profile
        updated_profile, error = AuthService.update_user_profile(
            user_id=user['sub'],
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            profile_image_url=data.profile_image_url,
            date_of_birth=str(data.date_of_birth) if data.date_of_birth else None
        )
        
        if error:
            return error_response(message=error, status_code=400, code="profile_update_failed")
        
        return success_response(
            message="Profile updated successfully",
            data={"profile": updated_profile},
            status_code=200
        )
        
    except ValidationError as e:
        return error_response(message="Validation failed", status_code=400, code="validation_error", details=e.errors())
    except Exception:
        return error_response(message="Internal server error", status_code=500, code="internal_error")


@auth_bp.route('/users/<user_id>/role', methods=['PUT'])
@role_required(['admin'], verify_with_supabase=True)
def update_user_role(user_id: str):
    """
    Update user role (admin only).
    """
    try:
        admin_user = get_current_user()
        
        # Validate request data
        data = UserRoleUpdate(**request.get_json())
        
        # Update role
        success, error = AuthService.update_user_role(
            user_id=user_id,
            new_role=data.role,
            admin_user_id=admin_user['sub']
        )
        
        if error:
            return error_response(message=error, status_code=400, code="role_update_failed")
        
        return success_response(message="Role updated successfully", status_code=200)
        
    except ValidationError as e:
        return error_response(message="Validation failed", status_code=400, code="validation_error", details=e.errors())
    except Exception:
        return error_response(message="Internal server error", status_code=500, code="internal_error")


@auth_bp.route('/password-reset/request', methods=['POST'])
def request_password_reset():
    """
    Request password reset email.
    """
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return error_response(message="Email is required", status_code=400, code="validation_error")
        
        success, error = AuthService.request_password_reset(email)
        
        # Always return success to prevent email enumeration
        return success_response(
            message="If an account exists with that email, a password reset link has been sent.",
            status_code=200
        )
        
    except Exception:
        return error_response(message="Failed to process request", status_code=500, code="internal_error")


@auth_bp.route('/password-reset/confirm', methods=['POST'])
def reset_password_confirm():
    """
    Complete password reset with token from email.
    
    Body:
    {
        "access_token": "token_from_reset_email",
        "new_password": "new_password"
    }
    """
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        new_password = data.get('new_password')
        
        if not access_token:
            return error_response(message="Reset token is required", status_code=400, code="validation_error")
        
        if not new_password:
            return error_response(message="New password is required", status_code=400, code="validation_error")
        
        if len(new_password) < 8:
            return error_response(message="Password must be at least 8 characters", status_code=400, code="validation_error")
        
        # Reset password with token
        success, error = AuthService.reset_password_with_token(access_token, new_password)
        
        if error:
            return error_response(message=error, status_code=400, code="reset_failed")
        
        return success_response(
            message="Password reset successfully. You can now log in with your new password.",
            status_code=200
        )
        
    except Exception:
        return error_response(message="Failed to reset password", status_code=500, code="internal_error")


@auth_bp.route('/password/change', methods=['PUT'])
@login_required()
def change_password():
    """
    Change password for authenticated user.
    
    Body:
    {
        "new_password": "new_password"
    }
    """
    try:
        user = get_current_user()
        data = request.get_json()
        new_password = data.get('new_password')
        
        if not new_password:
            return error_response(message="New password is required", status_code=400, code="validation_error")
        
        if len(new_password) < 8:
            return error_response(message="Password must be at least 8 characters", status_code=400, code="validation_error")
        
        # Get the actual token to update password
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        success, error = AuthService.update_password(token, new_password)
        
        if error:
            return error_response(message=error, status_code=400, code="password_change_failed")
        
        return success_response(message="Password changed successfully", status_code=200)
        
    except Exception:
        return error_response(message="Internal server error", status_code=500, code="internal_error")

