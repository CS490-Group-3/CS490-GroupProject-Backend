"""
Unit tests for ProductService.
Tests actual service logic by mocking Supabase dependencies.
"""
import pytest
from unittest.mock import Mock
from models.products import ProductCreateRequest, ProductUpdateRequest, ProductCategoryCreateRequest
from services.product_service import ProductService


def test_get_product_success(monkeypatch):
    """Test getting a product by ID - tests real service logic."""
    mock_product = {
        "id": "product-123",
        "name": "Hair Gel",
        "price": "15.99",
        "salon_id": "salon-1"
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_product
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
    
    # Test REAL ProductService.get_product() method
    product, error = ProductService.get_product("product-123")
    
    assert error is None
    assert product["id"] == "product-123"
    assert product["name"] == "Hair Gel"


def test_get_product_not_found(monkeypatch):
    """Test getting a non-existent product - tests real error handling."""
    # Mock Supabase response with no data
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
    
    # Test REAL ProductService.get_product() method
    product, error = ProductService.get_product("nonexistent")
    
    assert product is None
    assert error == "Product not found"


def test_create_product_success(monkeypatch):
    """Test creating a product - tests real service logic."""
    mock_created_product = {
        "id": "product-123",
        "name": "Hair Gel",
        "price": "15.99",
        "salon_id": "salon-1"
    }
    
    # Mock Supabase insert response
    mock_response = Mock()
    mock_response.data = [mock_created_product]
    mock_response.error = None
    
    class MockTable:
        def insert(self, data):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ProductService.create_product() method
    product_data = ProductCreateRequest(
        salon_id="salon-1",
        name="Hair Gel",
        price="15.99"
    )
    
    product, error = ProductService.create_product(product_data)
    
    assert error is None
    assert product["name"] == "Hair Gel"
    assert product["id"] == "product-123"


def test_list_products_success(monkeypatch):
    """Test listing products - tests real service logic."""
    mock_products = [
        {"id": "product-1", "name": "Hair Gel", "price": "15.99", "category_id": None, "product_categories": None},
        {"id": "product-2", "name": "Shampoo", "price": "12.99", "category_id": None, "product_categories": None}
    ]
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_products
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
    
    # Test REAL ProductService.list_products() method
    products, error = ProductService.list_products(salon_id="salon-1")
    
    assert error is None
    assert len(products) == 2
    assert products[0]["name"] == "Hair Gel"


def test_update_product_success(monkeypatch):
    """Test updating a product - tests real service logic."""
    mock_updated_product = {
        "id": "product-123",
        "name": "Updated Hair Gel",
        "price": "18.99"
    }
    
    # Mock Supabase update response
    mock_response = Mock()
    mock_response.data = [mock_updated_product]
    mock_response.error = None
    
    class MockTable:
        def update(self, data):
            return self
        def eq(self, *args, **kwargs):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ProductService.update_product() method
    update_data = ProductUpdateRequest(price="18.99")
    
    product, error = ProductService.update_product("product-123", update_data)
    
    assert error is None
    assert product["price"] == "18.99"


def test_list_product_categories_success(monkeypatch):
    """Test listing product categories - tests real service logic."""
    mock_categories = [
        {"id": "cat-1", "name": "Hair Care"},
        {"id": "cat-2", "name": "Styling Products"}
    ]
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = mock_categories
    mock_response.error = None
    
    class MockTable:
        def select(self, *args):
            return self
        def execute(self):
            return mock_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ProductService.list_product_categories() method
    categories, error = ProductService.list_product_categories()
    
    assert error is None
    assert len(categories) == 2
    assert categories[0]["name"] == "Hair Care"


def test_get_category_success(monkeypatch):
    """Test getting a category by ID - tests real service logic."""
    mock_category = {
        "id": "cat-1",
        "name": "Hair Care"
    }
    
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [mock_category]
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
    
    # Test REAL ProductService.get_category() method
    category, error = ProductService.get_category("cat-1")
    
    assert error is None
    assert category[0]["name"] == "Hair Care"


def test_create_product_category_success(monkeypatch):
    """Test creating a product category - tests real service logic."""
    mock_category = {
        "id": "cat-123",
        "name": "New Category"
    }
    
    # Mock Supabase responses (check + insert)
    check_response = Mock()
    check_response.data = []  # No existing category
    
    insert_response = Mock()
    insert_response.data = [mock_category]
    insert_response.error = None
    
    call_count = [0]
    
    class MockTable:
        def select(self, *args):
            return self
        def ilike(self, *args, **kwargs):
            return self
        def eq(self, *args, **kwargs):
            return self
        def insert(self, data):
            return self
        def execute(self):
            call_count[0] += 1
            if call_count[0] == 1:
                return check_response
            return insert_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ProductService.create_product_category() method
    category_data = ProductCategoryCreateRequest(name="New Category")
    
    category, error = ProductService.create_product_category(category_data)
    
    assert error is None
    assert category["name"] == "New Category"


def test_create_product_category_duplicate(monkeypatch):
    """Test creating duplicate category - tests real validation logic."""
    # Mock Supabase check response - category already exists
    check_response = Mock()
    check_response.data = [{"id": "cat-1", "name": "New Category"}]
    
    class MockTable:
        def select(self, *args):
            return self
        def ilike(self, *args, **kwargs):
            return self
        def execute(self):
            return check_response
    
    def fake_table(name):
        return MockTable()
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    # Test REAL ProductService.create_product_category() method
    category_data = ProductCategoryCreateRequest(name="New Category")
    
    category, error = ProductService.create_product_category(category_data)
    
    assert category is None
    assert "already exists" in error
