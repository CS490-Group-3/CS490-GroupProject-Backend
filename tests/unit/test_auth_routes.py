"""
Unit tests for authentication routes.
Tests all auth endpoints with mocked service calls.
"""
import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client."""
    import os
    os.environ.setdefault("FLASK_DEBUG", "false")
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def test_signup_success(client, monkeypatch):
    """Test successful signup endpoint."""
    
    def fake_signup(*args, **kwargs):
        return {
            "user_id": "user-123",
            "email": "test@example.com",
            "role": "customer"
        }, None
    
    monkeypatch.setattr("services.auth_service.AuthService.signup", fake_signup)
    
    response = client.post('/api/auth/signup', json={
        "email": "test@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe"
    })
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert "message" in data
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"


def test_signup_duplicate_email(client, monkeypatch):
    """Test signup with duplicate email."""
    
    def fake_signup(*args, **kwargs):
        return None, "User already registered"
    
    monkeypatch.setattr("services.auth_service.AuthService.signup", fake_signup)
    
    response = client.post('/api/auth/signup', json={
        "email": "existing@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe"
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_signup_validation_error(client):
    """Test signup with missing required fields."""
    
    response = client.post('/api/auth/signup', json={
        "email": "invalid-email",
        # missing password
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_login_success(client, monkeypatch):
    """Test successful login endpoint."""
    
    def fake_login(*args, **kwargs):
        return {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "role": "customer"
            }
        }, None
    
    monkeypatch.setattr("services.auth_service.AuthService.login", fake_login)
    
    response = client.post('/api/auth/login', json={
        "email": "test@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data


def test_login_invalid_credentials(client, monkeypatch):
    """Test login with invalid credentials."""
    
    def fake_login(*args, **kwargs):
        return None, "Invalid email or password"
    
    monkeypatch.setattr("services.auth_service.AuthService.login", fake_login)
    
    response = client.post('/api/auth/login', json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "error" in data


def test_logout_success(client, monkeypatch):
    """Test successful logout endpoint."""
    
    def fake_logout(*args):
        return True, None
    
    monkeypatch.setattr("services.auth_service.AuthService.logout", fake_logout)
    
    response = client.post('/api/auth/logout', 
                           headers={"Authorization": "Bearer token-123"})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "message" in data


def test_logout_missing_token(client):
    """Test logout without token."""
    
    response = client.post('/api/auth/logout')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "error" in data


def test_refresh_token_success(client, monkeypatch):
    """Test successful token refresh."""
    
    def fake_refresh(*args):
        return {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "bearer"
        }, None
    
    monkeypatch.setattr("services.auth_service.AuthService.refresh_token", fake_refresh)
    
    response = client.post('/api/auth/refresh', json={
        "refresh_token": "old-refresh-token"
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_token_missing(client):
    """Test refresh without token."""
    
    response = client.post('/api/auth/refresh', json={})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_refresh_token_invalid(client, monkeypatch):
    """Test refresh with invalid token."""
    
    def fake_refresh(*args):
        return None, "Invalid or expired refresh token"
    
    monkeypatch.setattr("services.auth_service.AuthService.refresh_token", fake_refresh)
    
    response = client.post('/api/auth/refresh', json={
        "refresh_token": "invalid-token"
    })
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "error" in data


def test_password_reset_request_success(client, monkeypatch):
    """Test password reset request."""
    
    def fake_reset(*args):
        return True, None
    
    monkeypatch.setattr("services.auth_service.AuthService.request_password_reset", fake_reset)
    
    response = client.post('/api/auth/password-reset/request', json={
        "email": "test@example.com"
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "message" in data


def test_password_reset_request_missing_email(client):
    """Test password reset request without email."""
    
    response = client.post('/api/auth/password-reset/request', json={})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_password_reset_confirm_success(client, monkeypatch):
    """Test password reset confirmation."""
    
    def fake_reset(*args):
        return True, None
    
    monkeypatch.setattr("services.auth_service.AuthService.reset_password_with_token", fake_reset)
    
    response = client.post('/api/auth/password-reset/confirm', json={
        "access_token": "reset-token",
        "new_password": "newpassword123"
    })
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "message" in data


def test_password_reset_confirm_short_password(client):
    """Test password reset with short password."""
    
    response = client.post('/api/auth/password-reset/confirm', json={
        "access_token": "reset-token",
        "new_password": "short"
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert "8 characters" in data["error"]


def test_password_reset_confirm_missing_token(client):
    """Test password reset without token."""
    
    response = client.post('/api/auth/password-reset/confirm', json={
        "new_password": "newpassword123"
    })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data

