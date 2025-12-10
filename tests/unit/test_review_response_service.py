"""
Unit tests for ReviewResponseService.
Tests creating and deleting review responses with proper authorization checks.
"""
import pytest
from unittest.mock import Mock
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from services.review_response_service import ReviewResponseService


class TestCreateResponse:
    """Tests for creating review responses."""

    def test_create_response_as_owner_success(self, monkeypatch):
        """Test salon owner can create a response to a review."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def insert(self, data):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        # Get review
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        # Get appointment
                        mock_response.data = [{
                            "id": "appt-123",
                            "barber_id": "barber-1"
                        }]
                    elif call_count[0] == 3:
                        # Get salon owner
                        mock_response.data = [{"owner_id": "owner-123"}]
                    elif call_count[0] == 4:
                        # Get barber user_id
                        mock_response.data = [{"user_id": "barber-user-456"}]
                    elif call_count[0] == 5:
                        # Check existing response (none exists)
                        mock_response.data = []
                    else:
                        # Insert response
                        mock_response.data = [{
                            "id": "response-123",
                            "review_id": "review-123",
                            "salon_id": "salon-1",
                            "response_text": "Thank you for your feedback!"
                        }]
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        response = ReviewResponseService.create_response(
            user_id="owner-123",  # Matches salon owner
            review_id="review-123",
            message="Thank you for your feedback!"
        )

        assert response["id"] == "response-123"
        assert response["response_text"] == "Thank you for your feedback!"

    def test_create_response_as_barber_success(self, monkeypatch):
        """Test assigned barber can create a response to their review."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def insert(self, data):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        mock_response.data = [{
                            "id": "appt-123",
                            "barber_id": "barber-1"
                        }]
                    elif call_count[0] == 3:
                        mock_response.data = [{"owner_id": "owner-456"}]
                    elif call_count[0] == 4:
                        mock_response.data = [{"user_id": "barber-user-123"}]
                    elif call_count[0] == 5:
                        mock_response.data = []
                    else:
                        mock_response.data = [{
                            "id": "response-123",
                            "review_id": "review-123",
                            "response_text": "Thanks!"
                        }]
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        response = ReviewResponseService.create_response(
            user_id="barber-user-123",  # Matches assigned barber
            review_id="review-123",
            message="Thanks!"
        )

        assert response["id"] == "response-123"

    def test_create_response_review_not_found(self, monkeypatch):
        """Test creating response for non-existent review raises NotFound."""
        mock_response = Mock()
        mock_response.data = []
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(NotFound) as exc_info:
            ReviewResponseService.create_response(
                user_id="user-123",
                review_id="nonexistent",
                message="Test message"
            )
        
        assert "Review not found" in str(exc_info.value)

    def test_create_response_appointment_not_found(self, monkeypatch):
        """Test creating response when appointment not found raises NotFound."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(NotFound) as exc_info:
            ReviewResponseService.create_response(
                user_id="user-123",
                review_id="review-123",
                message="Test message"
            )
        
        assert "Appointment not found" in str(exc_info.value)

    def test_create_response_salon_not_found(self, monkeypatch):
        """Test creating response when salon not found raises NotFound."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        mock_response.data = [{"id": "appt-123", "barber_id": "barber-1"}]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(NotFound) as exc_info:
            ReviewResponseService.create_response(
                user_id="user-123",
                review_id="review-123",
                message="Test message"
            )
        
        assert "Salon not found" in str(exc_info.value)

    def test_create_response_barber_not_found(self, monkeypatch):
        """Test creating response when barber not found raises NotFound."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        mock_response.data = [{"id": "appt-123", "barber_id": "barber-1"}]
                    elif call_count[0] == 3:
                        mock_response.data = [{"owner_id": "owner-456"}]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(NotFound) as exc_info:
            ReviewResponseService.create_response(
                user_id="user-123",
                review_id="review-123",
                message="Test message"
            )
        
        assert "barber not found" in str(exc_info.value).lower()

    def test_create_response_unauthorized(self, monkeypatch):
        """Test unauthorized user cannot create response."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        mock_response.data = [{"id": "appt-123", "barber_id": "barber-1"}]
                    elif call_count[0] == 3:
                        mock_response.data = [{"owner_id": "owner-456"}]
                    elif call_count[0] == 4:
                        mock_response.data = [{"user_id": "barber-user-789"}]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(Forbidden) as exc_info:
            ReviewResponseService.create_response(
                user_id="random-user-123",  # Not owner or barber
                review_id="review-123",
                message="Test message"
            )
        
        assert "Only salon owners or the assigned barber" in str(exc_info.value)

    def test_create_response_already_exists(self, monkeypatch):
        """Test creating response when one already exists raises BadRequest."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "review-123",
                            "salon_id": "salon-1",
                            "appointment_id": "appt-123"
                        }]
                    elif call_count[0] == 2:
                        mock_response.data = [{"id": "appt-123", "barber_id": "barber-1"}]
                    elif call_count[0] == 3:
                        mock_response.data = [{"owner_id": "owner-123"}]
                    elif call_count[0] == 4:
                        mock_response.data = [{"user_id": "barber-user-456"}]
                    else:
                        # Existing response found
                        mock_response.data = [{"id": "existing-response"}]
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(BadRequest) as exc_info:
            ReviewResponseService.create_response(
                user_id="owner-123",
                review_id="review-123",
                message="Test message"
            )
        
        assert "already has a response" in str(exc_info.value)


class TestDeleteResponse:
    """Tests for deleting review responses."""

    def test_delete_response_success(self, monkeypatch):
        """Test successfully deleting own response."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def delete(self):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    
                    if call_count[0] == 1:
                        mock_response.data = [{
                            "id": "response-123",
                            "responder_id": "user-123",
                            "review_id": "review-123",
                            "salon_id": "salon-1",
                            "response_text": "Thank you!"
                        }]
                    else:
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        result = ReviewResponseService.delete_response("user-123", "response-123")

        assert "message" in result
        assert "deleted" in result["message"].lower()

    def test_delete_response_not_found(self, monkeypatch):
        """Test deleting non-existent response raises NotFound."""
        mock_response = Mock()
        mock_response.data = []
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(NotFound) as exc_info:
            ReviewResponseService.delete_response("user-123", "nonexistent")
        
        assert "Response not found" in str(exc_info.value)

    def test_delete_response_unauthorized(self, monkeypatch):
        """Test deleting someone else's response raises Forbidden."""
        mock_response = Mock()
        mock_response.data = [{
            "id": "response-123",
            "responder_id": "other-user-456"  # Different user
        }]
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        with pytest.raises(Forbidden) as exc_info:
            ReviewResponseService.delete_response("user-123", "response-123")
        
        assert "only delete your own response" in str(exc_info.value).lower()

