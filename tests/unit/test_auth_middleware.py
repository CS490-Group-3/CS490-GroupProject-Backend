"""
Unit tests for authentication middleware.
Tests JWT verification and role-based access control decorators.
"""
import pytest
import jwt
from datetime import datetime, timedelta
from flask import Flask, g, jsonify
from middleware.auth import verify_jwt_token, get_current_user, login_required, role_required


# Test JWT secret (must match the one used in middleware)
TEST_JWT_SECRET = "test-secret-key"


@pytest.fixture
def app():
    """Create test Flask app."""
    import os
    os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
    
    app = Flask(__name__)
    app.config["TESTING"] = True
    
    @app.route('/public')
    def public_route():
        return jsonify({"message": "public"})
    
    @app.route('/protected')
    @login_required()
    def protected_route():
        user = get_current_user()
        return jsonify({"user": user})
    
    @app.route('/admin-only')
    @role_required(['admin'])
    def admin_route():
        return jsonify({"message": "admin access"})
    
    @app.route('/owner-or-admin')
    @role_required(['salon_owner', 'admin'])
    def owner_admin_route():
        return jsonify({"message": "owner or admin access"})
    
    return app


def create_test_token(user_id="user-123", role="customer", expires_delta=None):
    """Helper to create valid test JWT tokens."""
    if expires_delta is None:
        expires_delta = timedelta(hours=1)
    
    exp = datetime.utcnow() + expires_delta
    iat = datetime.utcnow()
    
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "exp": exp,
        "iat": iat,
        "aud": "authenticated",
        "user_metadata": {
            "role": role,
            "first_name": "Test",
            "last_name": "User"
        },
        "app_metadata": {
            "role": role
        }
    }
    
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def test_verify_jwt_token_success(monkeypatch):
    """Test successful JWT token verification."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    # Reimport after setting env var
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    from middleware.auth import verify_jwt_token
    
    token = create_test_token()
    decoded = verify_jwt_token(token)
    
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@example.com"
    assert decoded.get("user_metadata", {}).get("role") == "customer" or decoded.get("app_metadata", {}).get("role") == "customer"


def test_verify_jwt_token_expired(monkeypatch):
    """Test JWT verification with expired token."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    from middleware.auth import verify_jwt_token
    
    # Create expired token
    token = create_test_token(expires_delta=timedelta(seconds=-10))
    
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_jwt_token(token)


def test_verify_jwt_token_invalid_signature(monkeypatch):
    """Test JWT verification with invalid signature."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    from middleware.auth import verify_jwt_token
    
    # Create token with wrong secret
    wrong_secret = "wrong-secret"
    token = jwt.encode(
        {"sub": "user-123", "exp": datetime.utcnow() + timedelta(hours=1)},
        wrong_secret,
        algorithm="HS256"
    )
    
    with pytest.raises(jwt.InvalidTokenError):
        verify_jwt_token(token)


def test_login_required_decorator_success(app, monkeypatch):
    """Test login_required decorator with valid token."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    # Mock AuthService to avoid actual Supabase call
    def fake_get_user_from_token(token):
        return {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "customer"
        }, None
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    monkeypatch.setattr("middleware.auth.AuthService.get_user_from_token", 
                       fake_get_user_from_token)
    
    # Need to re-register routes after reloading middleware
    from middleware.auth import login_required, get_current_user
    
    @app.route('/test-protected')
    @login_required()
    def test_route():
        user = get_current_user()
        return jsonify({"user_id": user["sub"]})
    
    client = app.test_client()
    token = create_test_token()
    
    response = client.get('/test-protected',
                         headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200


def test_login_required_decorator_missing_token(app, monkeypatch):
    """Test login_required decorator without token."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    # Re-register route with fresh decorator
    from middleware.auth import login_required, get_current_user
    
    @app.route('/test-missing-token')
    @login_required()
    def test_route():
        return jsonify({"message": "should not reach here"})
    
    client = app.test_client()
    
    response = client.get('/test-missing-token')
    
    assert response.status_code == 401


def test_login_required_decorator_invalid_token(app, monkeypatch):
    """Test login_required decorator with invalid token."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    # Re-register route with fresh decorator
    from middleware.auth import login_required
    
    @app.route('/test-invalid-token')
    @login_required()
    def test_route():
        return jsonify({"message": "should not reach here"})
    
    client = app.test_client()
    
    response = client.get('/test-invalid-token',
                         headers={"Authorization": "Bearer invalid-token"})
    
    assert response.status_code == 401


def test_role_required_decorator_admin_success(app, monkeypatch):
    """Test role_required decorator with admin role."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    def fake_get_user_from_token(token):
        return {
            "sub": "admin-123",
            "email": "admin@example.com",
            "role": "admin"
        }, None
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    monkeypatch.setattr("middleware.auth.AuthService.get_user_from_token",
                       fake_get_user_from_token)
    
    from middleware.auth import role_required
    
    @app.route('/test-admin')
    @role_required(['admin'])
    def test_route():
        return jsonify({"message": "admin access granted"})
    
    client = app.test_client()
    token = create_test_token(user_id="admin-123", role="admin")
    
    response = client.get('/test-admin',
                         headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200


def test_role_required_decorator_insufficient_role(app, monkeypatch):
    """Test role_required decorator with insufficient role."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    def fake_get_user_from_token(token):
        return {
            "sub": "user-123",
            "email": "user@example.com",
            "role": "customer"
        }, None
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    monkeypatch.setattr("middleware.auth.AuthService.get_user_from_token",
                       fake_get_user_from_token)
    
    from middleware.auth import role_required
    
    @app.route('/test-admin-only')
    @role_required(['admin'])
    def test_route():
        return jsonify({"message": "admin only"})
    
    client = app.test_client()
    token = create_test_token(role="customer")
    
    response = client.get('/test-admin-only',
                         headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 403


def test_role_required_multiple_roles(app, monkeypatch):
    """Test role_required with multiple allowed roles."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    def fake_get_user_from_token(token):
        return {
            "sub": "owner-123",
            "email": "owner@example.com",
            "role": "salon_owner"
        }, None
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    monkeypatch.setattr("middleware.auth.AuthService.get_user_from_token",
                       fake_get_user_from_token)
    
    from middleware.auth import role_required
    
    @app.route('/test-multi-role')
    @role_required(['salon_owner', 'admin'])
    def test_route():
        return jsonify({"message": "access granted"})
    
    client = app.test_client()
    token = create_test_token(user_id="owner-123", role="salon_owner")
    
    response = client.get('/test-multi-role',
                         headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200


def test_get_current_user_in_context(app, monkeypatch):
    """Test get_current_user retrieves user from Flask g context."""
    import os
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    
    def fake_get_user_from_token(token):
        return {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "customer",
            "first_name": "John",
            "last_name": "Doe"
        }, None
    
    import importlib
    import middleware.auth
    importlib.reload(middleware.auth)
    
    monkeypatch.setattr("middleware.auth.AuthService.get_user_from_token",
                       fake_get_user_from_token)
    
    from middleware.auth import login_required, get_current_user
    
    @app.route('/test-user-context')
    @login_required()
    def test_route():
        user = get_current_user()
        return jsonify({
            "user_id": user["sub"],
            "email": user["email"],
            "role": user["role"]
        })
    
    client = app.test_client()
    token = create_test_token()
    
    response = client.get('/test-user-context',
                         headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["user_id"] == "user-123"
    assert data["email"] == "test@example.com"

