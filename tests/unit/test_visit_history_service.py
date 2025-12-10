"""
Unit tests for VisitHistoryService.
Tests customer visit history aggregation including appointments, spend, images, and loyalty.
"""
import pytest
from unittest.mock import Mock, patch
from services.visit_history_service import VisitHistoryService


class TestGetCustomerVisitHistory:
    """Tests for getting customer visit history."""

    def test_get_visit_history_success(self, monkeypatch):
        """Test successfully getting visit history with appointments."""
        mock_appointments = [
            {
                "id": "appt-1",
                "customer_id": "customer-123",
                "salon_id": "salon-1",
                "service_id": "service-1",
                "barber_id": "barber-1",
                "status": "completed",
                "start_at": "2024-01-15T10:00:00Z",
                "end_at": "2024-01-15T11:00:00Z",
                "notes": "Regular cut",
                "services": {"id": "service-1", "name": "Haircut", "price": "30.00", "duration_minutes": 60},
                "salons": {"id": "salon-1", "name": "Cool Cuts", "address": "123 Main St", "city": "NYC", "state": "NY"},
                "barbers": {"id": "barber-1", "user_id": "barber-user-1"}
            },
            {
                "id": "appt-2",
                "customer_id": "customer-123",
                "salon_id": "salon-1",
                "status": "completed",
                "start_at": "2024-02-15T10:00:00Z",
                "services": {"id": "service-1", "name": "Haircut", "price": "30.00"},
                "salons": {"id": "salon-1", "name": "Cool Cuts"},
                "barbers": None
            }
        ]

        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        # Appointments query
                        mock_response.data = mock_appointments
                    elif name == "customer_images":
                        mock_response.data = []
                    elif name == "loyalty_transactions":
                        mock_response.data = []
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        assert history is not None
        assert history["customer_id"] == "customer-123"
        assert history["statistics"]["total_visits"] == 2  # Both completed
        assert history["statistics"]["total_spend"] == 60.0  # $30 x 2
        assert len(history["appointments"]) == 2

    def test_get_visit_history_with_salon_filter(self, monkeypatch):
        """Test getting visit history filtered by salon."""
        mock_appointments = [
            {
                "id": "appt-1",
                "status": "completed",
                "start_at": "2024-01-15T10:00:00Z",
                "services": {"price": "25.00"},
                "salons": {"id": "salon-1", "name": "Test Salon"},
                "barbers": None
            }
        ]

        def fake_table(name):
            class MockTable:
                def __init__(self):
                    self.filters = {}
                def select(self, *args, **kwargs):
                    return self
                def eq(self, key, value):
                    self.filters[key] = value
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    if name == "appointments":
                        mock_response.data = mock_appointments
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history(
            "customer-123", 
            salon_id="salon-1"
        )

        assert error is None
        assert history is not None
        assert history["salon_id"] == "salon-1"

    def test_get_visit_history_with_images(self, monkeypatch):
        """Test visit history includes customer images.
        
        Note: The service tries to generate signed URLs for images but gracefully
        handles failures. We test that images are counted even if signed URL
        generation fails.
        """
        mock_images = [
            {
                "id": "img-1",
                "customer_id": "customer-123",
                "image_url": "path/to/image.jpg",
                "caption": "New haircut",
                "uploaded_at": "2024-01-16T10:00:00Z"
            }
        ]

        table_calls = {"appointments": 0, "customer_images": 0, "loyalty_transactions": 0}

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    table_calls[name] = table_calls.get(name, 0) + 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if name == "appointments":
                        mock_response.data = []
                    elif name == "customer_images":
                        mock_response.data = mock_images
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        # Images should be counted even if signed URL generation fails
        assert history["statistics"]["total_images"] == 1
        # Verify timeline includes an image entry
        image_entries = [t for t in history["timeline"] if t["type"] == "image"]
        assert len(image_entries) == 1

    def test_get_visit_history_with_loyalty(self, monkeypatch):
        """Test visit history includes loyalty transactions."""
        mock_loyalty = [
            {"id": "loyalty-1", "points": 100, "transaction_type": "earn", "created_at": "2024-01-15"},
            {"id": "loyalty-2", "points": -50, "transaction_type": "redeem", "created_at": "2024-01-20"}
        ]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if name == "appointments":
                        mock_response.data = []
                    elif name == "loyalty_transactions":
                        mock_response.data = mock_loyalty
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        assert history["loyalty_points"] == 50  # 100 - 50

    def test_get_visit_history_appointments_by_status(self, monkeypatch):
        """Test visit history includes appointment counts by status."""
        mock_appointments = [
            {"id": "appt-1", "status": "completed", "start_at": "2024-01-15", "services": None, "salons": None, "barbers": None},
            {"id": "appt-2", "status": "completed", "start_at": "2024-01-16", "services": None, "salons": None, "barbers": None},
            {"id": "appt-3", "status": "cancelled", "start_at": "2024-01-17", "services": None, "salons": None, "barbers": None},
            {"id": "appt-4", "status": "pending", "start_at": "2024-01-18", "services": None, "salons": None, "barbers": None}
        ]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    if name == "appointments":
                        mock_response.data = mock_appointments
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        assert history["statistics"]["appointments_by_status"]["completed"] == 2
        assert history["statistics"]["appointments_by_status"]["cancelled"] == 1
        assert history["statistics"]["appointments_by_status"]["pending"] == 1

    def test_get_visit_history_empty(self, monkeypatch):
        """Test visit history with no data."""
        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        assert history["statistics"]["total_visits"] == 0
        assert history["statistics"]["total_spend"] == 0
        assert history["appointments"] == []

    def test_get_visit_history_error(self, monkeypatch):
        """Test error handling in visit history retrieval."""
        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    raise Exception("Database connection error")
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.error_logging_service.ErrorLoggingService.log_exception", Mock())

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert history is None
        assert "Failed to get visit history" in error

    def test_get_visit_history_timeline_sorted(self, monkeypatch):
        """Test that timeline entries are sorted by date."""
        mock_appointments = [
            {"id": "appt-1", "status": "completed", "start_at": "2024-01-10T10:00:00Z", "services": None, "salons": None, "barbers": None},
            {"id": "appt-2", "status": "completed", "start_at": "2024-01-20T10:00:00Z", "services": None, "salons": None, "barbers": None}
        ]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    if name == "appointments":
                        mock_response.data = mock_appointments
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        # Timeline should be sorted with most recent first
        timeline = history["timeline"]
        assert len(timeline) == 2
        assert timeline[0]["date"] > timeline[1]["date"]


