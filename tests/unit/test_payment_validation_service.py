"""
Unit tests for PaymentValidationService.
Tests card validation, Luhn's algorithm, and card type detection.
"""
import pytest
from services.payment_validation_service import PaymentValidationService


class TestPaymentValidationService:
    """Test suite for PaymentValidationService"""
    
    def test_validate_card_number_valid_visa(self):
        """Test valid Visa card number"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('4111111111111111')
        assert is_valid is True
        assert error is None
        assert card_info['brand'] == 'visa'
    
    def test_validate_card_number_valid_mastercard(self):
        """Test valid Mastercard number"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('5555555555554444')
        assert is_valid is True
        assert error is None
        assert card_info['brand'] == 'mastercard'
    
    def test_validate_card_number_valid_amex(self):
        """Test valid American Express number"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('378282246310005')
        assert is_valid is True
        assert error is None
        assert card_info['brand'] == 'amex'
    
    def test_validate_card_number_invalid_luhn(self):
        """Test invalid card number (fails Luhn check)"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('4111111111111112')
        assert is_valid is False
        assert 'invalid' in error.lower() or 'luhn' in error.lower()
    
    def test_validate_card_number_too_short(self):
        """Test card number too short"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('1234')
        assert is_valid is False
        assert 'length' in error.lower() or 'digits' in error.lower()
    
    def test_validate_card_number_too_long(self):
        """Test card number too long"""
        is_valid, error, card_info = PaymentValidationService.validate_card_number('41111111111111111111')
        assert is_valid is False
        assert 'length' in error.lower() or 'digits' in error.lower()
    
    def test_validate_expiry_valid(self):
        """Test valid expiry date"""
        is_valid, error = PaymentValidationService.validate_expiry(12, 2025)
        assert is_valid is True
        assert error is None
    
    def test_validate_expiry_past_month(self):
        """Test expired card (past month)"""
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if current_month == 1:
            exp_month = 12
            exp_year = current_year - 1
        else:
            exp_month = current_month - 1
            exp_year = current_year
        
        is_valid, error = PaymentValidationService.validate_expiry(exp_month, exp_year)
        assert is_valid is False
        assert 'expired' in error.lower() or 'invalid' in error.lower()
    
    def test_validate_expiry_invalid_month(self):
        """Test invalid month"""
        is_valid, error = PaymentValidationService.validate_expiry(13, 2025)
        assert is_valid is False
        assert 'month' in error.lower()
    
    def test_validate_cvv_valid_visa(self):
        """Test valid CVV for Visa/Mastercard"""
        is_valid, error = PaymentValidationService.validate_cvv('123', 'visa')
        assert is_valid is True
        assert error is None
    
    def test_validate_cvv_valid_amex(self):
        """Test valid CVV for Amex"""
        is_valid, error = PaymentValidationService.validate_cvv('1234', 'amex')
        assert is_valid is True
        assert error is None
    
    def test_validate_cvv_invalid_length(self):
        """Test CVV with wrong length"""
        is_valid, error = PaymentValidationService.validate_cvv('12', 'visa')
        assert is_valid is False
        assert 'cvv' in error.lower() or 'length' in error.lower()
    
    def test_validate_cvv_non_numeric(self):
        """Test CVV with non-numeric characters"""
        is_valid, error = PaymentValidationService.validate_cvv('abc', 'visa')
        assert is_valid is False
        assert 'numeric' in error.lower() or 'digits' in error.lower()
    
    def test_detect_card_brand_visa(self):
        """Test Visa card brand detection"""
        brand = PaymentValidationService.detect_card_brand('4111111111111111')
        assert brand == 'visa'
    
    def test_detect_card_brand_mastercard(self):
        """Test Mastercard brand detection"""
        brand = PaymentValidationService.detect_card_brand('5555555555554444')
        assert brand == 'mastercard'
    
    def test_detect_card_brand_amex(self):
        """Test Amex brand detection"""
        brand = PaymentValidationService.detect_card_brand('378282246310005')
        assert brand == 'amex'
    
    def test_detect_card_brand_unknown(self):
        """Test unknown card brand"""
        brand = PaymentValidationService.detect_card_brand('1234567890123456')
        assert brand == 'unknown'
    
    def test_validate_full_card_info_success(self):
        """Test full card validation success"""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number='4111111111111111',
            exp_month=12,
            exp_year=2025,
            cvv='123',
            cardholder_name='John Doe'
        )
        assert is_valid is True
        assert error is None
        assert card_info is not None
        assert card_info['brand'] == 'visa'
    
    def test_validate_full_card_info_invalid_card(self):
        """Test full validation with invalid card"""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number='1234',
            exp_month=12,
            exp_year=2025,
            cvv='123'
        )
        assert is_valid is False
        assert error is not None

