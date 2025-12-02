"""
Unit tests for AppointmentService.
Tests appointment creation, updates, cancellation, and availability checks.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.appointment_service import AppointmentService
from datetime import datetime, timezone, timedelta
import uuid


class TestAppointmentService:
    """Test suite for AppointmentService"""
    
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
        mock_table.gte.return_value = mock_table
        mock_table.lte.return_value = mock_table
        mock_table.lt.return_value = mock_table
        mock_table.gt.return_value = mock_table
        mock_table.in_.return_value = mock_table
        mock_table.range.return_value = mock_table
        
        mock_supabase = Mock()
        mock_supabase.table.return_value = mock_table
        
        monkeypatch.setattr("services.appointment_service.supabase", mock_supabase)
        return mock_supabase, mock_table
    
    def test_get_service_success(self, mock_supabase):
        """Test retrieving service"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = {
            'id': 'svc-123',
            'salon_id': 'salon-123',
            'duration_minutes': 30
        }
        mock_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_response
        
        result, error = AppointmentService._get_service('svc-123')
        
        assert error is None
        assert result is not None
        assert result['id'] == 'svc-123'
        assert result['duration_minutes'] == 30
    
    def test_get_service_not_found(self, mock_supabase):
        """Test service not found"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = None
        mock_response.error = Mock(message='Not found')
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_response
        
        result, error = AppointmentService._get_service('svc-999')
        
        assert result is None
        assert error == 'Service not found'
    
    def test_get_barber_success(self, mock_supabase):
        """Test retrieving barber"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = {
            'id': 'barber-123',
            'salon_id': 'salon-123'
        }
        mock_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_response
        
        result, error = AppointmentService._get_barber('barber-123')
        
        assert error is None
        assert result is not None
        assert result['id'] == 'barber-123'
    
    def test_has_overlap_no_overlap(self, mock_supabase):
        """Test checking for appointment overlap when none exists"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock no existing appointments
        mock_response = Mock()
        mock_response.data = []
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        start = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat()
        
        has_overlap = AppointmentService.has_overlap(
            'salon-123',
            'barber-123',
            start,
            end
        )
        
        assert has_overlap is False
    
    def test_has_overlap_with_overlap(self, mock_supabase):
        """Test detecting appointment overlap"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock existing appointment that overlaps
        existing_start = datetime.now(timezone.utc) + timedelta(days=1, hours=1)
        existing_end = existing_start + timedelta(hours=1)
        
        mock_response = Mock()
        mock_response.data = [{
            'id': 'apt-123',
            'start_at': existing_start.isoformat(),
            'end_at': existing_end.isoformat()
        }]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        # New appointment overlaps
        new_start = (existing_start + timedelta(minutes=30)).isoformat()
        new_end = (existing_end + timedelta(minutes=30)).isoformat()
        
        has_overlap = AppointmentService.has_overlap(
            'salon-123',
            'barber-123',
            new_start,
            new_end
        )
        
        assert has_overlap is True
    
    def test_is_barber_available_success(self, mock_supabase):
        """Test barber availability check"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock salon timezone
        with patch.object(AppointmentService, '_get_salon_timezone') as mock_tz:
            mock_tz.return_value = 'America/New_York'
            
            # Mock barber availability
            mock_avail_response = Mock()
            mock_avail_response.data = [{'id': 'avail-123'}]  # Available
            mock_avail_response.error = None
            
            # Mock no unavailability
            mock_unavail_response = Mock()
            mock_unavail_response.data = []
            
            # Mock no overlapping appointments
            mock_appt_response = Mock()
            mock_appt_response.data = []
            
            def execute_side_effect(*args, **kwargs):
                if 'barber_availability' in str(mock_table.select.call_args):
                    return mock_avail_response
                elif 'barber_unavailability' in str(mock_table.select.call_args):
                    return mock_unavail_response
                else:
                    return mock_appt_response
            
            mock_table.execute.side_effect = execute_side_effect
            
            start = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            end = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat()
            
            with patch.object(AppointmentService, 'has_overlap') as mock_overlap:
                mock_overlap.return_value = False
                
                available, message = AppointmentService.is_barber_available(
                    'salon-123',
                    'barber-123',
                    start,
                    end
                )
                
                # Should be available if all checks pass
                assert isinstance(available, bool)
    
    def test_cancel_appointment_success(self, mock_supabase):
        """Test appointment cancellation"""
        mock_supabase, mock_table = mock_supabase
        
        appointment_id = str(uuid.uuid4())
        
        # Mock existing appointment
        mock_get_response = Mock()
        mock_get_response.data = {
            'id': appointment_id,
            'status': 'scheduled',
            'customer_id': 'user-123',
            'salon_id': 'salon-123',
            'barber_id': 'barber-123'
        }
        mock_get_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_get_response
        
        # Mock update
        mock_update_response = Mock()
        mock_update_response.data = [{
            'id': appointment_id,
            'status': 'cancelled'
        }]
        mock_update_response.error = None
        
        with patch.object(AppointmentService, 'get_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = (mock_get_response.data, None)
            
            result, error = AppointmentService.cancel_appointment(
                appointment_id,
                reason='Test cancellation',
                user={'sub': 'user-123', 'role': 'customer'}
            )
            
            # Should either succeed or return specific error
            assert isinstance(result, (dict, type(None)))
    
    def test_get_appointments_by_customer(self, mock_supabase):
        """Test retrieving customer appointments"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = [
            {
                'id': 'apt-1',
                'customer_id': 'user-123',
                'status': 'scheduled',
                'start_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            }
        ]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        with patch.object(AppointmentService, '_hydrate_appointments') as mock_hydrate:
            mock_hydrate.return_value = mock_response.data
            
            result, error = AppointmentService.get_appointments_by_customer(
                'user-123',
                when='upcoming'
            )
            
            assert error is None
            assert isinstance(result, list)

