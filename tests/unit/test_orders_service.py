"""
Unit tests for OrdersService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock
from models.orders import OrderCreateRequest
from services.orders_service import OrdersService


def test_get_order_details_success(monkeypatch):
    """Test getting an order by ID - tests real service logic."""
    mock_order = {
        "id": "order-123",
        "user_id": "user-123",
        "salon_id": "salon-1",
        "order_status": "pending",
        "total_amount": "50.00"
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_order
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def single(self):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL OrdersService.get_order_details() method
    order, error = OrdersService.get_order_details("order-123")
    
    assert error is None
    assert order["id"] == "order-123"
    assert order["order_status"] == "pending"


def test_get_order_not_found(monkeypatch):
    """Test getting a non-existent order - tests real error handling."""
    # Mock Supabase response with no data
    mock_response = Mock()
    mock_response.data = None
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def single(self):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL OrdersService.get_order_details() method
    order, error = OrdersService.get_order_details("nonexistent")
    
    assert order is None
    assert error == "Order not found"


def test_create_order_success(monkeypatch):
    """Test creating an order - tests real service logic."""
    mock_order = {
        "id": "order-123",
        "user_id": "user-123",
        "salon_id": "salon-1",
        "order_status": "cart",
        "total_amount": "50.00"
    }
    
    # Mock Supabase insert response
    mock_response = Mock()
    mock_response.data = [mock_order]
    mock_response.error = None
    
    class MockTable:
        def insert(self, data):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL OrdersService.create_order() method
    order_data = OrderCreateRequest(
        user_id="user-123",
        salon_id="salon-1"
    )
    
    order, error = OrdersService.create_order(order_data)
    
    assert error is None
    assert order["order_status"] == "cart"
    assert order["user_id"] == "user-123"


def test_get_active_cart_success(monkeypatch):
    """Test getting active cart - tests real service logic."""
    mock_cart = {
        "id": "order-123",
        "order_status": "cart",
        "user_id": "user-123",
        "salon_id": "salon-1"
    }
    
    # Mock Supabase response - cart exists
    mock_response = Mock()
    mock_response.data = [mock_cart]
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL OrdersService.get_active_cart() method
    cart, error = OrdersService.get_active_cart("user-123", "salon-1")
    
    assert error is None
    assert cart["order_status"] == "cart"


def test_get_active_cart_creates_new(monkeypatch):
    """Test that getting active cart creates new one if none exists - tests real logic."""
    mock_cart = {
        "id": "order-123",
        "order_status": "cart",
        "user_id": "user-123",
        "salon_id": "salon-1"
    }
    
    # Mock Supabase: first call (select) returns empty, second call (insert) returns new cart
    operation_type = []
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                operation_type.append("select")
                return self
            def eq(self, *args, **kwargs):
                return self
            def insert(self, data):
                operation_type.append("insert")
                return self
            def execute(self):
                mock_response = Mock()
                if operation_type[-1] == "select":
                    # First call: no cart exists
                    mock_response.data = []
                else:
                    # Second call: cart created via insert
                    mock_response.data = [mock_cart]
                mock_response.error = None
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL OrdersService.get_active_cart() method
    cart, error = OrdersService.get_active_cart("user-123", "salon-1")
    
    assert error is None
    assert cart is not None
    assert cart["order_status"] == "cart"
