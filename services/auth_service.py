"""
Authentication service using Supabase Auth.
Handles user signup, login, profile management.
"""
from config import supabase
from typing import Dict, Optional, Tuple
from gotrue.errors import AuthApiError
from services.error_logging_service import ErrorLoggingService
from services.audit_logging_service import AuditLoggingService
import json

class AuthService:
        
    @staticmethod
    def signup(
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str,
        phone: Optional[str] = None,
        role: str = 'customer'
    ) -> Tuple[Dict, Optional[str]]:
        """
        Create a new user account with Supabase Auth.
        
        Args:
            email: User's email address
            password: User's password (min 8 characters)
            first_name: User's first name
            last_name: User's last name
            phone: Optional phone number
            role: User role (default: 'customer')
        
        Returns:
            Tuple of (user_data, error_message)
        """
        try:
            # Check if email already exists in user_details table
            existing_user = supabase.table('user_details')\
                .select('id, email')\
                .eq('email', email)\
                .execute()
            
            if existing_user.data and len(existing_user.data) > 0:
                return None, "Email already registered. Please use a different email or try logging in."
            
            # Sign up user with Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                        "role": role
                    }
                }
            })
            
            if response.user:
                return {
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "role": role,
                    "access_token": response.session.access_token if response.session else None,
                    "refresh_token": response.session.refresh_token if response.session else None
                }, None
            else:
                return None, "Failed to create user"
                
        except AuthApiError as e:
            # Check if error is due to duplicate email
            error_message = str(e).lower()
            if 'email' in error_message and ('already' in error_message or 'exists' in error_message or 'registered' in error_message):
                return None, "Email already registered. Please use a different email or try logging in."
            return None, str(e)
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def get_user_profile(user_id: str) -> Optional[Dict]:
        """
        Get user profile from user_details view (includes all profile fields).
        Uses user_details view which combines auth and profile data.
        
        Args:
            user_id: User's UUID
        
        Returns:
            User profile dict or None
        """
        try:
            # Select all profile fields from user_details view
            # Note: user_details is a VIEW that combines auth.users and user_profiles
            # It uses aliased column names (profile_created_at, profile_updated_at)
            # We only select fields needed for the API response
            response = supabase.table('user_details')\
                .select('id, email, first_name, last_name, phone, profile_image_url, date_of_birth, city, state, age_bracket, gender, preferred_services, role')\
                .eq("id", user_id)\
                .execute()

            # response.data is a list of dicts
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                # preferred_services is a jsonb column, so Supabase should auto-deserialize it
                # Handle edge cases: None, malformed data, or ensure it's a list if present
                preferred_services = profile.get('preferred_services')
                if preferred_services is None:
                    # Keep as None (will be serialized as null in JSON)
                    pass
                elif isinstance(preferred_services, list):
                    # Already a list (correct format from jsonb)
                    pass
                elif isinstance(preferred_services, str):
                    # Malformed data stored as string - try to parse or default to empty list
                    try:
                        parsed = json.loads(preferred_services)
                        profile['preferred_services'] = parsed if isinstance(parsed, list) else []
                    except (json.JSONDecodeError, TypeError, ValueError):
                        profile['preferred_services'] = []
                else:
                    # Unexpected type - default to empty list
                    profile['preferred_services'] = []
                return profile
            return None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='medium')
            print("Error fetching user profile:", e)
            return None
    
    @staticmethod
    def login(email: str, password: str) -> Tuple[Dict, Optional[str]]:
        """
        Authenticate user and return session.
        
        Args:
            email: User's email address
            password: User's password
        
        Returns:
            Tuple of (session_data, error_message)
        """
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.session and response.user:
                session= dict(response.session.__dict__)
                user = dict(response.user.__dict__)
                # Get user profile with role
                profile = AuthService.get_user_profile(user.get('id'))
                print("Profile:", profile)
                print("first name", profile.get('first_name', '') if profile else '')
                return {
                    "access_token": session.get('access_token'),
                    "refresh_token": session.get('refresh_token'),
                    "expires_in": session.get('expires_in'),
                    "user": {
                        "id": user.get('id'),
                        "email": user.get('email'),
                        "role": profile.get('role', 'customer') if profile else 'customer',
                        "first_name": profile.get('first_name', ''),
                        "last_name": profile.get('last_name', '')
                    }
                }, None
            else:
                return None, "Invalid credentials"
                
        except AuthApiError as e:
            return None, "Invalid email or password"
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Login failed: {str(e)}"
    
    @staticmethod
    def logout(access_token: str) -> Tuple[bool, Optional[str]]:
        """
        Sign out user and invalidate session.
        
        Args:
            access_token: User's access token
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            supabase.auth.sign_out()
            return True, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
    
    @staticmethod
    def refresh_token(refresh_token: str) -> Tuple[Dict, Optional[str]]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token from login
        
        Returns:
            Tuple of (token_data, error_message)
        """
        try:
            response = supabase.auth.refresh_session(refresh_token)
            
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_in": response.session.expires_in,
                    "token_type": "bearer"
                }, None
            else:
                return None, "Failed to refresh token"
                
        except AuthApiError as e:
            return None, "Invalid or expired refresh token"
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Token refresh failed: {str(e)}"
    
    @staticmethod
    def get_user_from_token(access_token: str) -> Tuple[Dict, Optional[str]]:
        """
        Get user data from access token.
        
        Args:
            access_token: JWT access token
        
        Returns:
            Tuple of (user_data, error_message)
        """
        try:
            response = supabase.auth.get_user(access_token)
            
            if response.user:
                # Get full profile
                profile = AuthService.get_user_profile(response.user.id)
                
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": profile.get('role', 'customer') if profile else 'customer',
                    "first_name": profile.get('first_name', '') if profile else '',
                    "last_name": profile.get('last_name', '') if profile else '',
                    "phone": profile.get('phone') if profile else None,
                    "profile_image_url": profile.get('profile_image_url') if profile else None
                }, None
            else:
                return None, "Invalid or expired token"
                
        except AuthApiError as e:
            return None, "Invalid or expired token"
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def update_user_profile(
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        profile_image_url: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        age_bracket: Optional[str] = None,
        gender: Optional[str] = None,
        preferred_services: Optional[list] = None
    ) -> Tuple[Dict, Optional[str]]:
        """
        Update user profile information.
        
        Args:
            user_id: User's UUID
            first_name: New first name (optional)
            last_name: New last name (optional)
            phone: New phone (optional)
            profile_image_url: New profile image URL (optional)
            date_of_birth: New date of birth (optional)
            city: User's city (optional)
            state: User's state or province (optional)
            age_bracket: User's age bracket (optional)
            gender: User's gender (optional)
            preferred_services: List of preferred service IDs or names (optional)
        
        Returns:
            Tuple of (updated_profile, error_message)
        """
        try:
            # Build update data
            update_data = {}
            if first_name is not None:
                update_data['first_name'] = first_name
            if last_name is not None:
                update_data['last_name'] = last_name
            if phone is not None:
                update_data['phone'] = phone
            if profile_image_url is not None:
                update_data['profile_image_url'] = profile_image_url
            if date_of_birth is not None:
                update_data['date_of_birth'] = date_of_birth
            if city is not None:
                update_data['city'] = city
            if state is not None:
                update_data['state'] = state
            if age_bracket is not None:
                update_data['age_bracket'] = age_bracket
            if gender is not None:
                update_data['gender'] = gender
            if preferred_services is not None:
                # Store as JSON array in database
                update_data['preferred_services'] = json.dumps(preferred_services) if isinstance(preferred_services, list) else preferred_services
            
            if not update_data:
                return None, "No fields to update"
            
            # Get old values for audit log
            old_profile = supabase.table('user_profiles')\
                .select('*')\
                .eq('user_id', user_id)\
                .maybe_single()\
                .execute()
            
            old_values = {}
            if old_profile.data:
                for key in update_data.keys():
                    if key in old_profile.data:
                        old_values[key] = old_profile.data[key]
            
            # Add updated timestamp
            update_data['updated_at'] = 'now()'
            
            # Update user_profiles table directly
            # Note: user_details is a VIEW (not a table), so it cannot be updated directly
            # The view columns are aliased (profile_created_at, profile_updated_at) and it has JOINs
            response = supabase.table('user_profiles')\
                .update(update_data)\
                .eq('user_id', user_id)\
                .execute()
            
            if response.data:
                # Log audit
                AuditLoggingService.log_audit(
                    table_name='user_profiles',
                    record_id=user_id,
                    action='UPDATE',
                    old_values=old_values,
                    new_values=update_data,
                    changed_by=user_id
                )
                return response.data[0], None
            else:
                return None, "Failed to update profile"
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)
    
    @staticmethod
    def update_user_role(user_id: str, new_role: str, admin_user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Update user role (admin only).
        
        Args:
            user_id: Target user's UUID
            new_role: New role to assign
            admin_user_id: Admin user's UUID making the change
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify admin has permission
            admin_profile = AuthService.get_user_profile(admin_user_id)
            if not admin_profile or admin_profile.get('role') != 'admin':
                return False, "Unauthorized: Admin role required"
            
            # Get old role for audit log
            old_profile = supabase.table('user_profiles')\
                .select('role')\
                .eq('user_id', user_id)\
                .maybe_single()\
                .execute()
            
            old_role = old_profile.data.get('role') if old_profile.data else None
            
            # Update role
            response = supabase.table('user_profiles')\
                .update({'role': new_role, 'updated_at': 'now()'})\
                .eq('user_id', user_id)\
                .execute()
            
            if response.data:
                # Log audit (critical operation)
                AuditLoggingService.log_audit(
                    table_name='user_profiles',
                    record_id=user_id,
                    action='UPDATE',
                    old_values={'role': old_role},
                    new_values={'role': new_role},
                    changed_by=admin_user_id
                )
                return True, None
            else:
                return False, "Failed to update role"
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
    
    @staticmethod
    def request_password_reset(email: str) -> Tuple[bool, Optional[str]]:
        """
        Send password reset email.
        
        Args:
            email: User's email address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            supabase.auth.reset_password_email(email)
            return True, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
    
    @staticmethod
    def verify_email(token: str) -> Tuple[bool, Optional[str]]:
        """
        Verify user's email with token.
        
        Args:
            token: Verification token from email
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            response = supabase.auth.verify_otp({
                'token': token,
                'type': 'email'
            })
            return True if response else False, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
    
    @staticmethod
    def update_password(token: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Update user password using reset token.
        
        Args:
            token: Password reset token from email
            new_password: New password to set
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Verify the reset token and update password
            response = supabase.auth.update_user({
                'password': new_password
            })
            
            if response.user:
                return True, None
            else:
                return False, "Failed to update password"
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)
    
    @staticmethod
    def reset_password_with_token(access_token: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Reset password using the access token from password reset email.
        This is called after user clicks the reset link.
        
        Args:
            access_token: Token from password reset email
            new_password: New password to set
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Set the session with the reset token
            supabase.auth.set_session(access_token, access_token)
            
            # Update the password
            response = supabase.auth.update_user({
                'password': new_password
            })
            
            if response.user:
                return True, None
            else:
                return False, "Failed to reset password"
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return False, str(e)

    @staticmethod
    def get_barber_id(user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get barber ID associated with a user ID.
        
        Args:
            user_id: User's UUID
        
        Returns:
            Tuple of (barber_id, error_message)
        """
        try:
            response = supabase.table('barbers')\
                .select('id')\
                .eq('user_id', user_id)\
                .execute()
            
            print("Barber response:", response)
            if response.data:
                return response.data[0]['id'], None
            else:
                return None, "Barber not found for the given user ID"
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, str(e)