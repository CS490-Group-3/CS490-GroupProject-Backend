"""
Unit tests for StorageService.
"""
import pytest
from unittest.mock import Mock, MagicMock
from services.upload_file import StorageService


def test_upload_file_success(monkeypatch):
    """Test uploading a file."""
    mock_file = Mock()
    mock_file.filename = "test.jpg"
    mock_file.mimetype = "image/jpeg"
    mock_file.read.return_value = b"fake file content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/file.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_file(
        file=mock_file,
        salon_id="salon-123",
        file_type="logo"
    )
    
    assert "signed_url" in result
    assert "filepath" in result
    assert result["signed_url"] == "https://example.com/file.jpg"


def test_upload_license_file(monkeypatch):
    """Test uploading a license file."""
    mock_file = Mock()
    mock_file.filename = "license.pdf"
    mock_file.mimetype = "application/pdf"
    mock_file.read.return_value = b"fake pdf content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/license.pdf"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_file(
        file=mock_file,
        salon_id="salon-123",
        file_type="license"
    )
    
    assert result["signed_url"] == "https://example.com/license.pdf"


def test_upload_product_file(monkeypatch):
    """Test uploading a product file."""
    mock_file = Mock()
    mock_file.filename = "product.jpg"
    mock_file.mimetype = "image/jpeg"
    mock_file.read.return_value = b"fake image content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/product.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_file(
        file=mock_file,
        salon_id="salon-123",
        file_type="product"
    )
    
    assert result["signed_url"] == "https://example.com/product.jpg"


def test_upload_file_unknown_type(monkeypatch):
    """Test uploading file with unknown type defaults to salon-documents."""
    mock_file = Mock()
    mock_file.filename = "unknown.txt"
    mock_file.mimetype = "text/plain"
    mock_file.read.return_value = b"fake content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/unknown.txt"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_file(
        file=mock_file,
        salon_id="salon-123",
        file_type="unknown"
    )
    
    assert result["signed_url"] == "https://example.com/unknown.txt"


def test_upload_file_no_mimetype(monkeypatch):
    """Test uploading file without mimetype."""
    mock_file = Mock()
    mock_file.filename = "file.bin"
    mock_file.mimetype = None
    mock_file.read.return_value = b"fake content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/file.bin"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_file(
        file=mock_file,
        salon_id="salon-123",
        file_type="logo"
    )
    
    assert result["signed_url"] == "https://example.com/file.bin"


def test_regenerate_signed_url_success(monkeypatch):
    """Test regenerating signed URL."""
    mock_storage = Mock()
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/new-url.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.regenerate_signed_url("salon-123/logo/image.jpg")
    
    assert result == "https://example.com/new-url.jpg"


def test_regenerate_signed_url_custom_expiry(monkeypatch):
    """Test regenerating signed URL with custom expiry."""
    mock_storage = Mock()
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/new-url.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.regenerate_signed_url("salon-123/logo/image.jpg", expires_in_days=30)
    
    assert result == "https://example.com/new-url.jpg"


def test_regenerate_signed_url_custom_bucket(monkeypatch):
    """Test regenerating signed URL with custom bucket."""
    mock_storage = Mock()
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/new-url.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.regenerate_signed_url("path/to/file.jpg", BUCKET_NAME="custom-bucket")
    
    assert result == "https://example.com/new-url.jpg"


def test_upload_review_image_success(monkeypatch):
    """Test uploading review image."""
    mock_file = Mock()
    mock_file.filename = "review.jpg"
    mock_file.mimetype = "image/jpeg"
    mock_file.read.return_value = b"fake image content"
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    mock_storage.create_signed_url.return_value = {"signedURL": "https://example.com/review.jpg"}
    
    def fake_from(bucket):
        return mock_storage
    
    monkeypatch.setattr("config.supabase.storage.from_", fake_from)
    
    result = StorageService.upload_review_image(
        file=mock_file,
        review_id="review-123",
        user_id="user-123"
    )
    
    assert "signed_url" in result
    assert result["signed_url"] == "https://example.com/review.jpg"

