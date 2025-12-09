"""
Unit tests for LoyaltyService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock
from services.loyalty_service import LoyaltyService


def test_get_loyalty_program_success(monkeypatch):
    """Test getting loyalty program - tests real service logic."""
    mock_program = {
        "id": "lp-123",
        "salon_id": "salon-1",
        "points_per_dollar": 1.0,
        "discount": 10,
        "min_points_for_redemption": 100,
        "is_active": True
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_program
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def maybe_single(self):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.get_loyalty_program() method
    program, error = LoyaltyService.get_loyalty_program("salon-1")
    
    assert error is None
    assert program["points_per_dollar"] == 1.0
    assert program["is_active"] is True


def test_get_loyalty_program_not_found(monkeypatch):
    """Test getting loyalty program when none exists - tests real error handling."""
    # Mock Supabase response with no data (not an error)
    mock_response = Mock()
    mock_response.data = None
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def maybe_single(self):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.get_loyalty_program() method
    program, error = LoyaltyService.get_loyalty_program("salon-1")
    
    # No program is not an error - returns None, None
    assert program is None
    assert error is None


def test_create_or_update_loyalty_program_create(monkeypatch):
    """Test creating a new loyalty program - tests real service logic."""
    mock_program = {
        "id": "lp-123",
        "salon_id": "salon-1",
        "points_per_dollar": 1.0,
        "discount": 10,
        "min_points_for_redemption": 100,
        "is_active": True
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def maybe_single(self):
                return self
            def insert(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: check if exists (returns None)
                    mock_response.data = None
                else:
                    # Second call: insert new program
                    mock_response.data = [mock_program]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.create_or_update_loyalty_program() method
    program, error = LoyaltyService.create_or_update_loyalty_program(
        salon_id="salon-1",
        points_per_dollar=1.0,
        discount=10,
        min_points_for_redemption=100,
        is_active=True
    )
    
    assert error is None
    assert program["id"] == "lp-123"


def test_create_or_update_loyalty_program_update(monkeypatch):
    """Test updating existing loyalty program - tests real service logic."""
    existing_program = {
        "id": "lp-123",
        "salon_id": "salon-1",
        "points_per_dollar": 1.0,
        "discount": 10
    }
    
    updated_program = {
        **existing_program,
        "points_per_dollar": 2.0,
        "discount": 15
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def maybe_single(self):
                return self
            def update(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: check if exists (returns existing)
                    mock_response.data = existing_program
                else:
                    # Second call: update program
                    mock_response.data = [updated_program]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.create_or_update_loyalty_program() method
    program, error = LoyaltyService.create_or_update_loyalty_program(
        salon_id="salon-1",
        points_per_dollar=2.0,
        discount=15,
        min_points_for_redemption=100,
        is_active=True
    )
    
    assert error is None
    assert program["points_per_dollar"] == 2.0


def test_get_user_loyalty_balance_success(monkeypatch):
    """Test getting user loyalty balance - tests real service logic."""
    mock_balance = {
        "user_id": "user-123",
        "salon_id": "salon-1",
        "points_balance": 150
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_balance
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def maybe_single(self):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.get_user_loyalty_balance() method
    balance, error = LoyaltyService.get_user_loyalty_balance("user-123", "salon-1")
    
    assert error is None
    assert balance["points_balance"] == 150


def test_earn_points_success(monkeypatch):
    """Test earning points - tests real service logic."""
    mock_balance = {
        "user_id": "user-123",
        "salon_id": "salon-1",
        "points_balance": 50,
        "id": "balance-123"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def maybe_single(self):
                return self
            def insert(self, data):
                return self
            def update(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get balance
                    mock_response.data = mock_balance
                elif call_count[0] == 2:
                    # Second call: update balance
                    mock_response.data = [mock_balance]
                else:
                    # Third call: insert transaction
                    mock_response.data = [{"id": "tx-123", "points": 50}]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.earn_points() method
    success, error = LoyaltyService.earn_points(
        user_id="user-123",
        salon_id="salon-1",
        points=50,
        appointment_id="appt-123",
        description="Appointment completed"
    )
    
    assert error is None
    assert success is True


def test_redeem_points_success(monkeypatch):
    """Test redeeming points - tests real service logic."""
    mock_balance = {
        "user_id": "user-123",
        "salon_id": "salon-1",
        "points_balance": 150,
        "lifetime_points_redeemed": 0,
        "id": "balance-123"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def maybe_single(self):
                return self
            def insert(self, data):
                return self
            def update(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get balance
                    mock_response.data = mock_balance
                elif call_count[0] == 2:
                    # Second call: update balance
                    mock_response.data = [mock_balance]
                else:
                    # Third call: insert transaction
                    mock_response.data = [{"id": "tx-123", "points": -100}]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.redeem_points() method
    success, error = LoyaltyService.redeem_points(
        user_id="user-123",
        salon_id="salon-1",
        points_to_redeem=100
    )
    
    assert error is None
    assert success is True


def test_get_loyalty_transactions_success(monkeypatch):
    """Test getting loyalty transactions - tests real service logic."""
    mock_transactions = [
        {"id": "tx-1", "points": 50, "transaction_type": "earned"},
        {"id": "tx-2", "points": -100, "transaction_type": "redeemed"}
    ]
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_transactions
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def order(self, *args, **kwargs):
            return self
        def range(self, *args, **kwargs):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL LoyaltyService.get_loyalty_transactions() method
    transactions, error = LoyaltyService.get_loyalty_transactions("user-123", "salon-1")
    
    assert error is None
    assert len(transactions) == 2
