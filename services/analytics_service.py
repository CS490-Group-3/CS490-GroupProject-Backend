"""
Analytics Service for calculating and storing platform metrics.
Handles daily statistics, engagement metrics, revenue, loyalty, and retention analytics.
"""
from config import supabase
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta, date
from decimal import Decimal
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
                .gte('created_at', start)\
                .lt('created_at', end)\
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
                .lte('created_at', end_str)\
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
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'total_appointments': total,
                'by_status': by_status,
                'completion_rate': round(completion_rate, 2),
                'cancellation_rate': round(cancellation_rate, 2),
                'revenue': round(revenue, 2)
            }, None
            
        except Exception as e:
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
                .select('id, created_at')\
                .eq('role', 'customer')\
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
                .gte('created_at', start_str)\
                .lte('created_at', end_str)\
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
                'retention_rate': round(retention_rate, 2)
            }, None
            
        except Exception as e:
            return None, f"Failed to get retention metrics: {str(e)}"
    
    @staticmethod
    def get_platform_metrics() -> Tuple[Dict, Optional[str]]:
        """
        Get overall platform metrics (current snapshot).
        
        Returns:
            Tuple of (metrics_data, error_message)
        """
        try:
            # Total users
            users_response = supabase.table('user_details')\
                .select('id, role', count='exact')\
                .execute()
            
            total_users = users_response.count if hasattr(users_response, 'count') else len(users_response.data or [])
            
            # Users by role
            users_by_role = {}
            if users_response.data:
                for user in users_response.data:
                    role = user.get('role', 'customer')
                    users_by_role[role] = users_by_role.get(role, 0) + 1
            
            # Total salons
            salons_response = supabase.table('salons')\
                .select('id, status', count='exact')\
                .execute()
            
            total_salons = salons_response.count if hasattr(salons_response, 'count') else len(salons_response.data or [])
            
            # Verified salons
            verified_salons = len([s for s in (salons_response.data or []) if s.get('status') == 'verified'])
            
            # Total appointments
            appointments_response = supabase.table('appointments')\
                .select('id, status', count='exact')\
                .execute()
            
            total_appointments = appointments_response.count if hasattr(appointments_response, 'count') else len(appointments_response.data or [])
            
            # Completed appointments
            completed_appointments = len([a for a in (appointments_response.data or []) if a.get('status') == 'completed'])
            
            # Total revenue (from all completed appointments)
            completed_apts = supabase.table('appointments')\
                .select('service_id, services:service_id(price)')\
                .eq('status', 'completed')\
                .execute()
            
            total_revenue = 0.0
            if completed_apts.data:
                for apt in completed_apts.data:
                    service = apt.get('services')
                    if isinstance(service, dict) and service.get('price'):
                        try:
                            total_revenue += float(service['price'])
                        except (ValueError, TypeError):
                            pass
            
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
            return None, f"Failed to get platform metrics: {str(e)}"

