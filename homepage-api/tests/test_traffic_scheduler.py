"""
Unit tests for traffic scheduler module
"""
import pytest
from unittest.mock import patch
from datetime import datetime
import os

# Import after setting environment variables in conftest
import traffic_scheduler


class TestParseSchedule:
    """Tests for schedule parsing function"""

    def test_parse_weekday_schedule(self):
        """Test parsing Mon-Fri schedule"""
        days, start, end = traffic_scheduler.parse_schedule("Mon-Fri 07:00-09:00")
        assert days == [0, 1, 2, 3, 4]  # Monday through Friday
        assert start == '07:00'
        assert end == '09:00'

    def test_parse_daily_schedule(self):
        """Test parsing Daily schedule"""
        days, start, end = traffic_scheduler.parse_schedule("Daily 00:00-23:59")
        assert days == [0, 1, 2, 3, 4, 5, 6]  # All days
        assert start == '00:00'
        assert end == '23:59'

    def test_parse_weekend_schedule(self):
        """Test parsing Sat-Sun schedule"""
        days, start, end = traffic_scheduler.parse_schedule("Sat-Sun 10:00-18:00")
        assert days == [5, 6]  # Saturday and Sunday
        assert start == '10:00'
        assert end == '18:00'

    def test_parse_single_day_schedule(self):
        """Test parsing single day schedule"""
        days, start, end = traffic_scheduler.parse_schedule("Mon 08:00-09:00")
        assert days == [0]  # Monday only
        assert start == '08:00'
        assert end == '09:00'

    def test_parse_empty_schedule(self):
        """Test parsing empty schedule"""
        result = traffic_scheduler.parse_schedule("")
        assert result is None

    def test_parse_none_schedule(self):
        """Test parsing None schedule"""
        result = traffic_scheduler.parse_schedule(None)
        assert result is None

    def test_parse_invalid_format(self):
        """Test parsing invalid format"""
        result = traffic_scheduler.parse_schedule("Invalid Format")
        assert result is None

    def test_parse_case_insensitive(self):
        """Test parsing is case-insensitive"""
        days1, start1, end1 = traffic_scheduler.parse_schedule("mon-fri 07:00-09:00")
        days2, start2, end2 = traffic_scheduler.parse_schedule("Mon-Fri 07:00-09:00")
        assert days1 == days2
        assert start1 == start2
        assert end1 == end2


class TestIsRouteActive:
    """Tests for route active checking"""

    @patch('traffic_scheduler.datetime')
    def test_route_active_during_weekday_morning(self, mock_datetime):
        """Test route is active during weekday morning schedule"""
        # Mock Monday 8:30am
        mock_now = datetime(2025, 10, 27, 8, 30)  # Monday
        mock_datetime.now.return_value = mock_now

        active = traffic_scheduler.is_route_active("Mon-Fri 07:00-09:00")
        assert active is True

    @patch('traffic_scheduler.datetime')
    def test_route_inactive_on_weekend(self, mock_datetime):
        """Test route is inactive on weekend for weekday schedule"""
        # Mock Saturday 8:30am
        mock_now = datetime(2025, 11, 1, 8, 30)  # Saturday
        mock_datetime.now.return_value = mock_now

        active = traffic_scheduler.is_route_active("Mon-Fri 07:00-09:00")
        assert active is False

    @patch('traffic_scheduler.datetime')
    def test_route_inactive_outside_time_range(self, mock_datetime):
        """Test route is inactive outside time range"""
        # Mock Monday 6:30am (before 7am start)
        mock_now = datetime(2025, 10, 27, 6, 30)  # Monday
        mock_datetime.now.return_value = mock_now

        active = traffic_scheduler.is_route_active("Mon-Fri 07:00-09:00")
        assert active is False

    def test_route_active_with_no_schedule(self):
        """Test route is always active with no schedule"""
        active = traffic_scheduler.is_route_active("")
        assert active is True

        active = traffic_scheduler.is_route_active(None)
        assert active is True

    @patch('traffic_scheduler.datetime')
    def test_daily_route_always_active(self, mock_datetime):
        """Test daily route is active any time"""
        # Mock any day and time
        mock_now = datetime(2025, 10, 27, 15, 30)
        mock_datetime.now.return_value = mock_now

        active = traffic_scheduler.is_route_active("Daily 00:00-23:59")
        assert active is True


