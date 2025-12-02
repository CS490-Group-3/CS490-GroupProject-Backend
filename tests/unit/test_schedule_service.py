"""
Unit tests for ScheduleService.
Tests barber availability, unavailability blocks, and schedule management.
"""
import pytest
from unittest.mock import Mock, patch
from services.schedule_service import ScheduleService
from datetime import datetime, timezone, timedelta
import uuid


class TestScheduleService:
    """Test suite for ScheduleService"""
    
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
        mock_table.delete.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        
        mock_supabase = Mock()
        mock_supabase.table.return_value = mock_table
        
        monkeypatch.setattr("services.schedule_service.supabase", mock_supabase)
        return mock_supabase, mock_table
    
    def test_create_availability_success(self, mock_supabase):
        """Test creating barber availability"""
        mock_supabase, mock_table = mock_supabase
        
        availability_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.data = [{
            'id': availability_id,
            'barber_id': 'barber-123',
            'day_of_week': 1,
            'start_time': '09:00:00',
            'end_time': '17:00:00'
        }]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = ScheduleService.create_availability(
            barber_id='barber-123',
            day_of_week=1,
            start_time='09:00:00',
            end_time='17:00:00'
        )
        
        assert error is None
        assert result is not None
        assert result['day_of_week'] == 1
    
    def test_create_unavailability_success(self, mock_supabase):
        """Test creating unavailability block"""
        mock_supabase, mock_table = mock_supabase
        
        block_id = str(uuid.uuid4())
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=2)
        
        mock_response = Mock()
        mock_response.data = [{
            'id': block_id,
            'barber_id': 'barber-123',
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
            'reason': 'Vacation'
        }]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = ScheduleService.create_unavailability(
            barber_id='barber-123',
            start_datetime=start.isoformat(),
            end_datetime=end.isoformat(),
            reason='Vacation'
        )
        
        assert error is None
        assert result is not None
        assert result['reason'] == 'Vacation'
    
    def test_get_barber_availability(self, mock_supabase):
        """Test retrieving barber availability"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = [
            {'day_of_week': 0, 'start_time': '09:00:00', 'end_time': '17:00:00'},
            {'day_of_week': 1, 'start_time': '09:00:00', 'end_time': '17:00:00'}
        ]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = ScheduleService.get_barber_availability('barber-123')
        
        assert error is None
        assert len(result) == 2
    
    def test_delete_unavailability_success(self, mock_supabase):
        """Test deleting unavailability block"""
        mock_supabase, mock_table = mock_supabase
        
        block_id = str(uuid.uuid4())
        
        # Mock existing block
        mock_get_response = Mock()
        mock_get_response.data = {'id': block_id, 'barber_id': 'barber-123'}
        mock_get_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_get_response
        
        # Mock delete
        mock_delete_response = Mock()
        mock_delete_response.data = []
        mock_delete_response.error = None
        mock_table.delete.return_value = mock_table
        mock_table.execute.return_value = mock_delete_response
        
        success, error = ScheduleService.delete_unavailability(block_id, 'barber-123')
        
        assert success is True
        assert error is None

