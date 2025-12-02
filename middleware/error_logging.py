"""
Error logging utilities for routes.
Provides helper functions and decorators to log errors automatically.
"""
from functools import wraps
from flask import request, g
from services.error_logging_service import ErrorLoggingService


def log_route_error(exception: Exception, severity: str = 'high'):
    """
    Helper function to log errors in route exception handlers.
    Call this in your except blocks to ensure errors are logged.
    
    Example:
        @app.route('/endpoint')
        def my_route():
            try:
                # code that might fail
                pass
            except Exception as e:
                log_route_error(e)  # Log the error
                return jsonify({"error": str(e)}), 500
    """
    user_id = None
    try:
        if hasattr(g, 'user') and g.user:
            user_id = g.user.get('sub')
    except:
        pass
    
    ErrorLoggingService.log_exception(
        exception=exception,
        user_id=user_id,
        endpoint=request.path if request else None,
        severity=severity
    )


def log_service_error(error: str, severity: str = 'medium'):
    """
    Helper function to log errors from services that return error tuples.
    Use this when services return (result, error) and error is not None.
    
    Example:
        result, error = SomeService.doSomething()
        if error:
            log_service_error(error)  # Log the error
            return jsonify({"error": error}), 400
    """
    user_id = None
    try:
        if hasattr(g, 'user') and g.user:
            user_id = g.user.get('sub')
    except:
        pass
    
    ErrorLoggingService.log_error(
        error_type='ServiceError',
        error_message=str(error),
        user_id=user_id,
        endpoint=request.path if request else None,
        severity=severity
    )


def auto_log_errors(f):
    """
    Decorator that automatically logs any exceptions raised in the route.
    
    IMPORTANT: This decorator will log exceptions that bubble up from the route.
    If your route has try-except blocks that catch exceptions, those exceptions
    won't be logged by this decorator (they're handled before reaching here).
    
    For routes with try-except blocks, you can either:
    1. Call log_route_error(e) inside your except blocks, OR
    2. Let exceptions bubble up (remove try-except) and let this decorator handle them
    
    Use this decorator on routes to automatically log unhandled errors:
    
    Example:
        @app.route('/endpoint')
        @auto_log_errors
        def my_route():
            # Unhandled exceptions will be logged automatically
            result = some_operation_that_might_fail()
            return jsonify(result), 200
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log the error before re-raising
            # This ensures unhandled exceptions are logged
            log_route_error(e)
            # Mark as logged to prevent duplicate logging in global handlers
            try:
                g.error_logged = True
            except:
                pass
            # Re-raise so Flask's error handlers can still handle it
            raise
    
    return decorated_function

