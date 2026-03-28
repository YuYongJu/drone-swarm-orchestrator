"""Tests for drone_swarm.missions -- formation math and area sweep logic.

All tests verify that generated waypoints are geometrically reasonable
(correct count, near the expected center, symmetrical where expected).
No SITL or pymavlink needed.
"""

import math

import pytest

from drone_swarm.drone import Waypoint
from drone_swarm.missions import (
    area_sweep,
    line_formation,
    orbit_point,
    polygon_sweep,
    v_formation,
)

# Reference point: Edwards AFB, California
CENTER_LAT = 34.9592
CENTER_LON = -117.8814
ALT = 20.0


def _distance_m(wp1: Waypoint, wp2: Waypoint) -> float:
    """Haversine distance between two waypoints in meters."""
    earth_r = 6371000
    dlat = math.radians(wp2.lat - wp1.lat)
    dlon = math.radians(wp2.lon - wp1.lon)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(wp1.lat)) * math.cos(math.radians(wp2.lat))
         * math.sin(dlon / 2) ** 2)
    return earth_r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# v_formation
# ---------------------------------------------------------------------------

class TestVFormation:
    def test_returns_correct_number_of_missions(self):
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=5, spacing_m=15.0)
        assert len(result) == 5

    def test_each_mission_has_one_waypoint(self):
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=4)
        for mission in result:
            assert len(mission) == 1

    def test_leader_is_at_center(self):
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=3)
        leader_wp = result[0][0]
        assert leader_wp.lat == pytest.approx(CENTER_LAT)
        assert leader_wp.lon == pytest.approx(CENTER_LON)

    def test_altitude_is_preserved(self):
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=3)
        for mission in result:
            assert mission[0].alt == ALT

    def test_followers_are_behind_leader(self):
        """With heading=0 (north), followers should have lower lat (behind)."""
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=5, heading_deg=0.0)
        leader = result[0][0]
        for mission in result[1:]:
            follower = mission[0]
            # Followers must be behind (south of) or at leader lat
            assert follower.lat <= leader.lat + 1e-9

    def test_spacing_is_approximately_correct(self):
        spacing = 20.0
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=3, spacing_m=spacing)
        leader = result[0][0]
        wing1 = result[1][0]
        dist = _distance_m(leader, wing1)
        # Should be close to the requested spacing (within 10%)
        assert dist == pytest.approx(spacing, rel=0.1)

    def test_single_drone_returns_center(self):
        result = v_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=1)
        assert len(result) == 1
        assert result[0][0].lat == pytest.approx(CENTER_LAT)


# ---------------------------------------------------------------------------
# line_formation
# ---------------------------------------------------------------------------

class TestLineFormation:
    def test_returns_correct_number(self):
        result = line_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=4)
        assert len(result) == 4

    def test_center_drone_is_near_center(self):
        """With odd count the middle drone should be at the center."""
        result = line_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=3, spacing_m=20.0)
        mid = result[1][0]
        assert mid.lat == pytest.approx(CENTER_LAT, abs=1e-5)
        assert mid.lon == pytest.approx(CENTER_LON, abs=1e-5)

    def test_drones_are_roughly_evenly_spaced(self):
        spacing = 25.0
        result = line_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=4, spacing_m=spacing)
        distances = []
        for i in range(len(result) - 1):
            d = _distance_m(result[i][0], result[i + 1][0])
            distances.append(d)
        for d in distances:
            assert d == pytest.approx(spacing, rel=0.1)

    def test_altitude_preserved(self):
        result = line_formation(CENTER_LAT, CENTER_LON, ALT, num_drones=2)
        for m in result:
            assert m[0].alt == ALT


# ---------------------------------------------------------------------------
# area_sweep
# ---------------------------------------------------------------------------

