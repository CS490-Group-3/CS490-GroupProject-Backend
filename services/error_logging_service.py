"""
Error Logging Service for logging errors to the error_logs table.
"""
from config import supabase
from typing import Optional, Dict
from datetime import datetime
import traceback


class ErrorLoggingService:
    
    @staticmethod
    def log_error(
        error_type: str,
        error_message: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        severity: str = 'medium',
        stack_trace: Optional[str] = None
    ) -> Optional[str]:
        """
        Log an error to the error_logs table.
        
        Args:
            error_type: Type/category of error (e.g., 'DatabaseError', 'ValidationError')
            error_message: Human-readable error message
            user_id: Optional user ID if error is user-specific
            endpoint: Optional endpoint where error occurred
            severity: Error severity ('low', 'medium', 'high', 'critical')
            stack_trace: Optional stack trace string
        
        Returns:
            Error message if logging fails, None otherwise
        """
        try:
            # Get endpoint from request if not provided
            try:
                from flask import request as flask_request
                if endpoint is None and flask_request:
                    endpoint = flask_request.path
            except RuntimeError:
                # Not in request context
                pass
            
            error_data = {
                'error_type': error_type,
                'error_message': error_message[:1000],  # Limit message length
                'severity': severity,
                'created_at': datetime.utcnow().isoformat()
            }
            
            if user_id:
                error_data['user_id'] = user_id
            
            if endpoint:
                error_data['endpoint'] = endpoint[:200]  # Limit endpoint length
            
            if stack_trace:
                error_data['stack_trace'] = stack_trace[:5000]  # Limit stack trace length
            
            response = supabase.table('error_logs').insert(error_data).execute()
            
            if getattr(response, 'error', None):
                return f"Failed to log error: {response.error}"
            
            return None
            
        except Exception as e:
            # Don't let logging errors break the app
            print(f"Failed to log error to database: {e}")
            return None
    
    @staticmethod
    def log_exception(
        exception: Exception,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        severity: str = 'high'
    ) -> Optional[str]:
        """
        Log an exception with full stack trace.
        
        Args:
            exception: The exception object
            user_id: Optional user ID
            endpoint: Optional endpoint
            severity: Error severity
        
        Returns:
            Error message if logging fails, None otherwise
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        stack_trace = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        
        return ErrorLoggingService.log_error(
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            endpoint=endpoint,
            severity=severity,
            stack_trace=stack_trace
        )
    
    @staticmethod
    def get_error_logs(
        limit: int = 100,
        severity: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> tuple[list[Dict], Optional[str]]:
        """
        Retrieve error logs with optional filtering.
        
        Args:
            limit: Maximum number of logs to return
            severity: Filter by severity level
            start_date: Filter logs from this date (ISO format)
            end_date: Filter logs until this date (ISO format)
        
        Returns:
            Tuple of (error_logs_list, error_message)
        """
        try:
            query = supabase.table('error_logs').select('*')
            
            if severity:
                query = query.eq('severity', severity)
            
            if start_date:
                query = query.gte('created_at', start_date)
            
            if end_date:
                query = query.lte('created_at', end_date)
            
            query = query.order('created_at', desc=True).limit(limit)
            
            response = query.execute()
            
            if getattr(response, 'error', None):
                return [], f"Failed to retrieve error logs: {response.error}"
            
            return response.data or [], None
            
        except Exception as e:
            return [], f"Error retrieving logs: {str(e)}"

