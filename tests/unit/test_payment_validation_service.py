"""
Unit tests for PaymentValidationService.
Tests card validation logic including Luhn's algorithm, card brand detection,
expiry date validation, and CVV validation.
"""
import pytest
from datetime import datetime
from services.payment_validation_service import PaymentValidationService


class TestValidateCardNumber:
    """Tests for card number validation using Luhn's algorithm."""

    def test_valid_visa_card(self):
        """Test valid Visa card number."""
        is_valid, error = PaymentValidationService.validate_card_number("4532015112830366")
        assert is_valid is True
        assert error is None

    def test_valid_mastercard(self):
        """Test valid Mastercard number."""
        is_valid, error = PaymentValidationService.validate_card_number("5425233430109903")
        assert is_valid is True
        assert error is None

    def test_valid_amex(self):
        """Test valid American Express card number."""
        is_valid, error = PaymentValidationService.validate_card_number("374245455400126")
        assert is_valid is True
        assert error is None

    def test_card_with_spaces(self):
        """Test card number with spaces is handled correctly."""
        is_valid, error = PaymentValidationService.validate_card_number("4532 0151 1283 0366")
        assert is_valid is True
        assert error is None

    def test_card_with_dashes(self):
        """Test card number with dashes is handled correctly."""
        is_valid, error = PaymentValidationService.validate_card_number("4532-0151-1283-0366")
        assert is_valid is True
        assert error is None

    def test_invalid_card_non_digits(self):
        """Test card number with non-digit characters fails."""
        is_valid, error = PaymentValidationService.validate_card_number("4532015112830ABC")
        assert is_valid is False
        assert "only digits" in error.lower()

    def test_invalid_card_too_short(self):
        """Test card number too short fails."""
        is_valid, error = PaymentValidationService.validate_card_number("453201511")
        assert is_valid is False
        assert "between 13 and 19" in error

    def test_invalid_card_too_long(self):
        """Test card number too long fails."""
        is_valid, error = PaymentValidationService.validate_card_number("45320151128303661234567")
        assert is_valid is False
        assert "between 13 and 19" in error

    def test_invalid_card_fails_luhn(self):
        """Test card number that fails Luhn's algorithm."""
        is_valid, error = PaymentValidationService.validate_card_number("4532015112830367")
        assert is_valid is False
        assert "Luhn" in error


class TestDetectCardBrand:
    """Tests for card brand detection."""

    def test_detect_visa(self):
        """Test Visa detection (starts with 4)."""
        brand = PaymentValidationService.detect_card_brand("4532015112830366")
        assert brand == "visa"

    def test_detect_mastercard(self):
        """Test Mastercard detection (starts with 51-55)."""
        brand = PaymentValidationService.detect_card_brand("5425233430109903")
        assert brand == "mastercard"

    def test_detect_amex(self):
        """Test American Express detection (starts with 34 or 37)."""
        brand = PaymentValidationService.detect_card_brand("374245455400126")
        assert brand == "amex"

    def test_detect_discover(self):
        """Test Discover detection (starts with 6011 or 65)."""
        brand = PaymentValidationService.detect_card_brand("6011111111111117")
        assert brand == "discover"

    def test_detect_unknown(self):
        """Test unknown card brand."""
        brand = PaymentValidationService.detect_card_brand("9999999999999999")
        assert brand == "unknown"

    def test_detect_with_spaces(self):
        """Test brand detection works with spaces."""
        brand = PaymentValidationService.detect_card_brand("4532 0151 1283 0366")
        assert brand == "visa"


class TestValidateExpiryDate:
    """Tests for expiry date validation."""

    def test_valid_future_date(self):
        """Test valid future expiry date."""
        # Use a date that's definitely in the future
        is_valid, error = PaymentValidationService.validate_expiry_date(12, 2030)
        assert is_valid is True
        assert error is None

    def test_invalid_month_zero(self):
        """Test month 0 is invalid."""
        is_valid, error = PaymentValidationService.validate_expiry_date(0, 2030)
        assert is_valid is False
        assert "month" in error.lower()

    def test_invalid_month_thirteen(self):
        """Test month 13 is invalid."""
        is_valid, error = PaymentValidationService.validate_expiry_date(13, 2030)
        assert is_valid is False
        assert "month" in error.lower()

    def test_invalid_year_past(self):
        """Test past year is invalid."""
        is_valid, error = PaymentValidationService.validate_expiry_date(12, 2020)
        assert is_valid is False
        # Could be "year" validation error or "expired" error
        assert error is not None

    def test_invalid_year_too_far_future(self):
        """Test year too far in future is invalid."""
        is_valid, error = PaymentValidationService.validate_expiry_date(12, 2150)
        assert is_valid is False
        assert "year" in error.lower()