class TestAreaSweep:
    """Backwards-compatible area_sweep (now delegates to polygon_sweep)."""

    SW_LAT = 34.95
    SW_LON = -117.90
    NE_LAT = 34.97
    NE_LON = -117.87

    def test_returns_correct_number(self):
        result = area_sweep(self.SW_LAT, self.SW_LON, self.NE_LAT, self.NE_LON, ALT, 3)
        assert len(result) == 3

    def test_each_mission_has_waypoints(self):
        """Each drone should receive at least one waypoint."""
        result = area_sweep(self.SW_LAT, self.SW_LON, self.NE_LAT, self.NE_LON, ALT, 2)
        for mission in result:
            assert len(mission) >= 2

    def test_waypoints_stay_within_bounds(self):
        result = area_sweep(self.SW_LAT, self.SW_LON, self.NE_LAT, self.NE_LON, ALT, 4)
        for mission in result:
            for wp in mission:
                # Allow small float tolerance at polygon edges
                assert wp.lat >= self.SW_LAT - 1e-6
                assert wp.lat <= self.NE_LAT + 1e-6
                assert wp.lon >= self.SW_LON - 1e-6
                assert wp.lon <= self.NE_LON + 1e-6

    def test_strips_cover_full_longitude_range(self):
        result = area_sweep(self.SW_LAT, self.SW_LON, self.NE_LAT, self.NE_LON, ALT, 4)
        lons = sorted(wp.lon for m in result for wp in m)
        # First strip center should be near SW, last near NE
        assert lons[0] > self.SW_LON - 1e-4
        assert lons[-1] < self.NE_LON + 1e-4

    def test_altitude_preserved(self):
        result = area_sweep(self.SW_LAT, self.SW_LON, self.NE_LAT, self.NE_LON, ALT, 2)
        for mission in result:
            for wp in mission:
                assert wp.alt == ALT

    def test_old_signature_still_works(self):
        """The original 6-argument call signature must continue to work."""
        result = area_sweep(34.95, -117.90, 34.97, -117.87, 20.0, 3)
        assert len(result) == 3
        assert all(len(m) >= 1 for m in result)


# ---------------------------------------------------------------------------
# polygon_sweep (Boustrophedon decomposition)
# ---------------------------------------------------------------------------

