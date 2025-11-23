#!/usr/bin/env python3
"""
Script to calculate daily statistics.
Can be run as a scheduled job (cron) or manually.
"""
import sys
import os
from datetime import datetime, timedelta, date

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analytics_service import AnalyticsService


def main():
    """Calculate daily statistics for yesterday (default) or specified date."""
    # Get date from command line argument if provided
    target_date = None
    if len(sys.argv) > 1:
        try:
            target_date = datetime.fromisoformat(sys.argv[1]).date()
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD format.")
            sys.exit(1)
    
    print(f"Calculating daily statistics for: {target_date or (datetime.now() - timedelta(days=1)).date()}")
    
    stats, error = AnalyticsService.calculate_daily_statistics(target_date)
    
    if error:
        print(f"Error: {error}")
        sys.exit(1)
    
    print("Daily statistics calculated successfully!")
    print(f"Date: {stats.get('date')}")
    print(f"Total Appointments: {stats.get('total_appointments', 0)}")
    print(f"Completed: {stats.get('completed_appointments', 0)}")
    print(f"Cancelled: {stats.get('cancelled_appointments', 0)}")
    print(f"Revenue: ${stats.get('total_revenue', 0)}")
    print(f"New Customers: {stats.get('new_customers', 0)}")
    print(f"Returning Customers: {stats.get('returning_customers', 0)}")
    print(f"Average Rating: {stats.get('average_rating', 'N/A')}")
    sys.exit(0)


if __name__ == "__main__":
    main()

