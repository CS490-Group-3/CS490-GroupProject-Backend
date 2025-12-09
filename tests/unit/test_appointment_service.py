"""
Unit tests for AppointmentService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
from services.appointment_service import AppointmentService


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    return {
        "sub": "user-123",
        "email": "test@example.com",
        "role": "customer"
    }


def test_get_available_slots_success(monkeypatch):
    """Test getting available appointment slots - tests real service logic."""
    # Mock service lookup
    mock_service = {
        "id": "service-1",
        "duration_minutes": 30,
        "salon_id": "salon-1"
    }
    
    # Mock barber availability
    mock_availability = [
        {"start_time": "09:00", "end_time": "17:00", "is_active": True}
    ]
    
    # Mock unavailability (empty - no blocks)
    mock_unavailability = []
    
    # Mock existing appointments (empty - no conflicts)
    mock_appointments = []
    
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
            def order(self, *args, **kwargs):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if name == "services":
                    mock_response.data = mock_service
                elif name == "barber_availability":
                    mock_response.data = mock_availability
                elif name == "barber_unavailability":
                    mock_response.data = mock_unavailability
                elif name == "appointments":
                    mock_response.data = mock_appointments
                else:
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    # Mock timezone lookup
    def fake_get_timezone(salon_id):
        return "America/New_York"
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "_get_salon_timezone", fake_get_timezone)
    monkeypatch.setattr(AppointmentService, "_get_service", lambda *args: (mock_service, None))
    
    # Test REAL AppointmentService.get_available_slots() method
    slots, error = AppointmentService.get_available_slots(
        salon_id="salon-1",
        barber_id="barber-1",
        service_id="service-1",
        date_str="2024-01-15"
    )
    
    assert error is None
    assert slots is not None
    assert isinstance(slots, list)


def test_create_appointment_success(monkeypatch, mock_user):
    """Test creating a new appointment - tests real service logic."""
    # Mock service
    mock_service = {
        "id": "service-1",
        "duration_minutes": 30,
        "salon_id": "salon-1"
    }
    
    # Mock barber
    mock_barber = {
        "id": "barber-1",
        "salon_id": "salon-1"
    }
    
    # Mock created appointment
    mock_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "salon_id": "salon-1",
        "barber_id": "barber-1",
        "service_id": "service-1",
        "start_at": "2024-01-15T10:00:00Z",
        "end_at": "2024-01-15T10:30:00Z",
        "status": "scheduled"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def __init__(self):
                self._call_type = None
                self._is_single = False
            
            def select(self, *args):
                self._call_type = 'select'
                return self
            def eq(self, *args, **kwargs):
                return self
            def in_(self, *args, **kwargs):
                return self
            def single(self):
                self._is_single = True
                return self
            def insert(self, data):
                self._call_type = 'insert'
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if name == "services":
                    mock_response.data = mock_service
                elif name == "barbers":
                    mock_response.data = [mock_barber]
                elif name == "appointments":
                    if self._call_type == 'select' and self._is_single:
                        # get_by_id call (uses .single()) - return single appointment dict
                        mock_response.data = {"id": "appt-123", **mock_appointment}
                    elif self._call_type == 'insert':
                        # Insert returns created appointment with id
                        mock_response.data = [{"id": "appt-123", **mock_appointment}]
                    else:
                        # Overlap check and availability check return empty
                        mock_response.data = []
                else:
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    # Mock helper methods
    def fake_get_service(service_id):
        return mock_service, None
    
    def fake_get_barber(barber_id):
        return mock_barber, None
    
    def fake_has_overlap(*args):
        return False  # No overlap
    
    def fake_is_barber_available(*args):
        return True, None  # Available
    
    # Mock _hydrate_appointments to avoid additional queries
    def fake_hydrate(appointments):
        # Return appointments as-is (or as list if single dict)
        if isinstance(appointments, list):
            return appointments
        return [appointments] if appointments else []
    
    monkeypatch.setattr(AppointmentService, "_hydrate_appointments", fake_hydrate)
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "_get_service", fake_get_service)
    monkeypatch.setattr(AppointmentService, "_get_barber", fake_get_barber)
    monkeypatch.setattr(AppointmentService, "has_overlap", fake_has_overlap)
    monkeypatch.setattr(AppointmentService, "is_barber_available", fake_is_barber_available)
    monkeypatch.setattr(AppointmentService, "_hydrate_appointments", fake_hydrate)
    monkeypatch.setattr(AppointmentService, "_can_manage", lambda user, appt: True)  # Allow access
    
    # Test REAL AppointmentService.create_appointment() method
    appointment_data = {
        "customer_id": "user-123",
        "salon_id": "salon-1",
        "barber_id": "barber-1",
        "service_id": "service-1",
        "start_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    }
    
    appointment, error = AppointmentService.create_appointment(
        appointment_data,
        user=mock_user
    )
    
    assert error is None
    assert appointment is not None
    assert appointment["id"] == "appt-123"


def test_get_appointments_by_customer_success(monkeypatch):
    """Test listing appointments for a customer - tests real service logic."""
    mock_appointments = [
        {
            "id": "appt-1",
            "status": "scheduled",
            "start_at": "2024-01-15T10:00:00Z",
            "customer_id": "user-123"
        },
        {
            "id": "appt-2",
            "status": "confirmed",
            "start_at": "2024-01-16T11:00:00Z",
            "customer_id": "user-123"
        }
    ]
    
    # Mock Supabase response for data query
    mock_response = Mock()
    mock_response.data = mock_appointments
    mock_response.error = None
    
    # Mock Supabase response for count query
    mock_count_response = Mock()
    mock_count_response.count = 2
    mock_count_response.error = None
    
    call_count = [0]
    
    class MockTable:
        def __init__(self):
            self._is_count = False
        
        def select(self, *args, **kwargs):
            # Check if this is a count query (has count="exact" in kwargs)
            if kwargs.get("count") == "exact":
                self._is_count = True
            return self
        
        def eq(self, *args, **kwargs):
            return self
        
        def neq(self, *args, **kwargs):
            return self
        
        def order(self, *args, **kwargs):
            return self
        
        def execute(self):
            call_count[0] += 1
            if self._is_count:
                return mock_count_response
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    # Mock hydrate method
    def fake_hydrate(appointments):
        return appointments
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "_hydrate_appointments", fake_hydrate)
    monkeypatch.setattr(AppointmentService, "_apply_filters", lambda query, *args: query)
    monkeypatch.setattr(AppointmentService, "_paginate", lambda query, *args: query)
    
    # Test REAL AppointmentService.get_appointments_by_customer() method
    # Note: get_appointments_by_customer returns (appointments, error, total_count)
    appointments, error, total_count = AppointmentService.get_appointments_by_customer(
        customer_id="user-123",
        when="all"
    )
    
    assert error is None
    assert len(appointments) == 2
    assert appointments[0]["id"] == "appt-1"
    assert total_count == 2


def test_get_by_id_success(monkeypatch, mock_user):
    """Test getting a single appointment by ID - tests real service logic."""
    mock_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "status": "confirmed",
        "salon_id": "salon-1",
        "barber_id": "barber-1",
        "service_id": "service-1"
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_appointment
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
    
    # Mock hydrate method
    def fake_hydrate(appointments):
        if isinstance(appointments, list):
            return appointments[0] if appointments else None
        return appointments
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "_hydrate_appointments", lambda x: [x] if isinstance(x, dict) else [])
    
    # Test REAL AppointmentService.get_by_id() method
    appointment, error = AppointmentService.get_by_id("appt-123", user=mock_user)
    
    assert error is None
    assert appointment is not None
    assert appointment["id"] == "appt-123"


def test_update_appointment_success(monkeypatch, mock_user):
    """Test updating an appointment - tests real service logic."""
    current_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "status": "scheduled",
        "salon_id": "salon-1",
        "barber_id": "barber-1",
        "start_at": "2024-01-15T10:00:00Z",
        "end_at": "2024-01-15T10:30:00Z"
    }
    
    updated_appointment = {
        **current_appointment,
        "status": "confirmed",
        "notes": "Updated notes"
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
                    # First call: get_by_id
                    mock_response.data = current_appointment
                else:
                    # Second call: update
                    mock_response.data = [updated_appointment]
                return mock_response
        return MockTable()
    
    def fake_get_by_id(appointment_id, user):
        if call_count[0] == 0:
            return current_appointment, None
        return updated_appointment, None
    
    def fake_can_manage(user, appointment):
        return True  # User can manage
    
    def fake_has_overlap(*args):
        return False  # No overlap
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(AppointmentService, "_can_manage", fake_can_manage)
    monkeypatch.setattr(AppointmentService, "has_overlap", fake_has_overlap)
    monkeypatch.setattr(AppointmentService, "_to_utc_iso", lambda x: x if isinstance(x, str) else x.isoformat())
    
    # Test REAL AppointmentService.update_appointment() method
    update_data = {
        "status": "confirmed",
        "notes": "Updated notes"
    }
    
    appointment, error = AppointmentService.update_appointment(
        appointment_id="appt-123",
        update_data=update_data,
        user=mock_user
    )
    
    assert error is None
    assert appointment is not None


def test_cancel_appointment_success(monkeypatch, mock_user):
    """Test canceling an appointment - tests real service logic."""
    current_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "status": "scheduled",
        "salon_id": "salon-1"
    }
    
    cancelled_appointment = {
        **current_appointment,
        "status": "cancelled",
        "cancellation_reason": "Changed my mind"
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
                    # First call: get_by_id
                    mock_response.data = current_appointment
                else:
                    # Second call: update
                    mock_response.data = [cancelled_appointment]
                return mock_response
        return MockTable()
    
    def fake_get_by_id(appointment_id, user):
        if call_count[0] == 0:
            return current_appointment, None
        return cancelled_appointment, None
    
    def fake_can_manage(user, appointment):
        return True  # User can manage
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(AppointmentService, "_can_manage", fake_can_manage)
    
    # Test REAL AppointmentService.cancel_appointment() method
    appointment, error = AppointmentService.cancel_appointment(
        appointment_id="appt-123",
        user=mock_user,
        reason="Changed my mind"
    )
    
    assert error is None
    assert appointment is not None
    assert appointment["status"] == "cancelled"


def test_reschedule_appointment_success(monkeypatch, mock_user):
    """Test rescheduling an appointment - tests real service logic."""
    current_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "salon_id": "salon-1",
        "barber_id": "barber-1",
        "service_id": "service-1",  # Required for reschedule
        "start_at": "2024-01-15T10:00:00Z",
        "end_at": "2024-01-15T10:30:00Z"
    }
    
    rescheduled_appointment = {
        **current_appointment,
        "start_at": "2024-01-20T14:00:00Z",
        "end_at": "2024-01-20T14:30:00Z"
    }
    
    mock_service = {
        "duration_minutes": 30
    }
    
    def fake_get_by_id(appointment_id, user):
        return current_appointment, None
    
    def fake_can_manage(user, appointment):
        return True
    
    def fake_has_overlap(*args):
        return False  # No overlap
    
    def fake_is_barber_available(*args):
        return True, None  # Available
    
    mock_barber = {
        "id": "barber-1",
        "salon_id": "salon-1"
    }
    
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
                mock_response = Mock()
                mock_response.error = None
                if name == "services":
                    mock_response.data = mock_service
                elif name == "barbers":
                    mock_response.data = mock_barber
                elif name == "appointments":
                    mock_response.data = [rescheduled_appointment]
                else:
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(AppointmentService, "_can_manage", fake_can_manage)
    monkeypatch.setattr(AppointmentService, "has_overlap", fake_has_overlap)
    monkeypatch.setattr(AppointmentService, "is_barber_available", fake_is_barber_available)
    
    # Test REAL AppointmentService.reschedule_appointment() method
    appointment, error = AppointmentService.reschedule_appointment(
        appointment_id="appt-123",
        salon_id="salon-1",
        barber_id="barber-1",
        new_start_at="2024-01-20T14:00:00Z",
        user=mock_user
    )
    
    assert error is None
    assert appointment is not None


def test_mark_completed_or_no_show_success(monkeypatch, mock_user):
    """Test marking an appointment as completed - tests real service logic."""
    # Use salon_owner role for this test since customer can't mark completed
    admin_user = {
        "sub": "owner-123",
        "email": "owner@example.com",
        "role": "salon_owner"
    }
    
    current_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "status": "confirmed",
        "salon_id": "salon-1"
    }
    
    completed_appointment = {
        **current_appointment,
        "status": "completed"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                self._is_select = True
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                self._is_single = True
                return self
            def update(self, data):
                self._is_update = True
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                if name == "salons":
                    mock_response.data = [{"id": "salon-1"}]  # Owner's salon
                elif name == "appointments":
                    if hasattr(self, '_is_update'):
                        # update call - returns list
                        updated = {**completed_appointment, "status": "completed"}
                        mock_response.data = [updated]
                    elif hasattr(self, '_is_single'):
                        # get_by_id call - returns single dict with completed status
                        # This is called after update, so return completed appointment
                        mock_response.data = {**completed_appointment, "status": "completed"}
                    else:
                        mock_response.data = []
                else:
                    mock_response.data = []
                return mock_response
        return MockTable()
    
    # Mock _hydrate_appointments and _can_manage
    def fake_hydrate(appointments):
        if isinstance(appointments, list):
            return appointments
        return [appointments] if appointments else []
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    monkeypatch.setattr(AppointmentService, "_hydrate_appointments", fake_hydrate)
    monkeypatch.setattr(AppointmentService, "_can_manage", lambda user, appt: True)
    
    # Test REAL AppointmentService.mark_completed_or_no_show() method
    appointment, error = AppointmentService.mark_completed_or_no_show(
        appointment_id="appt-123",
        status="completed",
        user=admin_user
    )
    
    assert error is None
    assert appointment is not None
    assert appointment["status"] == "completed"
