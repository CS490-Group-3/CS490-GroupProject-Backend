"""
Unit tests for ScheduleService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock
from datetime import time
from services.schedule_service import ScheduleService


def test_check_barber_exists_success(monkeypatch):
    """Test checking if barber exists - tests real service logic."""
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [{"id": "barber-1"}]
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
    
    # Test REAL ScheduleService.check_barber_exists() method
    exists = ScheduleService.check_barber_exists("barber-1")
    
    assert exists is True


def test_create_availability_success(monkeypatch):
    """Test creating availability - tests real service logic."""
    mock_availability = {
        "id": "avail-123",
        "barber_id": "barber-1",
        "day_of_week": 1,
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "is_active": True
    }
    
    # Track calls per table name
    table_calls = {}
    
    def fake_table(name):
        if name not in table_calls:
            table_calls[name] = [0]
        
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def insert(self, data):
                return self
            def execute(self):
                table_calls[name][0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if name == "barbers":
                    # Barber lookup for salon hours check
                    mock_response.data = {"salon_id": "salon-1"}
                elif name == "salon_hours":
                    # Salon hours check
                    mock_response.data = {"day_of_week": 1, "open_time": "08:00:00", "close_time": "20:00:00", "is_closed": False}
                elif name == "barber_availability":
                    if table_calls[name][0] == 1:
                        # First call: check existing availability (empty - no conflict)
                        mock_response.data = []  # Empty list means no existing availability
                    else:
                        # Second call: insert availability
                        mock_response.data = [mock_availability]
                else:
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.create_availability() method
    availability, error = ScheduleService.create_availability(
        barber_id="barber-1",
        day_of_week=1,
        start_time="09:00",
        end_time="17:00",
        is_active=True
    )
    
    assert error is None
    assert availability["day_of_week"] == 1


def test_get_availability_success(monkeypatch):
    """Test getting availability - tests real service logic."""
    mock_availability = [
        {
            "id": "avail-1",
            "barber_id": "barber-1",
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "17:00:00"
        }
    ]
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_availability
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def order(self, *args, **kwargs):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.get_availability() method
    availability, error = ScheduleService.get_availability("barber-1")
    
    assert error is None
    assert len(availability) == 1
    assert availability[0]["day_of_week"] == 1


def test_update_availability_success(monkeypatch):
    """Test updating availability - tests real service logic."""
    existing_availability = {
        "barber_id": "barber-1",
        "day_of_week": 1,
        "start_time": "09:00:00",
        "end_time": "17:00:00"
    }
    
    mock_updated = {
        "id": "avail-123",
        "barber_id": "barber-1",
        "day_of_week": 1,
        "start_time": "10:00:00",
        "end_time": "18:00:00"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def update(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get existing
                    mock_response.data = existing_availability
                else:
                    # Second call: update
                    mock_response.data = [mock_updated]
                return mock_response
        return MockTable()
    
    # Mock salon hours check
    def fake_is_within_salon_hours(*args):
        return True, None
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(ScheduleService, "_is_within_salon_hours", fake_is_within_salon_hours)
    
    # Test REAL ScheduleService.update_availability() method
    update_data = {
        "start_time": "10:00:00",
        "end_time": "18:00:00"
    }
    
    availability, error = ScheduleService.update_availability(
        availability_id="avail-123",
        update_data=update_data
    )
    
    assert error is None
    assert availability["start_time"] == "10:00:00"


def test_create_unavailability_success(monkeypatch):
    """Test creating unavailability block - tests real service logic."""
    mock_block = {
        "id": "block-123",
        "barber_id": "barber-1",
        "start_datetime": "2024-01-15T10:00:00Z",
        "end_datetime": "2024-01-15T12:00:00Z"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def lt(self, *args, **kwargs):
                return self
            def gt(self, *args, **kwargs):
                return self
            def in_(self, *args, **kwargs):
                return self
            def insert(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] <= 2:
                    # First two calls: check overlap and appointments (empty)
                    mock_response.data = []
                else:
                    # Third call: insert block
                    mock_response.data = [mock_block]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.create_unavailability() method
    block, error = ScheduleService.create_unavailability(
        barber_id="barber-1",
        start_datetime="2024-01-15T10:00:00Z",
        end_datetime="2024-01-15T12:00:00Z",
        reason="Lunch break"
    )
    
    assert error is None
    assert block["id"] == "block-123"


def test_list_unavailability_success(monkeypatch):
    """Test listing unavailability blocks - tests real service logic."""
    mock_blocks = [
        {
            "id": "block-1",
            "barber_id": "barber-1",
            "start_datetime": "2024-01-15T10:00:00Z",
            "end_datetime": "2024-01-15T12:00:00Z"
        }
    ]
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_blocks
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args, **kwargs):
            return self
        def order(self, *args, **kwargs):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.list_unavailability() method
    blocks, error = ScheduleService.list_unavailability("barber-1")
    
    assert error is None
    assert len(blocks) == 1
    assert blocks[0]["id"] == "block-1"


def test_update_unavailability_success(monkeypatch):
    """Test updating unavailability block - tests real service logic."""
    existing_block = {
        "id": "block-123",
        "barber_id": "barber-1",
        "start_datetime": "2024-01-15T10:00:00Z",
        "end_datetime": "2024-01-15T12:00:00Z"
    }
    
    mock_updated = {
        **existing_block,
        "start_datetime": "2024-01-15T11:00:00Z",
        "end_datetime": "2024-01-15T13:00:00Z"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def lt(self, *args, **kwargs):
                return self
            def gt(self, *args, **kwargs):
                return self
            def in_(self, *args, **kwargs):
                return self
            def neq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def update(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get existing block
                    mock_response.data = existing_block
                elif call_count[0] <= 3:
                    # Next calls: check overlap and appointments (empty)
                    mock_response.data = []
                else:
                    # Last call: update block
                    mock_response.data = [mock_updated]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.update_unavailability() method
    updates = {
        "start_datetime": "2024-01-15T11:00:00Z",
        "end_datetime": "2024-01-15T13:00:00Z",
        "reason": "Updated reason"
    }
    
    block, error = ScheduleService.update_unavailability(
        block_id="block-123",
        barber_id="barber-1",
        updates=updates
    )
    
    assert error is None
    assert block["start_datetime"] == "2024-01-15T11:00:00Z"


def test_delete_unavailability_success(monkeypatch):
    """Test deleting unavailability block - tests real service logic."""
    existing_block = {
        "id": "block-123",
        "barber_id": "barber-1",
        "start_datetime": "2024-01-15T10:00:00Z",
        "end_datetime": "2024-01-15T12:00:00Z"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def maybe_single(self):
                return self
            def delete(self):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get existing block (single)
                    mock_response.data = existing_block
                elif call_count[0] == 2:
                    # Second call: get full block for audit (maybe_single)
                    mock_response.data = existing_block
                else:
                    # Third call: delete
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ScheduleService.delete_unavailability() method
    success, error = ScheduleService.delete_unavailability(
        block_id="block-123",
        barber_id="barber-1"
    )
    
    assert error is None
    assert success is True
