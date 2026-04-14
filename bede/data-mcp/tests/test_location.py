"""Tests for pure functions in sources/location.py — haversine, clustering, geocode extraction."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.location import (
    _activity_label,
    _centroid,
    _cluster_points,
    _extract_place,
    _haversine_km,
    CLUSTER_GAP_MINUTES,
    CLUSTER_RADIUS_KM,
)
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo("Australia/Sydney")


# ---------------------------------------------------------------------------
# _haversine_km
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(-33.8, 151.0, -33.8, 151.0) == pytest.approx(0.0)

    def test_known_distance(self):
        # North Parramatta to Parramatta CBD — roughly 1.6 km
        dist = _haversine_km(-33.801, 151.002, -33.814, 151.002)
        assert 1.3 < dist < 1.9

    def test_symmetry(self):
        a = (-33.8, 151.0)
        b = (-33.85, 151.05)
        assert _haversine_km(*a, *b) == pytest.approx(_haversine_km(*b, *a))

    def test_200m_threshold(self):
        # ~0.002° latitude ≈ 222 m — should exceed CLUSTER_RADIUS_KM
        lat1, lon = -33.800, 151.000
        lat2 = lat1 - 0.002
        assert _haversine_km(lat1, lon, lat2, lon) > CLUSTER_RADIUS_KM

    def test_within_200m(self):
        # ~0.001° latitude ≈ 111 m — should be within CLUSTER_RADIUS_KM
        lat1, lon = -33.800, 151.000
        lat2 = lat1 - 0.001
        assert _haversine_km(lat1, lon, lat2, lon) < CLUSTER_RADIUS_KM


# ---------------------------------------------------------------------------
# _centroid
# ---------------------------------------------------------------------------

class TestCentroid:
    def test_single_point(self):
        points = [{"lat": -33.8, "lon": 151.0}]
        lat, lon = _centroid(points)
        assert lat == pytest.approx(-33.8)
        assert lon == pytest.approx(151.0)

    def test_two_points_midpoint(self):
        points = [{"lat": -33.8, "lon": 151.0}, {"lat": -33.9, "lon": 151.1}]
        lat, lon = _centroid(points)
        assert lat == pytest.approx(-33.85)
        assert lon == pytest.approx(151.05)


# ---------------------------------------------------------------------------
# _cluster_points
# ---------------------------------------------------------------------------

def _pt(tst: int, lat: float, lon: float, vel: float = 0) -> dict:
    return {"tst": tst, "lat": lat, "lon": lon, "vel": vel}


class TestClusterPoints:
    def test_empty_input(self):
        assert _cluster_points([], SYDNEY) == []

    def test_single_point_forms_one_cluster(self):
        pts = [_pt(0, -33.8, 151.0)]
        clusters = _cluster_points(pts, SYDNEY)
        assert len(clusters) == 1
        assert len(clusters[0]) == 1

    def test_nearby_consecutive_points_cluster_together(self):
        # All points within 50 m of each other, 1 min apart
        base_lat, base_lon = -33.800, 151.000
        pts = [_pt(i * 60, base_lat + i * 0.0001, base_lon) for i in range(5)]
        clusters = _cluster_points(pts, SYDNEY)
        assert len(clusters) == 1
        assert len(clusters[0]) == 5

    def test_distant_point_starts_new_cluster(self):
        # Two locations clearly > 200 m apart
        home = _pt(0, -33.800, 151.000)
        away = _pt(300, -33.820, 151.020)  # ~2.5 km away
        clusters = _cluster_points([home, away], SYDNEY)
        assert len(clusters) == 2

    def test_large_time_gap_starts_new_cluster(self):
        # Same location but gap > CLUSTER_GAP_MINUTES → separate clusters
        gap_seconds = (CLUSTER_GAP_MINUTES + 1) * 60
        p1 = _pt(0, -33.800, 151.000)
        p2 = _pt(gap_seconds, -33.800, 151.000)
        clusters = _cluster_points([p1, p2], SYDNEY)
        assert len(clusters) == 2

    def test_small_time_gap_stays_in_cluster(self):
        gap_seconds = (CLUSTER_GAP_MINUTES - 1) * 60
        p1 = _pt(0, -33.800, 151.000)
        p2 = _pt(gap_seconds, -33.800, 151.000)
        clusters = _cluster_points([p1, p2], SYDNEY)
        assert len(clusters) == 1

    def test_out_of_order_input_is_sorted(self):
        # Points arrive out of order — clustering must sort by tst first
        p_later = _pt(120, -33.800, 151.000)
        p_earlier = _pt(0, -33.800, 151.000)
        clusters = _cluster_points([p_later, p_earlier], SYDNEY)
        assert len(clusters) == 1
        assert clusters[0][0]["tst"] == 0  # earliest first

    def test_three_location_journey(self):
        # Home → gym (2 km away) → home
        home_lat, home_lon = -33.800, 151.000
        gym_lat, gym_lon = -33.820, 151.010  # ~2.3 km

        t = 0
        pts = (
            [_pt(t + i * 60, home_lat, home_lon) for i in range(5)]  # 5 min at home
            + [_pt(t + 600 + i * 60, gym_lat, gym_lon) for i in range(30)]  # 30 min at gym
            + [_pt(t + 2400 + i * 60, home_lat, home_lon) for i in range(5)]  # 5 min home again
        )
        clusters = _cluster_points(pts, SYDNEY)
        assert len(clusters) == 3


# ---------------------------------------------------------------------------
# _activity_label
# ---------------------------------------------------------------------------

class TestActivityLabel:
    def test_none_velocity(self):
        assert _activity_label(None) == "stationary"

    def test_zero_velocity(self):
        assert _activity_label(0) == "stationary"

    def test_slow_walking(self):
        assert _activity_label(2) == "stationary"

    def test_walking(self):
        assert _activity_label(5) == "walking"

    def test_fast_walking(self):
        assert _activity_label(10) == "walking"

    def test_cycling(self):
        assert _activity_label(20) == "cycling"

    def test_driving(self):
        assert _activity_label(60) == "driving"


# ---------------------------------------------------------------------------
# _extract_place
# ---------------------------------------------------------------------------

class TestExtractPlace:
    def test_name_field_used_when_present(self):
        geo = {
            "name": "Parramatta Aquatic Centre",
            "address": {"suburb": "Parramatta", "city": "Parramatta", "state": "New South Wales", "postcode": "2150"},
        }
        place, address = _extract_place(geo)
        assert place == "Parramatta Aquatic Centre"

    def test_suburb_used_when_no_name(self):
        geo = {
            "name": "",
            "address": {"suburb": "North Parramatta", "city": "Parramatta", "state": "New South Wales", "postcode": "2151"},
        }
        place, address = _extract_place(geo)
        assert place == "North Parramatta"

    def test_address_string_constructed(self):
        geo = {
            "name": "Somewhere",
            "address": {"suburb": "Parramatta", "city": "Sydney", "state": "New South Wales", "postcode": "2150"},
        }
        _, address = _extract_place(geo)
        assert "Parramatta" in address

    def test_fallback_to_display_name(self):
        geo = {
            "name": "",
            "address": {},
            "display_name": "123 Some Street, Sydney NSW 2000",
        }
        place, address = _extract_place(geo)
        assert place == "Unknown"
        assert address == "123 Some Street, Sydney NSW 2000"

    def test_empty_geo_returns_unknown(self):
        place, address = _extract_place({})
        assert place == "Unknown"
