"""
Analytics Service for calculating and storing platform metrics.
Handles daily statistics, engagement metrics, revenue, loyalty, and retention analytics.
"""
from config import supabase
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta, date
from decimal import Decimal
from services.error_logging_service import ErrorLoggingService
import json


class AnalyticsService:
    
    @staticmethod
    def calculate_daily_statistics(target_date: Optional[date] = None) -> Tuple[Dict, Optional[str]]:
        """
        Calculate and store daily statistics for a given date.
        If no date provided, uses yesterday (to avoid incomplete data for today).
        
        Args:
            target_date: Date to calculate statistics for (default: yesterday)
        
        Returns:
            Tuple of (statistics_data, error_message)
        """
        try:
            if target_date is None:
                target_date = (datetime.now() - timedelta(days=1)).date()
            
            date_str = target_date.isoformat()
            start_of_day = datetime.combine(target_date, datetime.min.time()).isoformat()
            end_of_day = datetime.combine(target_date, datetime.max.time()).isoformat()
            
            # Check if platform-wide statistics already exist for this date (salon_id IS NULL)
            existing = supabase.table('daily_statistics')\
                .select('id')\
                .eq('date', date_str)\
                .is_('salon_id', 'null')\
                .execute()
            
            if existing.data:
                # Update existing record
                stats_id = existing.data[0]['id']
            else:
                stats_id = None
            
            # Calculate metrics (platform-wide, so salon_id is NULL)
            stats = {
                'date': date_str,
                'salon_id': None,  # NULL for platform-wide statistics
                'total_appointments': AnalyticsService._count_total_appointments(start_of_day, end_of_day),
                'completed_appointments': AnalyticsService._count_completed_appointments(start_of_day, end_of_day),
                'cancelled_appointments': AnalyticsService._count_cancelled_appointments(start_of_day, end_of_day),
                'total_revenue': AnalyticsService._calculate_daily_revenue(start_of_day, end_of_day),
                'new_customers': AnalyticsService._count_new_customers(target_date),
                'returning_customers': AnalyticsService._count_returning_customers(start_of_day, end_of_day),
                'average_rating': AnalyticsService._calculate_average_rating(start_of_day, end_of_day),
                'loyalty_points_earned': AnalyticsService._calculate_loyalty_points_earned(start_of_day, end_of_day),
                'loyalty_points_redeemed': AnalyticsService._calculate_loyalty_points_redeemed(start_of_day, end_of_day),
                'created_at': datetime.now().isoformat()
            }
            
            # Store in database
            if stats_id:
                response = supabase.table('daily_statistics')\
                    .update(stats)\
                    .eq('id', stats_id)\
                    .execute()
            else:
                response = supabase.table('daily_statistics')\
                    .insert(stats)\
                    .execute()
            
            if response.data:
                return response.data[0] if isinstance(response.data, list) else response.data, None
            else:
                return stats, None
                
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to calculate daily statistics: {str(e)}"
    
    @staticmethod
    def _count_new_customers(target_date: date) -> int:
        """Count new customers (users with role='customer') created on target date."""
        try:
            start = datetime.combine(target_date, datetime.min.time()).isoformat()
            end = datetime.combine(target_date, datetime.max.time()).isoformat()
            
            response = supabase.table('user_details')\
                .select('id', count='exact')\
                .eq('role', 'customer')\
                .not_.is_('profile_created_at', 'null')\
                .gte('profile_created_at', start)\
                .lt('profile_created_at', end)\
                .execute()
            
            return response.count if hasattr(response, 'count') else len(response.data or [])
        except Exception:
            return 0
    
    @staticmethod
    def _count_total_appointments(start: str, end: str) -> int:
        """Count total appointments (all statuses) in time range."""
        try:
            response = supabase.table('appointments')\
                .select('id', count='exact')\
                .gte('start_at', start)\
                .lt('start_at', end)\
                .execute()
            
            return response.count if hasattr(response, 'count') else len(response.data or [])
        except Exception:
            return 0
    
    @staticmethod
    def _count_completed_appointments(start: str, end: str) -> int:
        """Count appointments completed in time range."""
        try:
            response = supabase.table('appointments')\
                .select('id', count='exact')\
                .eq('status', 'completed')\
                .gte('updated_at', start)\
                .lt('updated_at', end)\
                .execute()
            
            return response.count if hasattr(response, 'count') else len(response.data or [])
        except Exception:
            return 0
    
    @staticmethod
    def _count_cancelled_appointments(start: str, end: str) -> int:
        """Count appointments cancelled in time range."""
        try:
            response = supabase.table('appointments')\
                .select('id', count='exact')\
                .eq('status', 'cancelled')\
                .gte('updated_at', start)\
                .lt('updated_at', end)\
                .execute()
            
            return response.count if hasattr(response, 'count') else len(response.data or [])
        except Exception:
            return 0
    
    @staticmethod
    def _calculate_daily_revenue(start: str, end: str) -> float:
        """Calculate total revenue from completed appointments."""
        try:
            # Get completed appointments with service prices
            appointments = supabase.table('appointments')\
                .select('id, service_id, services:service_id(price)')\
                .eq('status', 'completed')\
                .gte('updated_at', start)\
                .lt('updated_at', end)\
                .execute()
            
            total = 0.0
            if appointments.data:
                for apt in appointments.data:
                    service = apt.get('services')
                    if isinstance(service, dict) and service.get('price'):
                        try:
                            total += float(service['price'])
                        except (ValueError, TypeError):
                            pass
            
            return round(total, 2)
        except Exception:
            return 0.0
    
    @staticmethod
    def _count_returning_customers(start: str, end: str) -> int:
        """Count returning customers (customers with appointments who had previous appointments)."""
        try:
            # Get all customers with appointments in this time range
            appointments_response = supabase.table('appointments')\
                .select('customer_id')\
                .gte('start_at', start)\
                .lt('start_at', end)\
                .execute()
            
            if not appointments_response.data:
                return 0
            
            customer_ids = set(apt.get('customer_id') for apt in appointments_response.data if apt.get('customer_id'))
            
            if not customer_ids:
                return 0
            
            # For each customer, check if they had appointments before this time range
            returning_count = 0
            for customer_id in customer_ids:
                # Check if customer had any appointments before the start date
                prev_appointments = supabase.table('appointments')\
                    .select('id', count='exact')\
                    .eq('customer_id', customer_id)\
                    .lt('start_at', start)\
                    .execute()
                
                if prev_appointments.data or (hasattr(prev_appointments, 'count') and prev_appointments.count > 0):
                    returning_count += 1
            
            return returning_count
        except Exception:
            return 0
    
    @staticmethod
    def _calculate_average_rating(start: str, end: str) -> Optional[float]:
        """Calculate average rating from reviews created in time range."""
        try:
            response = supabase.table('reviews')\
                .select('rating')\
                .gte('created_at', start)\
                .lt('created_at', end)\
                .execute()
            
            if not response.data:
                return None
            
            ratings = [r.get('rating') for r in response.data if r.get('rating') is not None]
            if not ratings:
                return None
            
            avg = sum(ratings) / len(ratings)
            return round(avg, 2)
        except Exception:
            return None
    
    @staticmethod
    def _calculate_loyalty_points_earned(start: str, end: str) -> int:
        """Calculate loyalty points earned in time range."""
        try:
            response = supabase.table('loyalty_transactions')\
                .select('points')\
                .gte('created_at', start)\
                .lt('created_at', end)\
                .gt('points', 0)\
                .execute()
            
            total = 0
            if response.data:
                for trans in response.data:
                    points = trans.get('points', 0)
                    if isinstance(points, (int, float)) and points > 0:
                        total += int(points)
            return total
        except Exception:
            return 0
    
    @staticmethod
    def _calculate_loyalty_points_redeemed(start: str, end: str) -> int:
        """Calculate loyalty points redeemed in time range."""
        try:
            response = supabase.table('loyalty_transactions')\
                .select('points')\
                .gte('created_at', start)\
                .lt('created_at', end)\
                .lt('points', 0)\
                .execute()
            
            total = 0
            if response.data:
                for trans in response.data:
                    points = abs(trans.get('points', 0))
                    if isinstance(points, (int, float)):
                        total += int(points)
            return total
        except Exception:
            return 0
    
    @staticmethod
    def get_engagement_metrics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get engagement metrics for a date range.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()
            
            # Get platform-wide daily statistics for the range (salon_id IS NULL)
            stats = supabase.table('daily_statistics')\
                .select('*')\
                .gte('date', start_str)\
                .lte('date', end_str)\
                .is_('salon_id', 'null')\
                .order('date', desc=False)\
                .execute()
            
            daily_data = stats.data if stats.data else []
            
            # Calculate aggregates
            total_new_customers = sum(d.get('new_customers', 0) for d in daily_data)
            
            # If no daily stats data, fallback to counting customers registered in the date range
            if not daily_data or total_new_customers == 0:
                try:
                    new_customers_response = supabase.table('user_details')\
                        .select('id', count='exact')\
                        .eq('role', 'customer')\
                        .not_.is_('profile_created_at', 'null')\
                        .gte('profile_created_at', start_str)\
                        .lte('profile_created_at', end_str)\
                        .execute()
                    total_new_customers = new_customers_response.count if hasattr(new_customers_response, 'count') else len(new_customers_response.data or [])
                except Exception:
                    total_new_customers = 0
            
            total_appointments = sum(d.get('total_appointments', 0) for d in daily_data)
            total_completed = sum(d.get('completed_appointments', 0) for d in daily_data)
            total_revenue = sum(float(d.get('total_revenue', 0)) for d in daily_data)
            total_returning = sum(d.get('returning_customers', 0) for d in daily_data)
            
            # Calculate averages
            days = len(daily_data) if daily_data else 1
            avg_daily_appointments = total_appointments / days
            avg_daily_revenue = total_revenue / days
            
            # Calculate average rating across all days
            ratings = [d.get('average_rating') for d in daily_data if d.get('average_rating') is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else None
            
            # Calculate engagement rate (returning customers / total customers)
            total_customers_response = supabase.table('user_details')\
                .select('id', count='exact')\
                .eq('role', 'customer')\
                .not_.is_('profile_created_at', 'null')\
                .lte('profile_created_at', end_str)\
                .execute()
            
            total_customers = total_customers_response.count if hasattr(total_customers_response, 'count') else len(total_customers_response.data or [])
            
            engagement_rate = (total_returning / total_customers * 100) if total_customers > 0 else 0
            
            return {
                'period': {
                    'start_date': start_str,
                    'end_date': end_str,
                    'days': days
                },
                'summary': {
                    'total_new_customers': total_new_customers,
                    'total_appointments': total_appointments,
                    'total_completed_appointments': total_completed,
                    'total_revenue': round(total_revenue, 2),
                    'total_returning_customers': total_returning,
                    'average_rating': round(avg_rating, 2) if avg_rating else None,
                    'avg_daily_appointments': round(avg_daily_appointments, 2),
                    'avg_daily_revenue': round(avg_daily_revenue, 2),
                    'engagement_rate': round(engagement_rate, 2)
                },
                'daily_breakdown': daily_data
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get engagement metrics: {str(e)}"
    
    @staticmethod
    def get_appointment_metrics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get appointment-related metrics.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            start_str = datetime.combine(start_date, datetime.min.time()).isoformat()
            end_str = datetime.combine(end_date, datetime.max.time()).isoformat()
            
            # Get all appointments in range
            appointments = supabase.table('appointments')\
                .select('id, status, start_at, service_id, services:service_id(name, price)')\
                .gte('start_at', start_str)\
                .lte('start_at', end_str)\
                .execute()
            
            apts = appointments.data if appointments.data else []
            
            # Group by status
            by_status = {}
            for apt in apts:
                status = apt.get('status', 'unknown')
                by_status[status] = by_status.get(status, 0) + 1
            
            # Calculate completion rate
            total = len(apts)
            completed = by_status.get('completed', 0)
            cancelled = by_status.get('cancelled', 0)
            completion_rate = (completed / total * 100) if total > 0 else 0
            cancellation_rate = (cancelled / total * 100) if total > 0 else 0
            
            # Calculate revenue from completed
            revenue = 0.0
            for apt in apts:
                if apt.get('status') == 'completed':
                    service = apt.get('services')
                    if isinstance(service, dict) and service.get('price'):
                        try:
                            revenue += float(service['price'])
                        except (ValueError, TypeError):
                            pass
            
            # Calculate peak hours (group by hour of day)
            peak_hours = {}
            day_of_week_trends = {}
            for apt in apts:
                start_at = apt.get('start_at')
                if start_at:
                    try:
                        apt_datetime = datetime.fromisoformat(start_at.replace('Z', '+00:00'))
                        hour = apt_datetime.hour
                        day_of_week = apt_datetime.strftime('%A')  # Monday, Tuesday, etc.
                        
                        # Count by hour
                        peak_hours[hour] = peak_hours.get(hour, 0) + 1
                        
                        # Count by day of week
                        day_of_week_trends[day_of_week] = day_of_week_trends.get(day_of_week, 0) + 1
                    except (ValueError, AttributeError, TypeError):
                        pass
            
            # Convert peak hours to sorted list format
            peak_hours_list = [
                {'hour': hour, 'count': count}
                for hour, count in sorted(peak_hours.items())
            ]
            
            # Find peak hour
            peak_hour = max(peak_hours.items(), key=lambda x: x[1])[0] if peak_hours else None
            peak_hour_count = peak_hours.get(peak_hour, 0) if peak_hour is not None else 0
            
            # Convert day of week trends to list
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_of_week_list = [
                {'day': day, 'count': day_of_week_trends.get(day, 0)}
                for day in day_order
            ]
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'total_appointments': total,
                'by_status': by_status,
                'completion_rate': round(completion_rate, 2),
                'cancellation_rate': round(cancellation_rate, 2),
                'revenue': round(revenue, 2),
                'peak_hours': peak_hours_list,
                'peak_hour': peak_hour,
                'peak_hour_count': peak_hour_count,
                'day_of_week_trends': day_of_week_list
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get appointment metrics: {str(e)}"
    
    @staticmethod
    def get_revenue_metrics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get revenue metrics.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()
            
            # Get platform-wide daily statistics (salon_id IS NULL)
            stats = supabase.table('daily_statistics')\
                .select('date, total_revenue')\
                .gte('date', start_str)\
                .lte('date', end_str)\
                .is_('salon_id', 'null')\
                .order('date', desc=False)\
                .execute()
            
            daily_data = stats.data if stats.data else []
            
            total_revenue = sum(float(d.get('total_revenue', 0)) for d in daily_data)
            days = len(daily_data) if daily_data else 1
            avg_daily = total_revenue / days
            
            # Get revenue by salon
            start_datetime = datetime.combine(start_date, datetime.min.time()).isoformat()
            end_datetime = datetime.combine(end_date, datetime.max.time()).isoformat()
            
            appointments = supabase.table('appointments')\
                .select('salon_id, service_id, services:service_id(price), salons:salon_id(name)')\
                .eq('status', 'completed')\
                .gte('updated_at', start_datetime)\
                .lte('updated_at', end_datetime)\
                .execute()
            
            by_salon = {}
            if appointments.data:
                for apt in appointments.data:
                    salon_id = apt.get('salon_id')
                    salon_name = apt.get('salons', {}).get('name') if isinstance(apt.get('salons'), dict) else None
                    service = apt.get('services')
                    if isinstance(service, dict) and service.get('price'):
                        try:
                            price = float(service['price'])
                            if salon_id:
                                if salon_id not in by_salon:
                                    by_salon[salon_id] = {'name': salon_name, 'revenue': 0.0}
                                by_salon[salon_id]['revenue'] += price
                        except (ValueError, TypeError):
                            pass
            
            return {
                'period': {
                    'start_date': start_str,
                    'end_date': end_str
                },
                'total_revenue': round(total_revenue, 2),
                'avg_daily_revenue': round(avg_daily, 2),
                'daily_breakdown': daily_data,
                'by_salon': by_salon
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get revenue metrics: {str(e)}"
    
    @staticmethod
    def get_loyalty_metrics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get loyalty program metrics.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            start_str = datetime.combine(start_date, datetime.min.time()).isoformat()
            end_str = datetime.combine(end_date, datetime.max.time()).isoformat()
            
            # Get platform-wide daily statistics (salon_id IS NULL)
            stats = supabase.table('daily_statistics')\
                .select('date, loyalty_points_earned, loyalty_points_redeemed')\
                .gte('date', start_str)\
                .lte('date', end_str)\
                .is_('salon_id', 'null')\
                .order('date', desc=False)\
                .execute()
            
            daily_data = stats.data if stats.data else []
            
            total_earned = sum(d.get('loyalty_points_earned', 0) for d in daily_data)
            total_redeemed = sum(d.get('loyalty_points_redeemed', 0) for d in daily_data)
            
            # Get active loyalty members
            try:
                transactions = supabase.table('loyalty_transactions')\
                    .select('user_id')\
                    .gte('created_at', start_str)\
                    .lte('created_at', end_str)\
                    .execute()
                
                active_members = len(set(t.get('user_id') for t in (transactions.data or []) if t.get('user_id')))
            except Exception:
                active_members = 0
            
            return {
                'period': {
                    'start_date': start_str,
                    'end_date': end_str
                },
                'total_points_earned': total_earned,
                'total_points_redeemed': total_redeemed,
                'net_points': total_earned - total_redeemed,
                'active_members': active_members,
                'daily_breakdown': daily_data
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get loyalty metrics: {str(e)}"
    
    @staticmethod
    def get_retention_metrics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get customer retention metrics.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            # Get all customers
            all_customers = supabase.table('user_details')\
                .select('id, profile_created_at')\
                .eq('role', 'customer')\
                .not_.is_('profile_created_at', 'null')\
                .execute()
            
            customer_ids = [c.get('id') for c in (all_customers.data or []) if c.get('id')]
            
            if not customer_ids:
                return {
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    },
                    'total_customers': 0,
                    'returning_customers': 0,
                    'new_customers': 0,
                    'retention_rate': 0
                }, None
            
            # Get customers with appointments in the period
            start_str = datetime.combine(start_date, datetime.min.time()).isoformat()
            end_str = datetime.combine(end_date, datetime.max.time()).isoformat()
            
            appointments = supabase.table('appointments')\
                .select('customer_id')\
                .in_('customer_id', customer_ids)\
                .gte('start_at', start_str)\
                .lte('start_at', end_str)\
                .execute()
            
            active_customer_ids = set(apt.get('customer_id') for apt in (appointments.data or []) if apt.get('customer_id'))
            
            # Get new customers (created in period)
            new_customers_response = supabase.table('user_details')\
                .select('id')\
                .eq('role', 'customer')\
                .not_.is_('profile_created_at', 'null')\
                .gte('profile_created_at', start_str)\
                .lte('profile_created_at', end_str)\
                .execute()
            
            new_customer_ids = set(c.get('id') for c in (new_customers_response.data or []) if c.get('id'))
            
            # Returning customers = active customers who are not new
            returning_customers = active_customer_ids - new_customer_ids
            
            # Calculate retention rate (customers with 2+ appointments)
            customer_appointment_counts = {}
            for apt in (appointments.data or []):
                cid = apt.get('customer_id')
                if cid:
                    customer_appointment_counts[cid] = customer_appointment_counts.get(cid, 0) + 1
            
            repeat_customers = len([cid for cid, count in customer_appointment_counts.items() if count >= 2])
            retention_rate = (repeat_customers / len(customer_ids) * 100) if customer_ids else 0
            
            # Calculate churn rate (customers who had appointments before but not in this period)
            churn_rate = 0.0
            if customer_ids:
                # Get customers who had appointments before this period but not during
                customers_with_prev_appts = set()
                try:
                    prev_appts = supabase.table('appointments')\
                        .select('customer_id')\
                        .in_('customer_id', customer_ids)\
                        .lt('start_at', start_str)\
                        .execute()
                    customers_with_prev_appts = set(apt.get('customer_id') for apt in (prev_appts.data or []) if apt.get('customer_id'))
                    
                    # Churn = customers with previous appointments but no appointments in this period
                    churned = customers_with_prev_appts - active_customer_ids
                    churn_rate = (len(churned) / len(customers_with_prev_appts) * 100) if customers_with_prev_appts else 0
                except Exception:
                    pass
            
            return {
                'period': {
                    'start_date': start_str,
                    'end_date': end_str
                },
                'total_customers': len(customer_ids),
                'active_customers': len(active_customer_ids),
                'new_customers': len(new_customer_ids),
                'returning_customers': len(returning_customers),
                'repeat_customers': repeat_customers,
                'retention_rate': round(retention_rate, 2),
                'churn_rate': round(churn_rate, 2)
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get retention metrics: {str(e)}"

    @staticmethod
    def get_daily_statistics(start_date: date, end_date: date) -> Tuple[Dict, Optional[str]]:
        """
        Get raw daily statistics rows from daily_statistics table for a date range.
        Returns platform-wide rows (salon_id IS NULL) ordered by date ascending.
        """
        try:
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()

            stats = (
                supabase.table("daily_statistics")
                .select(
                    "date, total_appointments, completed_appointments, cancelled_appointments, "
                    "total_revenue, new_customers, returning_customers, average_rating, "
                    "loyalty_points_earned, loyalty_points_redeemed, created_at"
                )
                .gte("date", start_str)
                .lte("date", end_str)
                .is_("salon_id", "null")
                .order("date", desc=False)
                .execute()
            )

            rows = stats.data or []

            return {
                "period": {
                    "start_date": start_str,
                    "end_date": end_str,
                },
                "rows": rows,
            }, None
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity="high")
            return None, f"Failed to get daily statistics: {str(e)}"
    
    @staticmethod
    def calculate_and_store_platform_metrics(target_date: Optional[date] = None) -> Tuple[Dict, Optional[str]]:
        """
        Calculate platform metrics and store them in the platform_metrics table.
        If no date provided, uses today.
        
        Args:
            target_date: Date to calculate metrics for (default: today)
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            if target_date is None:
                target_date = datetime.now().date()
            
            date_str = target_date.isoformat()
            
            # Calculate metrics (same logic as before)
            # Total users - get count by role separately to avoid issues
            try:
                users_by_role = {}
                total_users = 0
                active_users = 0
                
                for role in ['customer', 'salon_owner', 'barber', 'admin']:
                    try:
                        role_response = supabase.table('user_details')\
                            .select('id', count='exact')\
                            .eq('role', role)\
                            .execute()
                        
                        role_count = role_response.count if hasattr(role_response, 'count') else 0
                        if role_count:
                            users_by_role[role] = role_count
                            total_users += role_count
                    except Exception as role_err:
                        print(f"[calculate_and_store_platform_metrics] Error counting {role} users: {role_err}")
                        continue
                
                # Count active users (users who have logged in within last 30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                try:
                    active_response = supabase.table('user_details')\
                        .select('id', count='exact')\
                        .gte('last_sign_in_at', thirty_days_ago)\
                        .execute()
                    active_users = active_response.count if hasattr(active_response, 'count') else len(active_response.data or [])
                except:
                    active_users = 0
            except Exception as e:
                print(f"[calculate_and_store_platform_metrics] Error fetching users: {e}")
                total_users = 0
                active_users = 0
                users_by_role = {}
            
            # Total salons
            try:
                salons_response = supabase.table('salons')\
                    .select('id, status', count='exact')\
                    .execute()
                
                total_salons = salons_response.count if hasattr(salons_response, 'count') else len(salons_response.data or [])
                
                # Active salons (verified salons)
                active_salons = len([s for s in (salons_response.data or []) if s.get('status') == 'verified'])
            except Exception as e:
                print(f"[calculate_and_store_platform_metrics] Error fetching salons: {e}")
                total_salons = 0
                active_salons = 0
            
            # Total appointments
            try:
                appointments_response = supabase.table('appointments')\
                    .select('id, status', count='exact')\
                    .execute()
                
                total_appointments = appointments_response.count if hasattr(appointments_response, 'count') else len(appointments_response.data or [])
            except Exception as e:
                print(f"[calculate_and_store_platform_metrics] Error fetching appointments: {e}")
                total_appointments = 0
            
            # Total revenue (from all completed appointments)
            total_revenue = Decimal('0.0')
            try:
                completed_apts = supabase.table('appointments')\
                    .select('service_id, services:service_id(price)')\
                    .eq('status', 'completed')\
                    .execute()
                
                if completed_apts.data:
                    for apt in completed_apts.data:
                        service = apt.get('services')
                        if isinstance(service, dict) and service.get('price'):
                            try:
                                total_revenue += Decimal(str(service['price']))
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                print(f"[calculate_and_store_platform_metrics] Error fetching revenue: {e}")
                total_revenue = Decimal('0.0')
            
            # Check if record exists for this date
            existing = supabase.table('platform_metrics')\
                .select('id')\
                .eq('date', date_str)\
                .execute()
            
            metrics_data = {
                'date': date_str,
                'total_users': total_users,
                'active_users': active_users,
                'total_salons': total_salons,
                'active_salons': active_salons,
                'total_appointments': total_appointments,
                'total_revenue': float(total_revenue)
            }
            
            if existing.data:
                # Update existing record
                metrics_id = existing.data[0]['id']
                response = supabase.table('platform_metrics')\
                    .update(metrics_data)\
                    .eq('id', metrics_id)\
                    .execute()
            else:
                # Insert new record
                response = supabase.table('platform_metrics')\
                    .insert(metrics_data)\
                    .execute()
            
            if getattr(response, 'error', None):
                return None, f"Failed to store platform metrics: {response.error}"
            
            # Return formatted response
            return {
                'timestamp': datetime.now().isoformat(),
                'date': date_str,
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'by_role': users_by_role
                },
                'salons': {
                    'total': total_salons,
                    'active': active_salons
                },
                'appointments': {
                    'total': total_appointments
                },
                'revenue': {
                    'total': round(float(total_revenue), 2)
                }
            }, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            import traceback
            traceback.print_exc()
            return None, f"Failed to calculate and store platform metrics: {str(e)}"
    
    @staticmethod
    def get_platform_metrics(use_stored: bool = True, target_date: Optional[date] = None) -> Tuple[Dict, Optional[str]]:
        """
        Get overall platform metrics.
        If use_stored is True, reads from platform_metrics table (most recent or specified date).
        Otherwise, calculates on the fly.
        
        Args:
            use_stored: Whether to read from stored metrics table
            target_date: Specific date to retrieve (default: most recent)
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            if use_stored:
                # Try to get from platform_metrics table
                try:
                    if target_date:
                        date_str = target_date.isoformat()
                        response = supabase.table('platform_metrics')\
                            .select('*')\
                            .eq('date', date_str)\
                            .maybe_single()\
                            .execute()
                    else:
                        # Get most recent
                        response = supabase.table('platform_metrics')\
                            .select('*')\
                            .order('date', desc=True)\
                            .limit(1)\
                            .maybe_single()\
                            .execute()
                    
                    if not response:
                        # Response is None, fall back to live calculation
                        print("[get_platform_metrics] Response is None, calculating on the fly")
                        return AnalyticsService._calculate_platform_metrics_live()
                    
                    if getattr(response, 'error', None):
                        # Fall back to calculating
                        print(f"[get_platform_metrics] Error reading from table: {response.error}, calculating on the fly")
                        return AnalyticsService._calculate_platform_metrics_live()
                    
                    if response.data:
                        stored = response.data
                        # Format to match expected structure
                        return {
                            'timestamp': stored.get('created_at', datetime.now().isoformat()),
                            'date': stored.get('date'),
                            'users': {
                                'total': stored.get('total_users', 0),
                                'active': stored.get('active_users', 0),
                                'by_role': {}  # Not stored in table, would need separate query
                            },
                            'salons': {
                                'total': stored.get('total_salons', 0),
                                'verified': stored.get('active_salons', 0)
                            },
                            'appointments': {
                                'total': stored.get('total_appointments', 0),
                                'completed': 0  # Not stored, would need separate query
                            },
                            'revenue': {
                                'total': float(stored.get('total_revenue', 0))
                            }
                        }, None
                    else:
                        # No stored data, calculate and store
                        print("[get_platform_metrics] No stored metrics found, calculating...")
                        result, error = AnalyticsService.calculate_and_store_platform_metrics(target_date)
                        if error or not result:
                            # If calculation fails, fall back to live calculation
                            print(f"[get_platform_metrics] Calculation failed: {error}, falling back to live calculation")
                            return AnalyticsService._calculate_platform_metrics_live()
                        return result, error
                except Exception as e:
                    # If any error occurs, fall back to live calculation
                    print(f"[get_platform_metrics] Exception reading from table: {e}, calculating on the fly")
                    return AnalyticsService._calculate_platform_metrics_live()
            else:
                # Calculate on the fly
                return AnalyticsService._calculate_platform_metrics_live()
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            import traceback
            traceback.print_exc()
            return None, f"Failed to get platform metrics: {str(e)}"
    
    @staticmethod
    def _calculate_platform_metrics_live() -> Tuple[Dict, Optional[str]]:
        """
        Calculate platform metrics on the fly (original logic).
        """
        try:
            # Total users - get count by role separately to avoid issues
            try:
                users_by_role = {}
                total_users = 0
                
                for role in ['customer', 'salon_owner', 'barber', 'admin']:
                    try:
                        role_response = supabase.table('user_details')\
                            .select('id', count='exact')\
                            .eq('role', role)\
                            .execute()
                        
                        role_count = role_response.count if hasattr(role_response, 'count') else 0
                        if role_count:
                            users_by_role[role] = role_count
                            total_users += role_count
                    except Exception as role_err:
                        print(f"[_calculate_platform_metrics_live] Error counting {role} users: {role_err}")
                        continue
            except Exception as e:
                print(f"[_calculate_platform_metrics_live] Error fetching users: {e}")
                total_users = 0
                users_by_role = {}
            
            # Total salons
            try:
                salons_response = supabase.table('salons')\
                    .select('id, status', count='exact')\
                    .execute()
                
                total_salons = salons_response.count if hasattr(salons_response, 'count') else len(salons_response.data or [])
                
                # Verified salons
                verified_salons = len([s for s in (salons_response.data or []) if s.get('status') == 'verified'])
            except Exception as e:
                print(f"[_calculate_platform_metrics_live] Error fetching salons: {e}")
                total_salons = 0
                verified_salons = 0
            
            # Total appointments
            try:
                appointments_response = supabase.table('appointments')\
                    .select('id, status', count='exact')\
                    .execute()
                
                total_appointments = appointments_response.count if hasattr(appointments_response, 'count') else len(appointments_response.data or [])
                
                # Completed appointments
                completed_appointments = len([a for a in (appointments_response.data or []) if a.get('status') == 'completed'])
            except Exception as e:
                print(f"[_calculate_platform_metrics_live] Error fetching appointments: {e}")
                total_appointments = 0
                completed_appointments = 0
            
            # Total revenue (from all completed appointments)
            total_revenue = 0.0
            try:
                completed_apts = supabase.table('appointments')\
                    .select('service_id, services:service_id(price)')\
                    .eq('status', 'completed')\
                    .execute()
                
                if completed_apts.data:
                    for apt in completed_apts.data:
                        service = apt.get('services')
                        if isinstance(service, dict) and service.get('price'):
                            try:
                                total_revenue += float(service['price'])
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                print(f"[_calculate_platform_metrics_live] Error fetching revenue: {e}")
                total_revenue = 0.0
            
            return {
                'timestamp': datetime.now().isoformat(),
                'users': {
                    'total': total_users,
                    'by_role': users_by_role
                },
                'salons': {
                    'total': total_salons,
                    'verified': verified_salons
                },
                'appointments': {
                    'total': total_appointments,
                    'completed': completed_appointments
                },
                'revenue': {
                    'total': round(total_revenue, 2)
                }
            }, None
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"Failed to calculate platform metrics: {str(e)}"

