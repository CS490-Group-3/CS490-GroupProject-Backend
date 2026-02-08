"""
Unit tests for PromotionService.
Tests promotional offer creation, retrieval, updates, and discount calculations.
"""
import pytest
from unittest.mock import Mock, patch
from services.promotion_service import PromotionService


class TestCreateOffer:
    """Tests for creating promotional offers."""

    def test_create_offer_success(self, monkeypatch):
        """Test successfully creating a promotional offer."""
        mock_response = Mock()
        mock_response.data = [{"id": "promo-123"}]
        mock_response.error = None

        class MockTable:
            def insert(self, data):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.notification_service.NotificationService.notify_promotional_offer", Mock())
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        data = {
            "title": "Summer Sale",
            "description": "20% off all services",
            "discount_type": "percentage",
            "discount_value": 20,
            "valid_from": "2024-06-01",
            "valid_until": "2024-08-31"
        }

        result = PromotionService.create_offer("salon-1", data)

        assert "offer_id" in result
        assert "message" in result

    def test_create_offer_missing_fields(self, monkeypatch):
        """Test creating offer with missing required fields raises ValueError."""
        data = {
            "title": "Summer Sale",
            # Missing other required fields
        }

        with pytest.raises(ValueError) as exc_info:
            PromotionService.create_offer("salon-1", data)
        
        assert "Missing fields" in str(exc_info.value)

    def test_create_offer_with_optional_fields(self, monkeypatch):
        """Test creating offer with optional targeting fields."""
        mock_response = Mock()
        mock_response.data = [{"id": "promo-123"}]
        mock_response.error = None

        class MockTable:
            def insert(self, data):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.notification_service.NotificationService.notify_promotional_offer", Mock())
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        data = {
            "title": "VIP Sale",
            "description": "Special discount for loyal customers",
            "discount_type": "fixed_amount",
            "discount_value": 50,
            "valid_from": "2024-06-01",
            "valid_until": "2024-08-31",
            "min_purchase_amount": 100,
            "target_audience": "vip_customers",
            "min_visits": 10,
            "min_loyalty_points": 500,
            "targeting_logic": "or"
        }

        result = PromotionService.create_offer("salon-1", data)
        assert "offer_id" in result


class TestGetSalonPromotions:
    """Tests for retrieving salon promotions."""

    def test_get_salon_promotions_success(self, monkeypatch):
        """Test successfully getting salon promotions."""
        mock_promos = [
            {"id": "promo-1", "title": "Summer Sale"},
            {"id": "promo-2", "title": "Winter Special"}
        ]

        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    if call_count[0] == 1:
                        mock_response.data = mock_promos
                    else:
                        # Recipient count queries
                        mock_response.data = []
                        mock_response.count = 5
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        promotions, error = PromotionService.get_salon_promotions("salon-1")

        assert error is None
        assert len(promotions) == 2
        assert promotions[0]["title"] == "Summer Sale"

    def test_get_salon_promotions_empty(self, monkeypatch):
        """Test getting promotions when none exist."""
        mock_response = Mock()
        mock_response.data = []
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def order(self, *args, **kwargs):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        promotions, error = PromotionService.get_salon_promotions("salon-1")

        assert error is None
        assert promotions == []

    def test_get_salon_promotions_error(self, monkeypatch):
        """Test handling database errors."""
        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    raise Exception("Database connection error")
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.error_logging_service.ErrorLoggingService.log_exception", Mock())

        promotions, error = PromotionService.get_salon_promotions("salon-1")

        assert error is not None
        assert "Failed to get promotions" in error
        assert promotions == []


class TestUpdatePromotion:
    """Tests for updating promotional offers."""

    def test_update_promotion_success(self, monkeypatch):
        """Test successfully updating a promotion."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
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
                        # Ownership check
                        mock_response.data = {"id": "promo-123"}
                    else:
                        # Update
                        mock_response.data = [{"id": "promo-123", "title": "Updated Title"}]
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        updated, error = PromotionService.update_promotion(
            "promo-123", 
            "salon-1", 
            {"title": "Updated Title"}
        )

        assert error is None
        assert updated is not None
        assert updated["title"] == "Updated Title"

    def test_update_promotion_not_found(self, monkeypatch):
        """Test updating non-existent promotion."""
        mock_response = Mock()
        mock_response.data = None
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
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

        updated, error = PromotionService.update_promotion(
            "promo-nonexistent",
            "salon-1",
            {"title": "Updated Title"}
        )

        assert error == "Promotion not found or unauthorized"
        assert updated is None

    def test_update_promotion_no_valid_fields(self, monkeypatch):
        """Test updating with no valid fields."""
        mock_response = Mock()
        mock_response.data = {"id": "promo-123"}
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
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

        updated, error = PromotionService.update_promotion(
            "promo-123",
            "salon-1",
            {"invalid_field": "value"}  # No valid fields
        )

        assert error == "No valid fields to update"
        assert updated is None


class TestDeletePromotion:
    """Tests for deleting promotional offers."""

    def test_delete_promotion_success(self, monkeypatch):
        """Test successfully deleting a promotion."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def single(self):
                    return self
                def delete(self):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    if call_count[0] == 1:
                        # Ownership check
                        mock_response.data = {"id": "promo-123"}
                    else:
                        # Delete
                        mock_response.data = []
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)
        monkeypatch.setattr("services.audit_logging_service.AuditLoggingService.log_audit", Mock())

        success, error = PromotionService.delete_promotion("promo-123", "salon-1")

        assert success is True
        assert error is None

    def test_delete_promotion_not_found(self, monkeypatch):
        """Test deleting non-existent promotion."""
        mock_response = Mock()
        mock_response.data = None
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
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

        success, error = PromotionService.delete_promotion("promo-nonexistent", "salon-1")

        assert success is False
        assert error == "Promotion not found or unauthorized"


