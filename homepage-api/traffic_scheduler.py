"""
Traffic route scheduler for Homepage
Determines which routes to show based on schedule configuration
"""

from datetime import datetime
import os
import re


def parse_schedule(schedule_string):
    """
    Parse schedule string like "Mon-Fri 07:00-09:00"

    Args:
        schedule_string: Schedule in format "DAYS START_TIME-END_TIME"

    Returns:
        tuple: (days, start_time, end_time) or None if invalid

    Examples:
        >>> parse_schedule("Mon-Fri 07:00-09:00")
        ([0, 1, 2, 3, 4], '07:00', '09:00')
        >>> parse_schedule("Daily 00:00-23:59")
        ([0, 1, 2, 3, 4, 5, 6], '00:00', '23:59')
    """
    if not schedule_string:
        return None

    # Parse format: "Mon-Fri 07:00-09:00" or "Daily 00:00-23:59"
    pattern = r'([\w-]+)\s+(\d{2}:\d{2})-(\d{2}:\d{2})'
    match = re.match(pattern, schedule_string)

    if not match:
        return None

    days_str, start_time, end_time = match.groups()

    # Parse days
    if days_str.lower() == 'daily':
        days = list(range(7))  # 0-6 (Monday-Sunday)
    elif '-' in days_str:
        # Parse "Mon-Fri"
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        start_day, end_day = days_str.lower().split('-')
        start_idx = day_map.get(start_day, 0)
        end_idx = day_map.get(end_day, 4)
        days = list(range(start_idx, end_idx + 1))
    else:
        # Single day
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        days = [day_map.get(days_str.lower(), 0)]

    return days, start_time, end_time


def is_route_active(schedule_string):
    """
    Check if route should be shown based on schedule

    Args:
        schedule_string: Schedule in format "DAYS START_TIME-END_TIME"

    Returns:
        bool: True if route should be shown now

    Examples:
        >>> is_route_active("Daily 00:00-23:59")
        True
        >>> is_route_active("")  # No schedule = always active
        True
    """
    if not schedule_string:
        return True  # Always show if no schedule

    parsed = parse_schedule(schedule_string)
    if not parsed:
        return True

    days, start_time, end_time = parsed

    now = datetime.now()
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_time = now.strftime('%H:%M')

    # Check if current day is in schedule
    if current_day not in days:
        return False

    # Check if current time is in range
    if start_time <= current_time <= end_time:
        return True

    return False


def get_active_routes():
    """
    Get list of active traffic routes based on schedule

    Returns:
        list: List of route configuration dicts with keys:
            - name: Route display name
            - origin: Starting address
            - destination: Ending address
            - route_num: Route number (for reference)
            - schedule: Schedule string

    Examples:
        Environment:
            TRAFFIC_ROUTE_1_NAME="Morning Commute"
            TRAFFIC_ROUTE_1_ORIGIN="Home"
            TRAFFIC_ROUTE_1_DESTINATION="Work"
            TRAFFIC_ROUTE_1_SCHEDULE="Mon-Fri 07:00-09:00"

        Returns (during Mon-Fri 07:00-09:00):
            [{'name': 'Morning Commute', 'origin': 'Home',
              'destination': 'Work', 'route_num': 1,
              'schedule': 'Mon-Fri 07:00-09:00'}]
    """
    active_routes = []

    # Check each configured route
    route_num = 1
    while True:
        route_name = os.getenv(f'TRAFFIC_ROUTE_{route_num}_NAME')
        if not route_name:
            break

        schedule = os.getenv(f'TRAFFIC_ROUTE_{route_num}_SCHEDULE', 'Daily 00:00-23:59')

        if is_route_active(schedule):
            active_routes.append({
                'name': route_name,
                'origin': os.getenv(f'TRAFFIC_ROUTE_{route_num}_ORIGIN'),
                'destination': os.getenv(f'TRAFFIC_ROUTE_{route_num}_DESTINATION'),
                'route_num': route_num,
                'schedule': schedule
            })

        route_num += 1

    return active_routes
