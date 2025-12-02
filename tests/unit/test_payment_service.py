"""
Unit tests for PaymentService.
Tests payment creation, validation, and saved payment methods.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.payment_service import PaymentService
from services.payment_validation_service import PaymentValidationService
import uuid
from datetime import datetime, timezone


class TestPaymentService:
    """Test suite for PaymentService"""
    
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
        
        monkeypatch.setattr("services.payment_service.supabase", mock_supabase)
        return mock_supabase, mock_table
    
    def test_create_saved_payment_method_success(self, mock_supabase):
        """Test successful creation of saved payment method"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock validation success
        with patch.object(PaymentValidationService, 'validate_full_card_info') as mock_validate:
            mock_validate.return_value = (True, None, {
                'brand': 'visa',
                'last4': '1234',
                'type': 'credit'
            })
            
            # Mock successful insert
            mock_response = Mock()
            mock_response.data = [{
                'id': str(uuid.uuid4()),
                'user_id': 'user-123',
                'card_brand': 'visa',
                'last4': '1234',
                'is_default': True
            }]
            mock_response.error = None
            mock_table.execute.return_value = mock_response
            
            result, error = PaymentService.create_saved_payment_method(
                user_id='user-123',
                card_number='4111111111111111',
                exp_month=12,
                exp_year=2025,
                cvv='123',
                cardholder_name='John Doe',
                is_default=True
            )
            
            assert error is None
            assert result is not None
            assert result['user_id'] == 'user-123'
            assert result['card_brand'] == 'visa'
    
    def test_create_saved_payment_method_invalid_card(self, mock_supabase):
        """Test creation fails with invalid card"""
        with patch.object(PaymentValidationService, 'validate_full_card_info') as mock_validate:
            mock_validate.return_value = (False, 'Invalid card number', None)
            
            result, error = PaymentService.create_saved_payment_method(
                user_id='user-123',
                card_number='1234',
                exp_month=12,
                exp_year=2025,
                cvv='123'
            )
            
            assert result is None
            assert error == 'Invalid card number'
    
    def test_create_payment_success(self, mock_supabase):
        """Test successful payment creation"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock payment insert
        payment_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.data = [{
            'id': payment_id,
            'appointment_id': 'apt-123',
            'user_id': 'user-123',
            'amount': 50.00,
            'payment_status': 'completed'
        }]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = PaymentService.create_payment(
            appointment_id='apt-123',
            user_id='user-123',
            salon_id='salon-123',
            amount=50.00
        )
        
        assert error is None
        assert result is not None
        assert result['id'] == payment_id
        assert result['amount'] == 50.00
    
    def test_refund_payment_success(self, mock_supabase):
        """Test successful payment refund"""
        mock_supabase, mock_table = mock_supabase
        
        # Mock existing payment
        payment_id = str(uuid.uuid4())
        mock_get_response = Mock()
        mock_get_response.data = {
            'id': payment_id,
            'payment_status': 'completed',
            'appointment_id': 'apt-123',
            'user_id': 'user-123',
            'salon_id': 'salon-123',
            'amount': 50.00
        }
        mock_get_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_get_response
        
        # Mock update response
        mock_update_response = Mock()
        mock_update_response.data = [{
            'id': payment_id,
            'payment_status': 'refunded'
        }]
        mock_update_response.error = None
        mock_table.update.return_value = mock_table
        mock_table.execute.return_value = mock_update_response
        
        success, error = PaymentService.refund_payment(payment_id, reason='Test refund')
        
        assert success is True
        assert error is None
    
    def test_refund_payment_already_refunded(self, mock_supabase):
        """Test refund fails if payment already refunded"""
        mock_supabase, mock_table = mock_supabase
        
        payment_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.data = {
            'id': payment_id,
            'payment_status': 'refunded'
        }
        mock_response.error = None
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = mock_response
        
        success, error = PaymentService.refund_payment(payment_id)
        
        assert success is True  # Already refunded, no action needed
        assert error is None
    
    def test_get_user_payment_methods(self, mock_supabase):
        """Test retrieving user's saved payment methods"""
        mock_supabase, mock_table = mock_supabase
        
        mock_response = Mock()
        mock_response.data = [
            {'id': 'pm-1', 'card_brand': 'visa', 'last4': '1234', 'is_default': True},
            {'id': 'pm-2', 'card_brand': 'mastercard', 'last4': '5678', 'is_default': False}
        ]
        mock_response.error = None
        mock_table.execute.return_value = mock_response
        
        result, error = PaymentService.get_user_payment_methods('user-123')
        
        assert error is None
        assert len(result) == 2
        assert result[0]['is_default'] is True

