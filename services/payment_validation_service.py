"""
Payment validation service using Luhn's algorithm and card type detection.
This service validates card numbers without processing real payments.
"""
import re
from typing import Dict, Optional, Tuple


class PaymentValidationService:
    """Service for validating payment card information."""
    
    # Card brand patterns (first digits)
    CARD_PATTERNS = {
        'visa': r'^4',
        'mastercard': r'^5[1-5]',
        'amex': r'^3[47]',
        'discover': r'^6(?:011|5)',
        'diners': r'^3[068]',
        'jcb': r'^35',
        'unionpay': r'^62',
    }
    
    @staticmethod
    def validate_card_number(card_number: str) -> Tuple[bool, Optional[str]]:
        """
        Validate card number using Luhn's algorithm.
        
        Args:
            card_number: Card number as string (spaces/dashes will be removed)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Remove spaces and dashes
        card_number = re.sub(r'[\s-]', '', card_number)
        
        # Check if it's all digits
        if not card_number.isdigit():
            return False, "Card number must contain only digits"
        
        # Check length (13-19 digits for most cards)
        if len(card_number) < 13 or len(card_number) > 19:
            return False, "Card number must be between 13 and 19 digits"
        
        # Luhn's algorithm
        def luhn_check(card_num: str) -> bool:
            """Luhn's algorithm implementation."""
            # Reverse the card number
            reversed_digits = card_num[::-1]
            
            total = 0
            for i, digit in enumerate(reversed_digits):
                n = int(digit)
                
                # Double every second digit
                if i % 2 == 1:
                    n *= 2
                    # If doubling results in two-digit number, add the digits
                    if n > 9:
                        n = (n // 10) + (n % 10)
                
                total += n
            
            # Card is valid if total is divisible by 10
            return total % 10 == 0
        
        is_valid = luhn_check(card_number)
        
        if not is_valid:
            return False, "Invalid card number (failed Luhn's algorithm check)"
        
        return True, None
    
    @staticmethod
    def detect_card_brand(card_number: str) -> str:
        """
        Detect card brand from card number.
        
        Args:
            card_number: Card number as string (spaces/dashes will be removed)
        
        Returns:
            Card brand: 'visa', 'mastercard', 'amex', 'discover', 'diners', 'jcb', 'unionpay', or 'unknown'
        """
        # Remove spaces and dashes
        card_number = re.sub(r'[\s-]', '', card_number)
        
        # Check each pattern
        for brand, pattern in PaymentValidationService.CARD_PATTERNS.items():
            if re.match(pattern, card_number):
                return brand
        
        return 'unknown'
    
    @staticmethod
    def validate_expiry_date(exp_month: int, exp_year: int) -> Tuple[bool, Optional[str]]:
        """
        Validate expiration date.
        
        Args:
            exp_month: Expiration month (1-12)
            exp_year: Expiration year (4 digits)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        from datetime import datetime
        
        # Validate month
        if exp_month < 1 or exp_month > 12:
            return False, "Expiration month must be between 1 and 12"
        
        # Validate year format
        if exp_year < 2024 or exp_year > 2099:
            return False, "Expiration year must be between 2024 and 2099"
        
        # Check if card is expired
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        
        if exp_year < current_year:
            return False, "Card has expired"
        
        if exp_year == current_year and exp_month < current_month:
            return False, "Card has expired"
        
        return True, None
    
    @staticmethod
    def validate_cvv(cvv: str, card_brand: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate CVV (Card Verification Value).
        
        Args:
            cvv: CVV as string
            card_brand: Optional card brand (AMEX uses 4 digits, others use 3)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not cvv.isdigit():
            return False, "CVV must contain only digits"
        
        # AMEX uses 4-digit CVV, others use 3-digit
        if card_brand == 'amex':
            if len(cvv) != 4:
                return False, "CVV for American Express must be 4 digits"
        else:
            if len(cvv) != 3:
                return False, "CVV must be 3 digits"
        
        return True, None
    
    @staticmethod
    def get_card_last4(card_number: str) -> str:
        """
        Extract last 4 digits of card number.
        
        Args:
            card_number: Card number as string
        
        Returns:
            Last 4 digits as string
        """
        # Remove spaces and dashes
        card_number = re.sub(r'[\s-]', '', card_number)
        
        if len(card_number) < 4:
            return card_number
        
        return card_number[-4:]
    
    @staticmethod
    def mask_card_number(card_number: str, show_last: int = 4) -> str:
        """
        Mask card number for display (e.g., "****1234").
        
        Args:
            card_number: Card number as string
            show_last: Number of last digits to show (default 4)
        
        Returns:
            Masked card number (e.g., "****1234")
        """
        # Remove spaces and dashes
        card_number = re.sub(r'[\s-]', '', card_number)
        
        if len(card_number) <= show_last:
            return '*' * len(card_number)
        
        return '*' * (len(card_number) - show_last) + card_number[-show_last:]
    
    @staticmethod
    def validate_full_card_info(
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        cardholder_name: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate all card information at once.
        
        Args:
            card_number: Card number as string
            exp_month: Expiration month (1-12)
            exp_year: Expiration year (4 digits)
            cvv: CVV as string
            cardholder_name: Optional cardholder name
        
        Returns:
            Tuple of (is_valid, error_message, card_info_dict)
            card_info_dict contains: brand, last4, masked_number
        """
        # Validate card number
        is_valid, error = PaymentValidationService.validate_card_number(card_number)
        if not is_valid:
            return False, error, None
        
        # Detect card brand
        brand = PaymentValidationService.detect_card_brand(card_number)
        
        # Validate expiry
        is_valid, error = PaymentValidationService.validate_expiry_date(exp_month, exp_year)
        if not is_valid:
            return False, error, None
        
        # Validate CVV (with brand for AMEX)
        is_valid, error = PaymentValidationService.validate_cvv(cvv, brand)
        if not is_valid:
            return False, error, None
        
        # Validate cardholder name (if provided)
        if cardholder_name:
            cardholder_name = cardholder_name.strip()
            if len(cardholder_name) < 2:
                return False, "Cardholder name must be at least 2 characters", None
            if len(cardholder_name) > 100:
                return False, "Cardholder name must be less than 100 characters", None
        
        # Extract card info
        last4 = PaymentValidationService.get_card_last4(card_number)
        masked = PaymentValidationService.mask_card_number(card_number)
        
        card_info = {
            'brand': brand,
            'last4': last4,
            'masked_number': masked,
            'exp_month': exp_month,
            'exp_year': exp_year
        }
        
        return True, None, card_info