class TestGetSalonCustomerHistory:
    """Tests for getting customer history at a specific salon."""

    def test_get_salon_customer_history_success(self, monkeypatch):
        """Test successfully getting customer history for a specific salon."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def single(self):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1 and name == "salons":
                        # Salon lookup
                        mock_response.data = {"id": "salon-1", "name": "Test Salon"}
                    elif name == "appointments":
                        mock_response.data = [
                            {"id": "appt-1", "status": "completed", "start_at": "2024-01-15", 
                             "services": {"price": "25.00"}, "salons": {"name": "Test Salon"}, "barbers": None}
                        ]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_salon_customer_history("salon-1", "customer-123")

        assert error is None
        assert history is not None
        assert history["salon"]["id"] == "salon-1"
        assert history["salon"]["name"] == "Test Salon"

    def test_get_salon_customer_history_salon_not_found(self, monkeypatch):
        """Test error when salon doesn't exist."""
        mock_response = Mock()
        mock_response.data = None
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
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

        history, error = VisitHistoryService.get_salon_customer_history("nonexistent", "customer-123")

        assert history is None
        assert error == "Salon not found"

    def test_get_salon_customer_history_error(self, monkeypatch):
        """Test error handling in salon customer history retrieval."""
        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def single(self):
                    raise Exception("Database error")
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.error_logging_service.ErrorLoggingService.log_exception", Mock())

        history, error = VisitHistoryService.get_salon_customer_history("salon-1", "customer-123")

        assert history is None
        assert "Failed to get salon customer history" in error


class TestVisitHistoryCalculations:
    """Tests for spend and statistics calculations."""

    def test_spend_calculation_handles_invalid_price(self, monkeypatch):
        """Test spend calculation handles invalid price values gracefully."""
        mock_appointments = [
            {
                "id": "appt-1", 
                "status": "completed", 
                "start_at": "2024-01-15",
                "services": {"price": "invalid"},  # Invalid price
                "salons": None,
                "barbers": None
            },
            {
                "id": "appt-2",
                "status": "completed",
                "start_at": "2024-01-16",
                "services": {"price": "50.00"},  # Valid price
                "salons": None,
                "barbers": None
            }
        ]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    if name == "appointments":
                        mock_response.data = mock_appointments
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        # Only the valid $50 should be counted
        assert history["total_spend"] == 50.0

    def test_spend_calculation_non_completed_excluded(self, monkeypatch):
        """Test that non-completed appointments don't count towards spend."""
        mock_appointments = [
            {
                "id": "appt-1",
                "status": "pending",  # Not completed
                "start_at": "2024-01-15",
                "services": {"price": "100.00"},
                "salons": None,
                "barbers": None
            },
            {
                "id": "appt-2",
                "status": "completed",
                "start_at": "2024-01-16",
                "services": {"price": "50.00"},
                "salons": None,
                "barbers": None
            }
        ]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    mock_response = Mock()
                    mock_response.error = None
                    if name == "appointments":
                        mock_response.data = mock_appointments
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        history, error = VisitHistoryService.get_customer_visit_history("customer-123")

        assert error is None
        # Only completed appointment's $50 should count
        assert history["total_spend"] == 50.0
        assert history["statistics"]["total_visits"] == 1

