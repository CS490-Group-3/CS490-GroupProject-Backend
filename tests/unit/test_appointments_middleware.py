"""
Unit tests for appointments middleware.
"""
import pytest
from unittest.mock import Mock
from flask import Flask, g
from middleware.appointments import get_owned_salons


def test_get_owned_salons_success(monkeypatch):
    """Test getting owned salons."""
    mock_salons = [
        {"id": "salon-1", "name": "Salon 1", "owner_id": "owner-123"},
        {"id": "salon-2", "name": "Salon 2", "owner_id": "owner-123"}
    ]
    
    mock_response = Mock()
    mock_response.data = mock_salons
    
    def fake_table(name):
        mock_table = Mock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_response
        return mock_table
    
    monkeypatch.setattr("config.supabase.table", fake_table)
    
    app = Flask(__name__)
    with app.test_request_context():
        g.user = {"sub": "owner-123"}
        salons = get_owned_salons()
    
    assert len(salons) == 2
    assert salons[0]["owner_id"] == "owner-123"


def test_get_owned_salons_no_user(monkeypatch):
    """Test getting owned salons when no user."""
    app = Flask(__name__)
    with app.test_request_context():
        g.user = None
        salons = get_owned_salons()
    
    assert salons == []