class TestValidateCVV:
    """Tests for CVV validation."""

    def test_valid_3_digit_cvv(self):
        """Test valid 3-digit CVV for non-AMEX cards."""
        is_valid, error = PaymentValidationService.validate_cvv("123")
        assert is_valid is True
        assert error is None

    def test_valid_4_digit_cvv_amex(self):
        """Test valid 4-digit CVV for AMEX."""
        is_valid, error = PaymentValidationService.validate_cvv("1234", card_brand="amex")
        assert is_valid is True
        assert error is None

    def test_invalid_cvv_non_digits(self):
        """Test CVV with non-digits fails."""
        is_valid, error = PaymentValidationService.validate_cvv("12A")
        assert is_valid is False
        assert "digits" in error.lower()

    def test_invalid_cvv_wrong_length(self):
        """Test CVV with wrong length fails."""
        is_valid, error = PaymentValidationService.validate_cvv("12")
        assert is_valid is False
        assert "3 digits" in error.lower()

    def test_invalid_amex_cvv_3_digits(self):
        """Test AMEX CVV must be 4 digits."""
        is_valid, error = PaymentValidationService.validate_cvv("123", card_brand="amex")
        assert is_valid is False
        assert "4 digits" in error.lower()


class TestGetCardLast4:
    """Tests for extracting last 4 digits."""

    def test_get_last_4(self):
        """Test getting last 4 digits."""
        last4 = PaymentValidationService.get_card_last4("4532015112830366")
        assert last4 == "0366"

    def test_get_last_4_with_spaces(self):
        """Test getting last 4 with spaces in number."""
        last4 = PaymentValidationService.get_card_last4("4532 0151 1283 0366")
        assert last4 == "0366"

    def test_get_last_4_short_number(self):
        """Test getting last 4 with short number returns full number."""
        last4 = PaymentValidationService.get_card_last4("123")
        assert last4 == "123"


class TestMaskCardNumber:
    """Tests for card number masking."""

    def test_mask_card_number(self):
        """Test masking card number."""
        masked = PaymentValidationService.mask_card_number("4532015112830366")
        assert masked == "************0366"
        assert len(masked) == 16

    def test_mask_card_number_with_spaces(self):
        """Test masking card number with spaces."""
        masked = PaymentValidationService.mask_card_number("4532 0151 1283 0366")
        assert masked.endswith("0366")
        assert "*" in masked

    def test_mask_card_show_last_6(self):
        """Test masking with custom last digits count."""
        masked = PaymentValidationService.mask_card_number("4532015112830366", show_last=6)
        assert masked == "**********830366"

    def test_mask_short_number(self):
        """Test masking very short number returns all asterisks when length <= show_last."""
        masked = PaymentValidationService.mask_card_number("1234", show_last=4)
        # When length <= show_last, the implementation masks everything
        assert masked == "****"


class TestValidateFullCardInfo:
    """Tests for full card information validation."""

    def test_valid_full_card_info(self):
        """Test valid complete card info."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="4532015112830366",
            exp_month=12,
            exp_year=2030,
            cvv="123",
            cardholder_name="John Doe"
        )
        assert is_valid is True
        assert error is None
        assert card_info is not None
        assert card_info["brand"] == "visa"
        assert card_info["last4"] == "0366"
        assert card_info["exp_month"] == 12
        assert card_info["exp_year"] == 2030

    def test_valid_card_no_name(self):
        """Test valid card without cardholder name."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="4532015112830366",
            exp_month=12,
            exp_year=2030,
            cvv="123"
        )
        assert is_valid is True
        assert error is None
        assert card_info is not None

    def test_invalid_card_number_fails_full_validation(self):
        """Test invalid card number fails full validation."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="1234567890123456",
            exp_month=12,
            exp_year=2030,
            cvv="123"
        )
        assert is_valid is False
        assert error is not None
        assert card_info is None

    def test_invalid_expiry_fails_full_validation(self):
        """Test invalid expiry fails full validation."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="4532015112830366",
            exp_month=13,  # Invalid month
            exp_year=2030,
            cvv="123"
        )
        assert is_valid is False
        assert "month" in error.lower()
        assert card_info is None

    def test_invalid_cvv_fails_full_validation(self):
        """Test invalid CVV fails full validation."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="4532015112830366",
            exp_month=12,
            exp_year=2030,
            cvv="12"  # Too short
        )
        assert is_valid is False
        assert "cvv" in error.lower()
        assert card_info is None

    def test_invalid_cardholder_name_too_short(self):
        """Test cardholder name too short fails."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="4532015112830366",
            exp_month=12,
            exp_year=2030,
            cvv="123",
            cardholder_name="J"  # Too short
        )
        assert is_valid is False
        assert "name" in error.lower()
        assert card_info is None

    def test_amex_card_with_4_digit_cvv(self):
        """Test AMEX card requires 4-digit CVV in full validation."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="374245455400126",  # AMEX
            exp_month=12,
            exp_year=2030,
            cvv="1234"  # 4-digit CVV
        )
        assert is_valid is True
        assert card_info["brand"] == "amex"

    def test_amex_card_with_3_digit_cvv_fails(self):
        """Test AMEX card with 3-digit CVV fails."""
        is_valid, error, card_info = PaymentValidationService.validate_full_card_info(
            card_number="374245455400126",  # AMEX
            exp_month=12,
            exp_year=2030,
            cvv="123"  # 3-digit CVV, should be 4 for AMEX
        )
        assert is_valid is False
        assert "4 digits" in error.lower()