class TestGetActiveRoutes:
    """Tests for get_active_routes function"""

    @patch('traffic_scheduler.is_route_active')
    @patch.dict(os.environ, {
        'TRAFFIC_ROUTE_1_NAME': 'Morning Commute',
        'TRAFFIC_ROUTE_1_ORIGIN': 'Home',
        'TRAFFIC_ROUTE_1_DESTINATION': 'Work',
        'TRAFFIC_ROUTE_1_SCHEDULE': 'Mon-Fri 07:00-09:00',
        'TRAFFIC_ROUTE_2_NAME': 'Evening Commute',
        'TRAFFIC_ROUTE_2_ORIGIN': 'Work',
        'TRAFFIC_ROUTE_2_DESTINATION': 'Home',
        'TRAFFIC_ROUTE_2_SCHEDULE': 'Mon-Fri 17:00-19:00',
    })
    def test_get_active_routes_one_active(self, mock_is_active):
        """Test getting active routes when one is active"""
        # Only first route is active
        mock_is_active.side_effect = [True, False]

        routes = traffic_scheduler.get_active_routes()

        assert len(routes) == 1
        assert routes[0]['name'] == 'Morning Commute'
        assert routes[0]['origin'] == 'Home'
        assert routes[0]['destination'] == 'Work'
        assert routes[0]['route_num'] == 1
        assert routes[0]['schedule'] == 'Mon-Fri 07:00-09:00'

    @patch('traffic_scheduler.is_route_active')
    @patch.dict(os.environ, {
        'TRAFFIC_ROUTE_1_NAME': 'Morning Commute',
        'TRAFFIC_ROUTE_1_ORIGIN': 'Home',
        'TRAFFIC_ROUTE_1_DESTINATION': 'Work',
        'TRAFFIC_ROUTE_1_SCHEDULE': 'Mon-Fri 07:00-09:00',
        'TRAFFIC_ROUTE_2_NAME': 'Evening Commute',
        'TRAFFIC_ROUTE_2_ORIGIN': 'Work',
        'TRAFFIC_ROUTE_2_DESTINATION': 'Home',
        'TRAFFIC_ROUTE_2_SCHEDULE': 'Mon-Fri 17:00-19:00',
    })
    def test_get_active_routes_both_active(self, mock_is_active):
        """Test getting active routes when both are active"""
        # Both routes are active
        mock_is_active.return_value = True

        routes = traffic_scheduler.get_active_routes()

        assert len(routes) == 2
        assert routes[0]['name'] == 'Morning Commute'
        assert routes[1]['name'] == 'Evening Commute'

    @patch('traffic_scheduler.is_route_active')
    @patch.dict(os.environ, {
        'TRAFFIC_ROUTE_1_NAME': 'Morning Commute',
        'TRAFFIC_ROUTE_1_ORIGIN': 'Home',
        'TRAFFIC_ROUTE_1_DESTINATION': 'Work',
        'TRAFFIC_ROUTE_1_SCHEDULE': 'Mon-Fri 07:00-09:00',
    })
    def test_get_active_routes_none_active(self, mock_is_active):
        """Test getting active routes when none are active"""
        # No routes are active
        mock_is_active.return_value = False

        routes = traffic_scheduler.get_active_routes()

        assert len(routes) == 0
        assert routes == []

    @patch('traffic_scheduler.is_route_active')
    @patch.dict(os.environ, {}, clear=True)
    def test_get_active_routes_no_config(self, mock_is_active):
        """Test getting active routes when no routes are configured"""
        routes = traffic_scheduler.get_active_routes()

        assert len(routes) == 0
        assert routes == []

    @patch('traffic_scheduler.is_route_active')
    @patch.dict(os.environ, {
        'TRAFFIC_ROUTE_1_NAME': 'Always Active',
        'TRAFFIC_ROUTE_1_ORIGIN': 'A',
        'TRAFFIC_ROUTE_1_DESTINATION': 'B',
        # No schedule = defaults to Daily 00:00-23:59
    })
    def test_get_active_routes_default_schedule(self, mock_is_active):
        """Test route without schedule gets default Daily 00:00-23:59"""
        mock_is_active.return_value = True

        routes = traffic_scheduler.get_active_routes()

        assert len(routes) == 1
        # Check that is_route_active was called with default schedule
        mock_is_active.assert_called_with('Daily 00:00-23:59')
