"""
Unit tests for ReviewService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from services.review_service import ReviewService


def test_create_review_success(monkeypatch):
    """Test creating a review - tests real service logic."""
    mock_appointment = {
        "id": "appt-123",
        "customer_id": "user-123",
        "salon_id": "salon-1",
        "status": "completed"
    }
    
    mock_review = {
        "id": "review-123",
        "user_id": "user-123",
        "appointment_id": "appt-123",
        "salon_id": "salon-1",
        "rating": 5,
        "title": "Great service",
        "comment": "Very satisfied"
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
            def insert(self, data):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get appointment
                    mock_response.data = mock_appointment
                elif call_count[0] == 2:
                    # Second call: check existing review (empty)
                    mock_response.data = []
                else:
                    # Third call: insert review
                    mock_response.data = [mock_review]
                return mock_response
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ReviewService.create_review() method
    review = ReviewService.create_review(
        user_id="user-123",
        appointment_id="appt-123",
        rating=5,
        title="Great service",
        comment="Very satisfied"
    )
    
    assert review["id"] == "review-123"
    assert review["rating"] == 5


def test_create_review_appointment_not_found(monkeypatch):
    """Test creating review for non-existent appointment - tests real error handling."""
    # Mock Supabase response - appointment not found
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
    
    # Test REAL ReviewService.create_review() method
    with pytest.raises(NotFound):
        ReviewService.create_review(
            user_id="user-123",
            appointment_id="nonexistent",
            rating=5,
            title="Test",
            comment="Test"
        )


def test_create_review_wrong_user(monkeypatch):
    """Test creating review for someone else's appointment - tests real authorization."""
    mock_appointment = {
        "id": "appt-123",
        "customer_id": "user-456",  # Different user
        "salon_id": "salon-1",
        "status": "completed"
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
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ReviewService.create_review() method
    with pytest.raises(Forbidden):
        ReviewService.create_review(
            user_id="user-123",  # Trying to review someone else's appointment
            appointment_id="appt-123",
            rating=5,
            title="Test",
            comment="Test"
        )


def test_get_review_success(monkeypatch):
    """Test getting a review - tests real service logic."""
    mock_review = {
        "id": "review-123",
        "rating": 5,
        "title": "Great service",
        "comment": "Very satisfied"
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [mock_review]
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
    
    # Test REAL ReviewService.get_review() method
    review = ReviewService.get_review("review-123")
    
    assert review["id"] == "review-123"
    assert review["rating"] == 5


def test_get_review_not_found(monkeypatch):
    """Test getting a non-existent review - tests real error handling."""
    # Mock Supabase response - no review found
    mock_response = Mock()
    mock_response.data = []
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
    
    # Test REAL ReviewService.get_review() method
    with pytest.raises(NotFound):
        ReviewService.get_review("nonexistent")


def test_update_review_success(monkeypatch):
    """Test updating a review - tests real service logic."""
    existing_review = {
        "id": "review-123",
        "user_id": "user-123",
        "rating": 5,
        "title": "Great service",
        "comment": "Very satisfied"
    }
    
    updated_review = {
        **existing_review,
        "rating": 4,
        "title": "Updated title",
        "comment": "Updated comment"
    }
    
    call_count = [0]
    
    def fake_table(name):
        class MockTable:
            def select(self, *args):
                return self
            def eq(self, *args, **kwargs):
                return self
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get_review
                    mock_response.data = [existing_review]
                else:
                    # Second call: update
                    mock_response.data = [updated_review]
                return mock_response
            def update(self, data):
                return self
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ReviewService.update_review() method
    review = ReviewService.update_review(
        user_id="user-123",
        review_id="review-123",
        rating=4,
        title="Updated title",
        comment="Updated comment"
    )
    
    assert review["rating"] == 4
    assert review["title"] == "Updated title"


def test_update_review_unauthorized(monkeypatch):
    """Test updating someone else's review - tests real authorization."""
    existing_review = {
        "id": "review-123",
        "user_id": "user-456",  # Different user
        "rating": 5
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [existing_review]
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
    
    # Test REAL ReviewService.update_review() method
    with pytest.raises(Forbidden):
        ReviewService.update_review(
            user_id="user-123",  # Trying to update someone else's review
            review_id="review-123",
            rating=1,
            title="Test",
            comment="Test"
        )


def test_delete_review_success(monkeypatch):
    """Test deleting a review - tests real service logic."""
    existing_review = {
        "id": "review-123",
        "user_id": "user-123",
        "appointment_id": "appt-123",
        "salon_id": "salon-1",
        "rating": 5,
        "title": "Test",
        "comment": "Test"
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
            def execute(self):
                call_count[0] += 1
                mock_response = Mock()
                mock_response.error = None
                
                if call_count[0] == 1:
                    # First call: get_review
                    mock_response.data = [existing_review]
                else:
                    # Second call: delete
                    mock_response.data = []
                return mock_response
            def delete(self):
                return self
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ReviewService.delete_review() method
    # Note: delete_review returns dict with message on success
    result = ReviewService.delete_review("user-123", "review-123")
    
    # Method returns dict with message on success
    assert result is not None
    assert "message" in result
    assert "deleted successfully" in result["message"].lower()


def test_delete_review_unauthorized(monkeypatch):
    """Test deleting someone else's review - tests real authorization."""
    existing_review = {
        "id": "review-123",
        "user_id": "user-456"  # Different user
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [existing_review]
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
    
    # Test REAL ReviewService.delete_review() method
    with pytest.raises(Forbidden):
        ReviewService.delete_review("user-123", "review-123")  # Trying to delete someone else's review
