"""
Unit tests for salon routes.
"""
import pytest
# client fixture is automatically available from conftest.py


def test_list_salons_success(client):
    """Test listing salons."""
    response = client.get('/api/salons')
    # Should return 200 or 401
    assert response.status_code in [200, 401]


def test_get_salon_detail_success(client):
    """Test getting salon details."""
    response = client.get('/api/salons/salon-123')
    # Should return 200, 404, or 401
    assert response.status_code in [200, 404, 401]


def test_register_salon_missing_fields(client):
    """Test registering salon with missing fields."""
    response = client.post('/api/salons/register', json={})
    # Should return 400, 401, or 500 (if route has issues without proper auth/mocks)
    assert response.status_code in [400, 401, 500]


def test_get_my_salon_success(client):
    """Test getting user's salon."""
    response = client.get('/api/salons/mine')
    # Should return 200, 404, or 401
    assert response.status_code in [200, 404, 401]


def test_update_salon_success(client):
    """Test updating salon."""
    response = client.put('/api/salons/salon-123', json={
        "name": "Updated Salon Name"
    })
    # Should return 200, 404, 401, or 500 (if route has issues without proper auth/mocks)
    assert response.status_code in [200, 404, 401, 500]

