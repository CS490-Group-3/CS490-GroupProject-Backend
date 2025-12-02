"""
Audit Logging Service for logging database changes to the audit_logs table.
"""
from config import supabase
from typing import Optional, Dict, Any
from datetime import datetime


class AuditLoggingService:
    
    @staticmethod
    def log_audit(
        table_name: str,
        record_id: str,
        action: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        changed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        Log an audit event to the audit_logs table.
        
        Args:
            table_name: Name of the table being modified
            record_id: ID of the record being modified
            action: Action type ('INSERT', 'UPDATE', 'DELETE')
            old_values: Previous values (for UPDATE/DELETE)
            new_values: New values (for INSERT/UPDATE)
            changed_by: User ID who made the change
            ip_address: IP address of the requester
            user_agent: User agent string
        
        Returns:
            Error message if logging fails, None otherwise
        """
        try:
            # Get request info if not provided
            try:
                from flask import request as flask_request
                if ip_address is None and flask_request:
                    ip_address = flask_request.remote_addr
                
                if user_agent is None and flask_request:
                    user_agent = flask_request.headers.get('User-Agent', '')[:500]  # Limit length
            except RuntimeError:
                # Not in request context
                pass
            
            audit_data = {
                'table_name': table_name,
                'record_id': str(record_id),
                'action': action,
                'changed_at': datetime.utcnow().isoformat()
            }
            
            if old_values:
                audit_data['old_values'] = old_values
            
            if new_values:
                audit_data['new_values'] = new_values
            
            if changed_by:
                audit_data['changed_by'] = changed_by
            
            if ip_address:
                audit_data['ip_address'] = ip_address
            
            if user_agent:
                audit_data['user_agent'] = user_agent
            
            response = supabase.table('audit_logs').insert(audit_data).execute()
            
            if getattr(response, 'error', None):
                return f"Failed to log audit: {response.error}"
            
            return None
            
        except Exception as e:
            # Don't let logging errors break the app
            print(f"Failed to log audit to database: {e}")
            return None
    
    @staticmethod
    def get_audit_logs(
        table_name: Optional[str] = None,
        record_id: Optional[str] = None,
        action: Optional[str] = None,
        changed_by: Optional[str] = None,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> tuple[list[Dict], Optional[str]]:
        """
        Retrieve audit logs with optional filtering.
        
        Args:
            table_name: Filter by table name
            record_id: Filter by record ID
            action: Filter by action type
            changed_by: Filter by user ID
            limit: Maximum number of logs to return
            start_date: Filter logs from this date (ISO format)
            end_date: Filter logs until this date (ISO format)
        
        Returns:
            Tuple of (audit_logs_list, error_message)
        """
        try:
            query = supabase.table('audit_logs').select('*')
            
            if table_name:
                query = query.eq('table_name', table_name)
            
            if record_id:
                query = query.eq('record_id', record_id)
            
            if action:
                query = query.eq('action', action)
            
            if changed_by:
                query = query.eq('changed_by', changed_by)
            
            if start_date:
                query = query.gte('changed_at', start_date)
            
            if end_date:
                query = query.lte('changed_at', end_date)
            
            query = query.order('changed_at', desc=True).limit(limit)
            
            response = query.execute()
            
            if getattr(response, 'error', None):
                return [], f"Failed to retrieve audit logs: {response.error}"
            
            return response.data or [], None
            
        except Exception as e:
            return [], f"Error retrieving audit logs: {str(e)}"

