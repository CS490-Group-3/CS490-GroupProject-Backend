"""
Unit tests for error logging middleware.
"""
import pytest
from unittest.mock import Mock, patch
from flask import Flask, g
from middleware.error_logging import auto_log_errors, log_route_error, log_service_error


def test_auto_log_errors_decorator(monkeypatch):
    """Test auto_log_errors decorator logs exceptions."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    logged_exception = None
    
    def fake_log_route_error(*args, **kwargs):
        """Mock log_route_error which is called by the decorator."""
        nonlocal logged_exception
        logged_exception = args[0] if args else None
    
    # Mock log_route_error which is called inside the decorator
    monkeypatch.setattr("middleware.error_logging.log_route_error", fake_log_route_error)
    
    @app.route('/test')
    @auto_log_errors
    def test_route():
        raise ValueError("Test error")
    
    # Add error handler to catch the exception
    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def handle_error(e):
        return "Error", 500
    
    with app.test_client() as client:
        # The decorator logs then re-raises, Flask's error handler catches it
        try:
            response = client.get('/test')
        except ValueError:
            # Exception was re-raised as expected by decorator
            pass
    
    # Exception should have been logged before re-raising
    # The decorator calls log_route_error which should log the exception
    assert logged_exception is not None
    assert isinstance(logged_exception, ValueError)


def test_log_route_error(monkeypatch):
    """Test log_route_error helper function."""
    logged = False
    
    def fake_log(*args, **kwargs):
        nonlocal logged
        logged = True
    
    monkeypatch.setattr("services.error_logging_service.ErrorLoggingService.log_exception", fake_log)
    
    app = Flask(__name__)
    with app.test_request_context():
        g.user = {"sub": "user-123"}
        log_route_error(ValueError("Test"), severity="high")
    
    assert logged is True


def test_log_service_error(monkeypatch):
    """Test log_service_error helper function."""
    logged = False
    
    def fake_log(*args, **kwargs):
        nonlocal logged
        logged = True
    
    monkeypatch.setattr("services.error_logging_service.ErrorLoggingService.log_error", fake_log)
    
    app = Flask(__name__)
    with app.test_request_context():
        g.user = {"sub": "user-123"}
        log_service_error("Service error occurred", severity="medium")
    
    assert logged is True

