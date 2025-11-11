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
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "User created successfully. Please check your email to verify your account.",
            "user": result
        }), 201
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            return jsonify({"error": error}), 401
        
        return jsonify({
            "message": "Login successful",
            "access_token": result['access_token'],
            "refresh_token": result['refresh_token'],
            "expires_in": result['expires_in'],
            "user": result['user']
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": "Login failed"}), 500


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
            return jsonify({"error": "Missing or invalid token"}), 401
        
        token = auth_header.split(' ')[1]
        
        # Call auth service
        success, error = AuthService.logout(token)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({"message": "Logged out successfully"}), 200
        
    except Exception as e:
        return jsonify({"error": "Logout failed"}), 500


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
            return jsonify({"error": "Refresh token is required"}), 400
        
        # Call auth service
        result, error = AuthService.refresh_token(refresh_token)
        
        if error:
            return jsonify({"error": error}), 401
        
        return jsonify({
            "message": "Token refreshed successfully",
            "access_token": result['access_token'],
            "refresh_token": result['refresh_token'],
            "expires_in": result['expires_in'],
            "token_type": result['token_type']
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Token refresh failed"}), 500


@auth_bp.route('/me', methods=['GET'])
@login_required()
def get_current_user_route():
    """
    Get current authenticated user's data.
    """
    try:
        user = get_current_user()
        return jsonify({"user": user}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Profile updated successfully",
            "profile": updated_profile
        }), 200
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            return jsonify({"error": error}), 400
        
        return jsonify({"message": "Role updated successfully"}), 200
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/password-reset/request', methods=['POST'])
def request_password_reset():
    """
    Request password reset email.
    """
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({"error": "Email is required"}), 400
        
        success, error = AuthService.request_password_reset(email)
        
        # Always return success to prevent email enumeration
        return jsonify({
            "message": "If an account exists with that email, a password reset link has been sent."
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to process request"}), 500


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
            return jsonify({"error": "Reset token is required"}), 400
        
        if not new_password:
            return jsonify({"error": "New password is required"}), 400
        
        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        
        # Reset password with token
        success, error = AuthService.reset_password_with_token(access_token, new_password)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Password reset successfully. You can now log in with your new password."
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to reset password"}), 500


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
            return jsonify({"error": "New password is required"}), 400
        
        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        
        # Get the actual token to update password
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        success, error = AuthService.update_password(token, new_password)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "message": "Password changed successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