class TestGetActivePromotions:
    """Tests for getting active promotions."""

    def test_get_active_promotions_success(self, monkeypatch):
        """Test getting active promotions."""
        mock_promos = [
            {"id": "promo-1", "title": "Summer Sale", "min_purchase_amount": 50}
        ]

        mock_response = Mock()
        mock_response.data = mock_promos
        mock_response.error = None

        class MockTable:
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def lte(self, *args, **kwargs):
                return self
            def gte(self, *args, **kwargs):
                return self
            def order(self, *args, **kwargs):
                return self
            def execute(self):
                return mock_response

        def fake_table(name):
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        promotions, error = PromotionService.get_active_promotions("salon-1")

        assert error is None
        assert len(promotions) == 1

    def test_get_active_promotions_with_user_eligibility(self, monkeypatch):
        """Test getting promotions filtered by user eligibility."""
        call_count = [0]

        def fake_table(name):
            class MockTable:
                def select(self, *args, **kwargs):
                    return self
                def eq(self, *args, **kwargs):
                    return self
                def lte(self, *args, **kwargs):
                    return self
                def gte(self, *args, **kwargs):
                    return self
                def order(self, *args, **kwargs):
                    return self
                def execute(self):
                    call_count[0] += 1
                    mock_response = Mock()
                    mock_response.error = None
                    if call_count[0] == 1:
                        # Promotions query
                        mock_response.data = [
                            {"id": "promo-1", "title": "Summer Sale"},
                            {"id": "promo-2", "title": "VIP Only"}
                        ]
                    else:
                        # Recipients query
                        mock_response.data = [{"offer_id": "promo-1"}]
                    return mock_response
            return MockTable()

        monkeypatch.setattr("config.supabase.table", fake_table)

        promotions, error = PromotionService.get_active_promotions("salon-1", user_id="user-123")

        assert error is None
        # User is only eligible for promo-1
        assert len(promotions) == 1
        assert promotions[0]["id"] == "promo-1"


class TestCalculateDiscount:
    """Tests for discount calculations."""

    def test_calculate_percentage_discount(self):
        """Test percentage discount calculation."""
        promotion = {"discount_type": "percentage", "discount_value": 20}
        
        discount = PromotionService.calculate_discount(promotion, 100.0)
        
        assert discount == 20.0

    def test_calculate_fixed_amount_discount(self):
        """Test fixed amount discount calculation."""
        promotion = {"discount_type": "fixed_amount", "discount_value": 15}
        
        discount = PromotionService.calculate_discount(promotion, 100.0)
        
        assert discount == 15.0

    def test_calculate_fixed_discount_caps_at_amount(self):
        """Test fixed discount doesn't exceed purchase amount."""
        promotion = {"discount_type": "fixed_amount", "discount_value": 50}
        
        discount = PromotionService.calculate_discount(promotion, 30.0)
        
        # Discount should be capped at purchase amount
        assert discount == 30.0

    def test_calculate_discount_unknown_type(self):
        """Test unknown discount type returns 0."""
        promotion = {"discount_type": "unknown", "discount_value": 20}
        
        discount = PromotionService.calculate_discount(promotion, 100.0)
        
        assert discount == 0.0

    def test_calculate_discount_rounds_to_2_decimals(self):
        """Test discount is rounded to 2 decimal places."""
        promotion = {"discount_type": "percentage", "discount_value": 33}
        
        discount = PromotionService.calculate_discount(promotion, 100.0)
        
        assert discount == 33.0
        # Test with amount that would produce more decimals
        discount = PromotionService.calculate_discount(promotion, 10.0)
        assert discount == 3.3

    def test_calculate_discount_handles_missing_value(self):
        """Test handling promotion with missing discount value."""
        promotion = {"discount_type": "percentage"}  # No discount_value
        
        discount = PromotionService.calculate_discount(promotion, 100.0)
        
        assert discount == 0.0