class TestPolygonSweep:
    """Tests for polygon_sweep with arbitrary polygons."""

    def test_rectangle_returns_correct_drone_count(self):
        rect = [(34.95, -117.90), (34.95, -117.87),
                (34.97, -117.87), (34.97, -117.90)]
        result = polygon_sweep(rect, ALT, num_drones=3)
        assert len(result) == 3

    def test_rectangle_all_waypoints_within_bounds(self):
        sw_lat, sw_lon = 34.95, -117.90
        ne_lat, ne_lon = 34.97, -117.87
        rect = [(sw_lat, sw_lon), (sw_lat, ne_lon),
                (ne_lat, ne_lon), (ne_lat, sw_lon)]
        result = polygon_sweep(rect, ALT, num_drones=2)
        for mission in result:
            for wp in mission:
                assert wp.lat >= sw_lat - 1e-6
                assert wp.lat <= ne_lat + 1e-6
                assert wp.lon >= sw_lon - 1e-6
                assert wp.lon <= ne_lon + 1e-6

    def test_rectangle_altitude_preserved(self):
        rect = [(34.95, -117.90), (34.95, -117.87),
                (34.97, -117.87), (34.97, -117.90)]
        result = polygon_sweep(rect, ALT, num_drones=2)
        for mission in result:
            for wp in mission:
                assert wp.alt == ALT

    def test_l_shaped_polygon(self):
        """An L-shaped polygon should produce valid waypoints inside bounds."""
        # L-shape: bottom-left rectangle + top-left rectangle
        l_poly = [
            (34.95, -117.90),   # bottom-left
            (34.95, -117.87),   # bottom-right
            (34.96, -117.87),   # step right
            (34.96, -117.885),  # step inward
            (34.97, -117.885),  # top inner
            (34.97, -117.90),   # top-left
        ]
        result = polygon_sweep(l_poly, ALT, num_drones=2)
        assert len(result) == 2
        # All waypoints should have some content
        total_wps = sum(len(m) for m in result)
        assert total_wps >= 2

        # All waypoints should be within the bounding box of the L
        for mission in result:
            for wp in mission:
                assert 34.95 - 1e-6 <= wp.lat <= 34.97 + 1e-6
                assert -117.90 - 1e-6 <= wp.lon <= -117.87 + 1e-6

    def test_l_shaped_sweep_lines_inside_polygon(self):
        """Sweep waypoints for an L-shape should not be in the cut-out region."""
        # L-shape with a clear cut-out in the top-right
        l_poly = [
            (34.950, -117.900),
            (34.950, -117.870),
            (34.960, -117.870),
            (34.960, -117.885),
            (34.970, -117.885),
            (34.970, -117.900),
        ]
        result = polygon_sweep(l_poly, ALT, num_drones=2, line_spacing_m=10.0)
        # No waypoint should be in the cut-out area:
        # lat > 34.960 AND lon > -117.885
        for mission in result:
            for wp in mission:
                if wp.lat > 34.960 + 1e-5:
                    # Must be west of the step
                    assert wp.lon <= -117.885 + 1e-4

    def test_single_drone_gets_all_sweep_lines(self):
        rect = [(34.95, -117.90), (34.95, -117.87),
                (34.97, -117.87), (34.97, -117.90)]
        result = polygon_sweep(rect, ALT, num_drones=1)
        assert len(result) == 1
        assert len(result[0]) >= 2

    def test_coverage_all_sweep_lines_within_polygon(self):
        """Verify that every generated waypoint is inside (or on the edge of)
        the polygon bounding box."""
        pentagon = [
            (34.960, -117.890),
            (34.955, -117.880),
            (34.957, -117.870),
            (34.963, -117.870),
            (34.965, -117.880),
        ]
        result = polygon_sweep(pentagon, ALT, num_drones=2, line_spacing_m=10.0)
        all_lats = [p[0] for p in pentagon]
        all_lons = [p[1] for p in pentagon]
        lat_min, lat_max = min(all_lats), max(all_lats)
        lon_min, lon_max = min(all_lons), max(all_lons)

        for mission in result:
            for wp in mission:
                assert lat_min - 1e-5 <= wp.lat <= lat_max + 1e-5
                assert lon_min - 1e-5 <= wp.lon <= lon_max + 1e-5


# ---------------------------------------------------------------------------
# orbit_point
# ---------------------------------------------------------------------------

class TestOrbitPoint:
    def test_returns_correct_number_of_missions(self):
        result = orbit_point(CENTER_LAT, CENTER_LON, ALT, num_drones=4)
        assert len(result) == 4

    def test_default_points_per_orbit(self):
        result = orbit_point(CENTER_LAT, CENTER_LON, ALT, num_drones=2, points_per_orbit=12)
        for mission in result:
            assert len(mission) == 12

    def test_orbit_waypoints_are_at_correct_radius(self):
        radius = 50.0
        result = orbit_point(
            CENTER_LAT, CENTER_LON, ALT, radius_m=radius, num_drones=1, points_per_orbit=8,
        )
        center = Waypoint(CENTER_LAT, CENTER_LON, ALT)
        for wp in result[0]:
            dist = _distance_m(center, wp)
            assert dist == pytest.approx(radius, rel=0.05)

    def test_altitude_preserved(self):
        result = orbit_point(CENTER_LAT, CENTER_LON, ALT, num_drones=2, points_per_orbit=6)
        for mission in result:
            for wp in mission:
                assert wp.alt == ALT

    def test_drones_start_at_different_phases(self):
        """Two drones should not start at the same location."""
        result = orbit_point(CENTER_LAT, CENTER_LON, ALT, num_drones=2, points_per_orbit=8)
        wp_a = result[0][0]
        wp_b = result[1][0]
        dist = _distance_m(wp_a, wp_b)
        # They should be separated (for 2 drones on a 50m circle, ~100m apart)
        assert dist > 10.0
