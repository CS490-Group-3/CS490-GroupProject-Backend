"""
Unit tests for AuthService.
Tests all authentication service methods with mocked Supabase interactions.
"""
import pytest
from services.auth_service import AuthService
from gotrue.errors import AuthApiError


def test_signup_success(monkeypatch):
    """Test successful user signup."""
    
    # Mock Supabase auth.sign_up response
    class MockUser:
        id = "user-123"
        email = "test@example.com"
    
    class MockSession:
        access_token = "access-token-123"
        refresh_token = "refresh-token-123"
    
    class MockResponse:
        user = MockUser()
        session = MockSession()
    
    def fake_sign_up(data):
        return MockResponse()
    
    monkeypatch.setattr("config.supabase.auth.sign_up", fake_sign_up)
    
    # Test signup
    result, error = AuthService.signup(
        email="test@example.com",
        password="password123",
        first_name="John",
        last_name="Doe",
        phone="555-1234",
        role="customer"
    )
    
    # Verify result
    assert error is None
    assert result is not None
    assert result["user_id"] == "user-123"
    assert result["email"] == "test@example.com"
    assert result["role"] == "customer"
    assert result["access_token"] == "access-token-123"
    assert result["refresh_token"] == "refresh-token-123"


def test_signup_duplicate_email(monkeypatch):
    """Test signup with duplicate email."""
    
    def fake_sign_up(data):
        raise AuthApiError("User already registered", status=400, code="user_already_registered")
    
    monkeypatch.setattr("config.supabase.auth.sign_up", fake_sign_up)
    
    result, error = AuthService.signup(
        email="existing@example.com",
        password="password123",
        first_name="John",
        last_name="Doe"
    )
    
    assert result is None
    assert error is not None
    assert "already registered" in error or "User already registered" in error


def test_login_success(monkeypatch):
    """Test successful user login."""
    
    class MockUser:
        id = "user-123"
        email = "test@example.com"
        __dict__ = {"id": "user-123", "email": "test@example.com"}
    
    class MockSession:
        access_token = "access-token-123"
        refresh_token = "refresh-token-123"
        expires_in = 3600
        __dict__ = {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600
        }
    
    class MockAuthResponse:
        user = MockUser()
        session = MockSession()
    
    def fake_sign_in(data):
        return MockAuthResponse()
    
    # Mock profile retrieval
    def fake_get_user_profile(user_id):
        return {
            "id": "user-123",
            "role": "customer",
            "first_name": "John",
            "last_name": "Doe"
        }
    
    monkeypatch.setattr("config.supabase.auth.sign_in_with_password", fake_sign_in)
    monkeypatch.setattr(AuthService, "get_user_profile", fake_get_user_profile)
    
    result, error = AuthService.login("test@example.com", "password123")
    
    assert error is None
    assert result is not None
    assert result["access_token"] == "access-token-123"
    assert result["refresh_token"] == "refresh-token-123"
    assert result["expires_in"] == 3600
    assert result["user"]["id"] == "user-123"
    assert result["user"]["email"] == "test@example.com"
    assert result["user"]["role"] == "customer"


def test_login_invalid_credentials(monkeypatch):
    """Test login with invalid credentials."""
    
    def fake_sign_in(data):
        raise AuthApiError("Invalid login credentials", status=401, code="invalid_credentials")
    
    monkeypatch.setattr("config.supabase.auth.sign_in_with_password", fake_sign_in)
    
    result, error = AuthService.login("test@example.com", "wrongpassword")
    
    assert result is None
    assert error is not None
    assert "Invalid" in error


def test_logout_success(monkeypatch):
    """Test successful logout."""
    
    def fake_sign_out():
        pass
    
    monkeypatch.setattr("config.supabase.auth.sign_out", fake_sign_out)
    
    success, error = AuthService.logout("some-token")
    
    assert success is True
    assert error is None


