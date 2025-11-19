"""
Demographics service for aggregating user demographic data.
Provides analytics and segmentation for admin dashboard.
"""
from config import supabase
from typing import Dict, Optional, Tuple, List
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
                
                if city:
                    demographics['by_location']['cities'][city] = \
                        demographics['by_location']['cities'].get(city, 0) + 1
                
                if state:
                    demographics['by_location']['states'][state] = \
                        demographics['by_location']['states'].get(state, 0) + 1
                
                # Age bracket aggregation
                age_bracket = user.get('age_bracket')
                if age_bracket:
                    demographics['by_age_bracket'][age_bracket] = \
                        demographics['by_age_bracket'].get(age_bracket, 0) + 1
                
                # Gender aggregation
                gender = user.get('gender')
                if gender:
                    demographics['by_gender'][gender] = \
                        demographics['by_gender'].get(gender, 0) + 1
                
                # Role aggregation
                role = user.get('role', 'customer')
                demographics['by_role'][role] = \
                    demographics['by_role'].get(role, 0) + 1
                
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
                        if service:
                            demographics['preferred_services'][service] = \
                                demographics['preferred_services'].get(service, 0) + 1
            
            # Convert to distribution lists for easier frontend consumption
            demographics['location_distribution'] = [
                {'city': city, 'count': count}
                for city, count in sorted(
                    demographics['by_location']['cities'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]
            
            demographics['state_distribution'] = [
                {'state': state, 'count': count}
                for state, count in sorted(
                    demographics['by_location']['states'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]
            
            demographics['age_distribution'] = [
                {'age_bracket': bracket, 'count': count}
                for bracket, count in sorted(
                    demographics['by_age_bracket'].items(),
                    key=lambda x: x[0] if x[0] else ''
                )
            ]
            
            demographics['gender_distribution'] = [
                {'gender': gender, 'count': count}
                for gender, count in sorted(
                    demographics['by_gender'].items()
                )
            ]
            
            demographics['role_distribution'] = [
                {'role': role, 'count': count}
                for role, count in sorted(
                    demographics['by_role'].items()
                )
            ]
            
            demographics['service_distribution'] = [
                {'service': service, 'count': count}
                for service, count in sorted(
                    demographics['preferred_services'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]
            
            # Top N lists
            demographics['top_cities'] = [
                {'city': city, 'count': count}
                for city, count in demographics['location_distribution'][:10]
            ]
            
            demographics['top_states'] = [
                {'state': state, 'count': count}
                for state, count in demographics['state_distribution'][:10]
            ]
            
            demographics['top_services'] = [
                {'service': service, 'count': count}
                for service, count in demographics['service_distribution'][:10]
            ]
            
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
            return None, f"Failed to get segmented demographics: {str(e)}"


