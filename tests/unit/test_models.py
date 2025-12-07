"""
Unit tests for Pydantic models.
Tests model validation and serialization.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError
from models.appointment import (
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    AppointmentResponse
)
from models.salon import SalonRegisterRequest
from models.products import (
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductCategoryCreateRequest
)


def test_appointment_create_request_valid():
    """Test valid appointment creation request."""
    # end_at is required in the model, even though comment says optional
    request = AppointmentCreateRequest(
        barber_id="barber-1",
        service_id="service-1",
        salon_id="salon-1",
        start_at=datetime(2024, 1, 15, 10, 0, 0),
        end_at=datetime(2024, 1, 15, 11, 0, 0)  # Required field
    )
    
    assert request.barber_id == "barber-1"
    assert request.service_id == "service-1"
    assert request.start_at == datetime(2024, 1, 15, 10, 0, 0)
    # customer_id is optional, so None is valid
    assert request.customer_id is None


def test_appointment_update_request_valid():
    """Test valid appointment update request."""
    request = AppointmentUpdateRequest(
        status="confirmed",
        notes="Updated notes"
    )
    
    assert request.status == "confirmed"
    assert request.notes == "Updated notes"


def test_appointment_update_request_all_optional():
    """Test appointment update with all optional fields."""
    request = AppointmentUpdateRequest()
    
    assert request.start_at is None
    assert request.status is None


def test_salon_register_request_valid():
    """Test valid salon registration request."""
    request = SalonRegisterRequest(
        name="Test Salon",
        address="123 Main St",
        city="New York",
        state="NY",
        zip_code="10001",
        phone="1234567890",
        email="test@example.com"
    )
    
    assert request.name == "Test Salon"
    assert request.phone == "1234567890"


def test_salon_register_request_requires_contact():
    """Test salon registration requires phone or email."""
    with pytest.raises(ValidationError):
        SalonRegisterRequest(
            name="Test Salon",
            address="123 Main St"
            # Missing phone and email
        )


def test_salon_register_request_phone_only():
    """Test salon registration with phone only."""
    # state and zip_code are required fields (despite being Optional in type hint)
    request = SalonRegisterRequest(
        name="Test Salon",
        address="123 Main St",
        state="NY",
        zip_code="10001",
        phone="1234567890"
    )
    
    assert request.phone == "1234567890"
    assert request.email is None


def test_salon_register_request_email_only():
    """Test salon registration with email only."""
    # state and zip_code are required fields (despite being Optional in type hint)
    request = SalonRegisterRequest(
        name="Test Salon",
        address="123 Main St",
        state="NY",
        zip_code="10001",
        email="test@example.com"
    )
    
    assert request.email == "test@example.com"
    assert request.phone is None


def test_product_create_request_valid():
    """Test valid product creation request."""
    request = ProductCreateRequest(
        salon_id="salon-1",
        name="Hair Gel",
        price="15.99"
    )
    
    assert request.salon_id == "salon-1"
    assert request.name == "Hair Gel"
    assert request.price == "15.99"
    assert request.is_active is True


def test_product_create_request_with_category():
    """Test product creation with category."""
    request = ProductCreateRequest(
        salon_id="salon-1",
        category_id="cat-1",
        name="Hair Gel",
        price="15.99"
    )
    
    assert request.category_id == "cat-1"


def test_product_update_request_partial():
    """Test product update with partial fields."""
    request = ProductUpdateRequest(
        price="18.99"
    )
    
    assert request.price == "18.99"
    assert request.name is None


def test_product_category_create_request_valid():
    """Test valid product category creation."""
    request = ProductCategoryCreateRequest(
        name="Hair Care"
    )
    
    assert request.name == "Hair Care"
    assert request.parent_category_id is None


def test_product_category_create_request_with_parent():
    """Test product category with parent."""
    request = ProductCategoryCreateRequest(
        name="Shampoo",
        parent_category_id="cat-1"
    )
    
    assert request.parent_category_id == "cat-1"