def test_refresh_token_success(monkeypatch):
    """Test successful token refresh."""
    
    class MockSession:
        access_token = "new-access-token"
        refresh_token = "new-refresh-token"
        expires_in = 3600
    
    class MockResponse:
        session = MockSession()
    
    def fake_refresh(refresh_token):
        return MockResponse()
    
    monkeypatch.setattr("config.supabase.auth.refresh_session", fake_refresh)
    
    result, error = AuthService.refresh_token("old-refresh-token")
    
    assert error is None
    assert result is not None
    assert result["access_token"] == "new-access-token"
    assert result["refresh_token"] == "new-refresh-token"
    assert result["expires_in"] == 3600
    assert result["token_type"] == "bearer"


def test_refresh_token_invalid(monkeypatch):
    """Test refresh with invalid token."""
    
    def fake_refresh(refresh_token):
        raise AuthApiError("Invalid refresh token", status=401, code="invalid_refresh_token")
    
    monkeypatch.setattr("config.supabase.auth.refresh_session", fake_refresh)
    
    result, error = AuthService.refresh_token("invalid-token")
    
    assert result is None
    assert error is not None
    assert "Invalid" in error or "expired" in error


def test_get_user_from_token_success(monkeypatch):
    """Test getting user data from access token."""
    
    class MockUser:
        id = "user-123"
        email = "test@example.com"
    
    class MockResponse:
        user = MockUser()
    
    def fake_get_user(token):
        return MockResponse()
    
    def fake_get_profile(user_id):
        return {
            "role": "customer",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "555-1234",
            "profile_image_url": None
        }
    
    monkeypatch.setattr("config.supabase.auth.get_user", fake_get_user)
    monkeypatch.setattr(AuthService, "get_user_profile", fake_get_profile)
    
    result, error = AuthService.get_user_from_token("valid-token")
    
    assert error is None
    assert result is not None
    assert result["id"] == "user-123"
    assert result["email"] == "test@example.com"
    assert result["role"] == "customer"


def test_get_user_profile_success(monkeypatch):
    """Test retrieving user profile."""
    
    class MockResponse:
        data = [{
            "id": "user-123",
            "first_name": "John",
            "last_name": "Doe",
            "role": "customer",
            "phone": "555-1234"
        }]
    
    class MockChain:
        def select(self, *args):
            return self
        
        def eq(self, *args):
            return self
        
        def execute(self):
            return MockResponse()
    
    def fake_table(name):
        return MockChain()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    profile = AuthService.get_user_profile("user-123")
    
    assert profile is not None
    assert profile["id"] == "user-123"
    assert profile["first_name"] == "John"
    assert profile["role"] == "customer"


def test_update_user_profile_success(monkeypatch):
    """Test updating user profile."""
    
    class MockUpdateResponse:
        data = [{
            "user_id": "user-123",
            "first_name": "Jane",
            "last_name": "Smith",
            "phone": "555-9999"
        }]
    
    class MockOldProfileResponse:
        data = {
            "user_id": "user-123",
            "first_name": "John",
            "last_name": "Doe"
        }
    
    class MockUpdatedProfileResponse:
        data = [{
            "id": "user-123",
            "email": "test@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "phone": "555-9999",
            "role": "customer"
        }]
    
    call_count = [0]
    
    class MockChain:
        def __init__(self, table_name):
            self.table_name = table_name
            self._is_select = False
            self._is_update = False
            self._is_maybe_single = False
        
        def select(self, *args):
            self._is_select = True
            return self
        
        def update(self, data):
            self._is_update = True
            self.update_data = data
            return self
        
        def eq(self, *args):
            return self
        
        def maybe_single(self):
            self._is_maybe_single = True
            return self
        
        def execute(self):
            from unittest.mock import Mock
            call_count[0] += 1
            mock_response = Mock()
            mock_response.error = None
            
            if self.table_name == "user_profiles":
                if self._is_select and self._is_maybe_single:
                    # First call: get old values
                    mock_response.data = MockOldProfileResponse().data
                elif self._is_update:
                    # Second call: update
                    mock_response.data = MockUpdateResponse().data
            elif self.table_name == "user_details":
                # Third call: get_user_profile after update
                mock_response.data = MockUpdatedProfileResponse().data
            
            return mock_response
    
    def fake_table(name):
        return MockChain(name)
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result, error = AuthService.update_user_profile(
        user_id="user-123",
        first_name="Jane",
        last_name="Smith",
        phone="555-9999"
    )
    
    assert error is None
    assert result is not None
    assert result["first_name"] == "Jane"
    assert result["last_name"] == "Smith"


