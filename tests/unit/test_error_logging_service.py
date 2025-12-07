"""
Unit tests for ErrorLoggingService.
"""
import pytest
from unittest.mock import Mock, patch
from services.error_logging_service import ErrorLoggingService


def test_log_error_success(monkeypatch):
    """Test logging an error."""
    mock_response = Mock()
    mock_response.data = [{"id": "error-123"}]
    mock_response.error = None  # Important: error must be None for success
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result = ErrorLoggingService.log_error(
        error_type="TestError",
        error_message="Test error message",
        severity="medium"
    )
    
    assert result is None  # No error means success


def test_log_exception_success(monkeypatch):
    """Test logging an exception."""
    mock_response = Mock()
    mock_response.data = [{"id": "error-123"}]
    mock_response.error = None
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    exception = ValueError("Test exception")
    result = ErrorLoggingService.log_exception(
        exception=exception,
        severity="high"
    )
    
    assert result is None


def test_log_error_with_user_id(monkeypatch):
    """Test logging error with user ID."""
    mock_response = Mock()
    mock_response.data = [{"id": "error-123"}]
    mock_response.error = None
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result = ErrorLoggingService.log_error(
        error_type="TestError",
        error_message="Test error",
        user_id="user-123",
        severity="high"
    )
    
    assert result is None
