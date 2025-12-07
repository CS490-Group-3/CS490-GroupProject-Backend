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