def test_update_user_profile_no_fields(monkeypatch):
    """Test updating profile with no fields."""
    
    result, error = AuthService.update_user_profile(user_id="user-123")
    
    assert result is None
    assert error == "No fields to update"


def test_update_user_role_success(monkeypatch):
    """Test updating user role as admin."""
    
    def fake_get_profile(user_id):
        if user_id == "admin-123":
            return {"id": "admin-123", "role": "admin"}
        return {"id": "user-123", "role": "customer"}
    
    class MockUpdateResponse:
        data = [{"user_id": "user-123", "role": "salon_owner"}]
    
    class MockOldProfileResponse:
        data = {"user_id": "user-123", "role": "customer"}
    
    class MockChain:
        def __init__(self):
            self._is_select = False
        
        def select(self, *args):
            self._is_select = True
            return self
        
        def update(self, data):
            return self
        
        def eq(self, *args):
            return self
        
        def maybe_single(self):
            return self
        
        def execute(self):
            if self._is_select:
                return MockOldProfileResponse()
            return MockUpdateResponse()
    
    def fake_table(name):
        return MockChain()
    
    monkeypatch.setattr(AuthService, "get_user_profile", fake_get_profile)
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    success, error = AuthService.update_user_role(
        user_id="user-123",
        new_role="salon_owner",
        admin_user_id="admin-123"
    )
    
    assert success is True
    assert error is None


def test_update_user_role_unauthorized(monkeypatch):
    """Test updating user role as non-admin."""
    
    def fake_get_profile(user_id):
        return {"role": "customer"}
    
    monkeypatch.setattr(AuthService, "get_user_profile", fake_get_profile)
    
    success, error = AuthService.update_user_role(
        user_id="user-123",
        new_role="admin",
        admin_user_id="not-admin"
    )
    
    assert success is False
    assert "Unauthorized" in error


def test_request_password_reset_success(monkeypatch):
    """Test password reset request."""
    
    def fake_reset_email(email, redirect_to_dict=None):
        # Accept both email and redirect_to_dict to match actual implementation
        # Implementation calls: supabase.auth.reset_password_email(email, {"redirect_to": redirect_to})
        pass
    
    monkeypatch.setattr("config.supabase.auth.reset_password_email", fake_reset_email)
    
    success, error = AuthService.request_password_reset("test@example.com")
    
    assert success is True
    assert error is None


def test_reset_password_with_token_success(monkeypatch):
    """Test password reset with token."""
    
    class MockUser:
        id = "user-123"
    
    class MockResponse:
        user = MockUser()
    
    def fake_set_session(access_token, refresh_token):
        pass
    
    def fake_update_user(data):
        return MockResponse()
    
    monkeypatch.setattr("config.supabase.auth.set_session", fake_set_session)
    monkeypatch.setattr("config.supabase.auth.update_user", fake_update_user)
    
    success, error = AuthService.reset_password_with_token(
        access_token="reset-token",
        new_password="newpassword123"
    )
    
    assert success is True
    assert error is None


def test_get_barber_id_success(monkeypatch):
    """Test getting barber ID for a user."""
    
    class MockResponse:
        data = [{"id": "barber-456"}]
    
    class MockChain:
        def select(self, *args):
            return self
        
        def eq(self, *args):
            return self
        
        def limit(self, *args):
            return self
        
        def execute(self):
            return MockResponse()
    
    def fake_table(name):
        return MockChain()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    barber_id, error = AuthService.get_barber_id("user-123")
    
    assert error is None
    assert barber_id == "barber-456"


def test_get_barber_id_not_found(monkeypatch):
    """Test getting barber ID when user is not a barber."""
    
    class MockResponse:
        data = []
    
    class MockChain:
        def select(self, *args):
            return self
        
        def eq(self, *args):
            return self
        
        def limit(self, *args):
            return self
        
        def execute(self):
            return MockResponse()
    
    def fake_table(name):
        return MockChain()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    barber_id, error = AuthService.get_barber_id("user-123")
    
    assert barber_id is None
    assert "not found" in error

