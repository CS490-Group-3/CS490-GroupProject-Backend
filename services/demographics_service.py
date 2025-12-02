"""
Demographics service for aggregating user demographic data.
Provides analytics and segmentation for admin dashboard.
"""
from config import supabase
from typing import Dict, Optional, Tuple, List
from services.error_logging_service import ErrorLoggingService
import json


class DemographicsService:
    
    @staticmethod
    def get_demographics_aggregation() -> Tuple[Dict, Optional[str]]:
        """
        Get aggregated demographic data for all users.
        Returns statistics grouped by various demographic attributes.
        
        Returns:
            Tuple of (demographics_data, error_message)
        """
        try:
            # Get all user profiles with demographic data
            # Try user_details first, fallback to user_profiles
            response = supabase.table('user_details')\
                .select('city, state, age_bracket, gender, preferred_services, role')\
                .execute()
            
            if not response.data:
                # Fallback to user_profiles
                response = supabase.table('user_profiles')\
                    .select('city, state, age_bracket, gender, preferred_services, role')\
                    .execute()
            
            users = response.data if response.data else []
            
            # Initialize aggregation structures
            demographics = {
                'total_users': len(users),
                'by_location': {
                    'cities': {},
                    'states': {}
                },
                'by_age_bracket': {},
                'by_gender': {},
                'by_role': {},
                'preferred_services': {},
                'location_distribution': [],
                'age_distribution': [],
                'gender_distribution': [],
                'role_distribution': [],
                'top_cities': [],
                'top_states': [],
                'top_services': []
            }
            
            # Aggregate data
            for user in users:
                # Location aggregation
                city = user.get('city')
                state = user.get('state')
                
                if city and city is not None:
                    city_str = str(city).strip()
                    if city_str:
                        demographics['by_location']['cities'][city_str] = \
                            demographics['by_location']['cities'].get(city_str, 0) + 1
                
                if state and state is not None:
                    state_str = str(state).strip()
                    if state_str:
                        demographics['by_location']['states'][state_str] = \
                            demographics['by_location']['states'].get(state_str, 0) + 1
                
                # Age bracket aggregation
                age_bracket = user.get('age_bracket')
                if age_bracket and age_bracket is not None:
                    bracket_str = str(age_bracket).strip()
                    if bracket_str:
                        demographics['by_age_bracket'][bracket_str] = \
                            demographics['by_age_bracket'].get(bracket_str, 0) + 1
                
                # Gender aggregation
                gender = user.get('gender')
                if gender and gender is not None:
                    gender_str = str(gender).strip()
                    if gender_str:
                        demographics['by_gender'][gender_str] = \
                            demographics['by_gender'].get(gender_str, 0) + 1
                
                # Role aggregation
                role = user.get('role', 'customer')
                if role and role is not None:
                    role_str = str(role).strip()
                    if role_str:
                        demographics['by_role'][role_str] = \
                            demographics['by_role'].get(role_str, 0) + 1
                
                # Preferred services aggregation
                preferred_services = user.get('preferred_services')
                if preferred_services:
                    # Handle JSON string or list
                    if isinstance(preferred_services, str):
                        try:
                            services_list = json.loads(preferred_services)
                        except (json.JSONDecodeError, TypeError):
                            services_list = [preferred_services]
                    elif isinstance(preferred_services, list):
                        services_list = preferred_services
                    else:
                        services_list = []
                    
                    for service in services_list:
                        if service and service is not None:
                            service_str = str(service).strip()
                            if service_str:
                                demographics['preferred_services'][service_str] = \
                                    demographics['preferred_services'].get(service_str, 0) + 1
            
            # Convert to distribution lists for easier frontend consumption
            # All keys should now be strings, but add extra safety checks
            demographics['location_distribution'] = [
                {'city': city, 'count': count}
                for city, count in sorted(
                    [(k, v) for k, v in demographics['by_location']['cities'].items() if k is not None and str(k).strip()],
                    key=lambda x: (0, -x[1]) if x[0] is None else (1, -x[1])  # Sort by count, None keys last
                )
            ]
            
            demographics['state_distribution'] = [
                {'state': state, 'count': count}
                for state, count in sorted(
                    [(k, v) for k, v in demographics['by_location']['states'].items() if k is not None and str(k).strip()],
                    key=lambda x: (0, -x[1]) if x[0] is None else (1, -x[1])  # Sort by count, None keys last
                )
            ]
            
            demographics['age_distribution'] = [
                {'age_bracket': bracket, 'count': count}
                for bracket, count in sorted(
                    [(k, v) for k, v in demographics['by_age_bracket'].items() if k is not None and str(k).strip()],
                    key=lambda x: (str(x[0]) if x[0] is not None else 'zzz', x[1])  # Sort by bracket name
                )
            ]
            
            demographics['gender_distribution'] = [
                {'gender': gender, 'count': count}
                for gender, count in sorted(
                    [(k, v) for k, v in demographics['by_gender'].items() if k is not None and str(k).strip()],
                    key=lambda x: (str(x[0]) if x[0] is not None else 'zzz', x[1])  # Sort by gender name
                )
            ]
            
            demographics['role_distribution'] = [
                {'role': role, 'count': count}
                for role, count in sorted(
                    [(k, v) for k, v in demographics['by_role'].items() if k is not None and str(k).strip()],
                    key=lambda x: (str(x[0]) if x[0] is not None else 'zzz', x[1])  # Sort by role name
                )
            ]
            
            demographics['service_distribution'] = [
                {'service': service, 'count': count}
                for service, count in sorted(
                    [(k, v) for k, v in demographics['preferred_services'].items() if k is not None and str(k).strip()],
                    key=lambda x: (0, -x[1]) if x[0] is None else (1, -x[1])  # Sort by count, None keys last
                )
            ]
            
            # Top N lists - distribution lists are already dictionaries, so just slice them
            demographics['top_cities'] = demographics['location_distribution'][:10]
            
            demographics['top_states'] = demographics['state_distribution'][:10]
            
            demographics['top_services'] = demographics['service_distribution'][:10]
            
            # Calculate percentages
            total_with_demographics = sum(demographics['by_age_bracket'].values())
            if total_with_demographics > 0:
                demographics['age_percentages'] = {
                    bracket: round((count / total_with_demographics) * 100, 2)
                    for bracket, count in demographics['by_age_bracket'].items()
                }
            
            total_with_gender = sum(demographics['by_gender'].values())
            if total_with_gender > 0:
                demographics['gender_percentages'] = {
                    gender: round((count / total_with_gender) * 100, 2)
                    for gender, count in demographics['by_gender'].items()
                }
            
            return demographics, None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to aggregate demographics: {str(e)}"
    
    @staticmethod
    def get_demographics_by_segment(
        city: Optional[str] = None,
        state: Optional[str] = None,
        age_bracket: Optional[str] = None,
        gender: Optional[str] = None,
        role: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get user demographics filtered by specific segments.
        
        Args:
            city: Filter by city
            state: Filter by state
            age_bracket: Filter by age bracket
            gender: Filter by gender
            role: Filter by role
        
        Returns:
            Tuple of (filtered_users, error_message)
        """
        try:
            query = supabase.table('user_details').select('*')
            
            # Apply filters
            if city:
                query = query.eq('city', city)
            if state:
                query = query.eq('state', state)
            if age_bracket:
                query = query.eq('age_bracket', age_bracket)
            if gender:
                query = query.eq('gender', gender)
            if role:
                query = query.eq('role', role)
            
            response = query.execute()
            
            if not response.data:
                # Fallback to user_profiles
                query = supabase.table('user_profiles').select('*')
                if city:
                    query = query.eq('city', city)
                if state:
                    query = query.eq('state', state)
                if age_bracket:
                    query = query.eq('age_bracket', age_bracket)
                if gender:
                    query = query.eq('gender', gender)
                if role:
                    query = query.eq('role', role)
                
                response = query.execute()
            
            return response.data if response.data else [], None
            
        except Exception as e:
            ErrorLoggingService.log_exception(e, severity='high')
            return None, f"Failed to get segmented demographics: {str(e)}"


