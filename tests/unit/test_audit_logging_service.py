"""
Unit tests for AuditLoggingService.
"""
import pytest
from unittest.mock import Mock
from services.audit_logging_service import AuditLoggingService


def test_log_audit_insert_success(monkeypatch):
    """Test logging an INSERT audit."""
    mock_response = Mock()
    mock_response.data = [{"id": "audit-123"}]
    mock_response.error = None  # Important: error must be None for success
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result = AuditLoggingService.log_audit(
        table_name="salons",
        record_id="salon-123",
        action="INSERT",
        new_values={"name": "Test Salon"},
        changed_by="user-123"
    )
    
    assert result is None


def test_log_audit_update_success(monkeypatch):
    """Test logging an UPDATE audit."""
    mock_response = Mock()
    mock_response.data = [{"id": "audit-123"}]
    mock_response.error = None
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result = AuditLoggingService.log_audit(
        table_name="salons",
        record_id="salon-123",
        action="UPDATE",
        old_values={"name": "Old Name"},
        new_values={"name": "New Name"},
        changed_by="user-123"
    )
    
    assert result is None


def test_log_audit_delete_success(monkeypatch):
    """Test logging a DELETE audit."""
    mock_response = Mock()
    mock_response.data = [{"id": "audit-123"}]
    mock_response.error = None
    
    def fake_table(name):
        mock_table = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    result = AuditLoggingService.log_audit(
        table_name="salons",
        record_id="salon-123",
        action="DELETE",
        old_values={"name": "Test Salon"},
        changed_by="user-123"
    )
    
    assert result is None
