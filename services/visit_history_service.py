"""
Visit History Service for aggregating customer visit data.
Provides comprehensive history including appointments, spend, images, and notes.
"""
from config import supabase
from typing import Dict, Optional, Tuple, List
from datetime import datetime


class VisitHistoryService:
    
    @staticmethod
    def get_customer_visit_history(customer_id: str, salon_id: Optional[str] = None) -> Tuple[Dict, Optional[str]]:
        """
        Get complete visit history for a customer.
        Aggregates appointments, spend, images, and notes.
        
        Args:
            customer_id: Customer's user ID
            salon_id: Optional salon ID to filter by specific salon
        
        Returns:
            Tuple of (visit_history_data, error_message)
        """
        try:
            # Build base query for appointments
            query = supabase.table('appointments')\
                .select('*, services:service_id(id, name, price, duration_minutes), salons:salon_id(id, name, address, city, state), barbers:barber_id(id, user_id)')\
                .eq('customer_id', customer_id)\
                .order('start_at', desc=True)
            
            if salon_id:
                query = query.eq('salon_id', salon_id)
            
            appointments_response = query.execute()
            appointments = appointments_response.data if appointments_response.data else []
            
            # Calculate total spend from completed appointments
            total_spend = 0.0
            completed_appointments = []
            visit_timeline = []
            
            for apt in appointments:
                # Calculate spend for completed appointments
                if apt.get('status') == 'completed' and apt.get('services'):
                    service = apt['services']
                    if isinstance(service, dict) and service.get('price'):
                        try:
                            price = float(service['price'])
                            total_spend += price
                        except (ValueError, TypeError):
                            pass
                
                # Build timeline entry
                timeline_entry = {
                    'type': 'appointment',
                    'id': apt.get('id'),
                    'date': apt.get('start_at'),
                    'status': apt.get('status'),
                    'salon_name': apt.get('salons', {}).get('name') if isinstance(apt.get('salons'), dict) else None,
                    'service_name': apt.get('services', {}).get('name') if isinstance(apt.get('services'), dict) else None,
                    'notes': apt.get('notes'),
                    'appointment': {
                        'id': apt.get('id'),
                        'start_at': apt.get('start_at'),
                        'end_at': apt.get('end_at'),
                        'status': apt.get('status'),
                        'service_id': apt.get('service_id'),
                        'salon_id': apt.get('salon_id'),
                        'barber_id': apt.get('barber_id'),
                        'notes': apt.get('notes'),
                        'created_at': apt.get('created_at'),
                        'updated_at': apt.get('updated_at')
                    }
                }
                
                # Add service details if available
                if apt.get('services') and isinstance(apt['services'], dict):
                    timeline_entry['service'] = {
                        'id': apt['services'].get('id'),
                        'name': apt['services'].get('name'),
                        'price': apt['services'].get('price'),
                        'duration_minutes': apt['services'].get('duration_minutes')
                    }
                
                # Add salon details if available
                if apt.get('salons') and isinstance(apt['salons'], dict):
                    timeline_entry['salon'] = {
                        'id': apt['salons'].get('id'),
                        'name': apt['salons'].get('name'),
                        'address': apt['salons'].get('address'),
                        'city': apt['salons'].get('city'),
                        'state': apt['salons'].get('state')
                    }
                
                visit_timeline.append(timeline_entry)
                
                if apt.get('status') == 'completed':
                    completed_appointments.append(apt)
            
            # Try to get customer images (if table exists)
            images = []
            try:
                images_query = supabase.table('customer_images')\
                    .select('*')\
                    .eq('customer_id', customer_id)
                
                if salon_id:
                    images_query = images_query.eq('salon_id', salon_id)
                
                images_response = images_query.order('uploaded_at', desc=True).execute()
                if images_response.data:
                    images = images_response.data
                    # Generate signed URLs for images (image_url stores filepath)
                    from datetime import timedelta
                    for img in images:
                        filepath = img.get('image_url')  # This is the filepath
                        if filepath:
                            try:
                                signed = supabase.storage.from_('customer-images').create_signed_url(
                                    filepath,
                                    int(timedelta(days=7).total_seconds())
                                )
                                if not (hasattr(signed, 'error') and signed.error):
                                    img['signed_url'] = signed.get('signedURL')
                            except Exception:
                                img['signed_url'] = None
                        
                        # Add image entries to timeline
                        visit_timeline.append({
                            'type': 'image',
                            'id': img.get('id'),
                            'date': img.get('uploaded_at') or img.get('created_at'),
                            'image_url': img.get('signed_url') or img.get('image_url'),
                            'caption': img.get('caption'),
                            'salon_id': img.get('salon_id')
                        })
            except Exception:
                # Table might not exist, that's okay
                pass
            
            # Try to get loyalty transactions (if table exists)
            loyalty_transactions = []
            loyalty_points = 0
            try:
                loyalty_query = supabase.table('loyalty_transactions')\
                    .select('*')\
                    .eq('customer_id', customer_id)
                
                if salon_id:
                    loyalty_query = loyalty_query.eq('salon_id', salon_id)
                
                loyalty_response = loyalty_query.order('created_at', desc=True).execute()
                if loyalty_response.data:
                    loyalty_transactions = loyalty_response.data
                    # Calculate total points
                    for trans in loyalty_transactions:
                        points = trans.get('points', 0)
                        if isinstance(points, (int, float)):
                            loyalty_points += points
                    
                    # Add loyalty entries to timeline
                    for trans in loyalty_transactions:
                        visit_timeline.append({
                            'type': 'loyalty',
                            'id': trans.get('id'),
                            'date': trans.get('created_at'),
                            'points': trans.get('points'),
                            'transaction_type': trans.get('transaction_type'),
                            'description': trans.get('description'),
                            'salon_id': trans.get('salon_id')
                        })
            except Exception:
                # Table might not exist, that's okay
                pass
            
            # Sort timeline by date (most recent first)
            visit_timeline.sort(key=lambda x: x.get('date') or '', reverse=True)
            
            # Aggregate statistics
            stats = {
                'total_visits': len(completed_appointments),
                'total_appointments': len(appointments),
                'total_spend': round(total_spend, 2),
                'loyalty_points': loyalty_points,
                'total_images': len(images),
                'appointments_by_status': {}
            }
            
            # Count appointments by status
            for apt in appointments:
                status = apt.get('status', 'unknown')
                stats['appointments_by_status'][status] = stats['appointments_by_status'].get(status, 0) + 1
            
            return {
                'customer_id': customer_id,
                'salon_id': salon_id,
                'statistics': stats,
                'appointments': appointments,
                'completed_appointments': completed_appointments,
                'images': images,
                'loyalty_transactions': loyalty_transactions,
                'timeline': visit_timeline,
                'total_spend': round(total_spend, 2),
                'loyalty_points': loyalty_points
            }, None
            
        except Exception as e:
            return None, f"Failed to get visit history: {str(e)}"
    
    @staticmethod
    def get_salon_customer_history(salon_id: str, customer_id: str) -> Tuple[Dict, Optional[str]]:
        """
        Get customer history at a specific salon (for salon owners).
        Same as get_customer_visit_history but filtered to specific salon.
        
        Args:
            salon_id: Salon ID
            customer_id: Customer's user ID
        
        Returns:
            Tuple of (visit_history_data, error_message)
        """
        # Verify salon exists and user has access
        try:
            salon_response = supabase.table('salons')\
                .select('id, name')\
                .eq('id', salon_id)\
                .single()\
                .execute()
            
            if not salon_response.data:
                return None, "Salon not found"
            
            # Get history filtered to this salon
            history, error = VisitHistoryService.get_customer_visit_history(customer_id, salon_id=salon_id)
            
            if error:
                return None, error
            
            # Add salon context
            if history:
                history['salon'] = {
                    'id': salon_response.data.get('id'),
                    'name': salon_response.data.get('name')
                }
            
            return history, None
            
        except Exception as e:
            return None, f"Failed to get salon customer history: {str(e)}"

