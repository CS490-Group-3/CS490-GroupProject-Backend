"""
Unit tests for ReviewService.
Tests review creation, updates, deletion, and retrieval.
"""
import pytest
from unittest.mock import Mock, patch
from services.review_service import ReviewService
import uuid


class TestReviewService:
    """Test suite for ReviewService"""
    
    @pytest.fixture
    def mock_supabase(self, monkeypatch):
        """Mock Supabase client"""
        mock_table = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        mock_table.maybe_single.return_value = mock_table
        
        mock_supabase = Mock()
        mock_supabase.table.return_value = mock_table
        
        monkeypatch.setattr("services.review_service.supabase", mock_supabase)
        return mock_supabase, mock_table
    
    def test_create_review_success(self, mock_supabase):
        """Test successful review creation"""
        mock_supabase, mock_table = mock_supabase
        
        review_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.data = [{
            'id': review_id,
            'customer_id': 'user-123',
            'salon_id': 'salon-123',
            'rating': 5,
            'comment': 'Great service!'
        }]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = ReviewService.create_review(
            customer_id='user-123',
            salon_id='salon-123',
            rating=5,
            comment='Great service!'
        )
        
        assert error is None
        assert result is not None
        assert result['rating'] == 5
    
    def test_create_review_duplicate(self, mock_supabase):
        """Test duplicate review prevention"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock existing review
        mock_check_response = Mock()
        mock_check_response.data = [{'id': 'review-123'}]
        mock_check_response.error = None
        mock_table.execute.return_value = mock_check_response
        
        result, error = ReviewService.create_review(
            customer_id='user-123',
            salon_id='salon-123',
            rating=5
        )
        
        assert result is None
        assert 'already' in error.lower() or 'duplicate' in error.lower()
    
    def test_update_review_success(self, mock_supabase):
        """Test successful review update"""
        mock_supabase, mock_table = mock_supabase
        
        review_id = str(uuid.uuid4())
        
        # Mock existing review
        mock_get_response = Mock()
        mock_get_response.data = {
            'id': review_id,
            'customer_id': 'user-123',
            'rating': 3
        }
        mock_get_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_get_response
        
        # Mock update
        mock_update_response = Mock()
        mock_update_response.data = [{
            'id': review_id,
            'rating': 5,
            'comment': 'Updated review'
        }]
        mock_update_response.error = None
        
        result, error = ReviewService.update_review(
            review_id=review_id,
            customer_id='user-123',
            rating=5,
            comment='Updated review'
        )
        
        assert error is None
        assert result is not None
        assert result['rating'] == 5
    
    def test_delete_review_success(self, mock_supabase):
        """Test successful review deletion"""
        mock_supabase, mock_table = mock_supabase
        
        review_id = str(uuid.uuid4())
        
        # Mock existing review
        mock_get_response = Mock()
        mock_get_response.data = {'id': review_id, 'customer_id': 'user-123'}
        mock_get_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_get_response
        
        # Mock delete
        mock_delete_response = Mock()
        mock_delete_response.data = []
        mock_delete_response.error = None
        mock_table.delete.return_value = mock_table
        mock_table.execute.return_value = mock_delete_response
        
        success, error = ReviewService.delete_review(review_id, 'user-123')
        
        assert success is True
        assert error is None
    
    def test_get_salon_reviews(self, mock_supabase):
        """Test retrieving salon reviews"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = [
            {'id': 'review-1', 'rating': 5, 'salon_id': 'salon-123'},
            {'id': 'review-2', 'rating': 4, 'salon_id': 'salon-123'}
        ]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = ReviewService.get_salon_reviews('salon-123')
        
        assert error is None
        assert len(result) == 2

