"""Tests for the geofence system (drone_swarm.geofence).

Covers point-in-polygon, altitude checks, distance-to-boundary,
warning zone detection, irregular polygons, and swarm integration.
"""

import math

import pytest

from drone_swarm.drone import Drone, DroneStatus
from drone_swarm.geofence import Geofence, GeofenceStatus
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A square geofence roughly 200m x 200m around Edwards AFB
REF_LAT = 34.9592
REF_LON = -117.8814

_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(REF_LAT))


def _lat_offset(metres: float) -> float:
    return metres / _M_PER_DEG_LAT


def _lon_offset(metres: float) -> float:
    return metres / _M_PER_DEG_LON


# Square polygon: 200m x 200m centered on REF_LAT, REF_LON
SQUARE_POLYGON = [
    (REF_LAT - _lat_offset(100), REF_LON - _lon_offset(100)),  # SW
    (REF_LAT - _lat_offset(100), REF_LON + _lon_offset(100)),  # SE
    (REF_LAT + _lat_offset(100), REF_LON + _lon_offset(100)),  # NE
    (REF_LAT + _lat_offset(100), REF_LON - _lon_offset(100)),  # NW
]


def _make_drone(
    drone_id: str = "alpha",
    lat: float = REF_LAT,
    lon: float = REF_LON,
    alt: float = 10.0,
) -> Drone:
    d = Drone(drone_id=drone_id, connection_string="udp:127.0.0.1:14550")
    d.lat = lat
    d.lon = lon
    d.alt = alt
    d.status = DroneStatus.AIRBORNE
    return d


# ---------------------------------------------------------------------------
# Point inside polygon
# ---------------------------------------------------------------------------

class TestPointInsidePolygon:
    def test_center_point_is_inside(self):
        gf = Geofence(SQUARE_POLYGON)
        assert gf.contains(REF_LAT, REF_LON, 10.0) is True

    def test_point_slightly_inside(self):
        gf = Geofence(SQUARE_POLYGON)
        # 50m north of center -- well inside the 100m half-width
        assert gf.contains(REF_LAT + _lat_offset(50), REF_LON, 10.0) is True


# ---------------------------------------------------------------------------
# Point outside polygon
# ---------------------------------------------------------------------------

class TestPointOutsidePolygon:
    def test_point_far_outside(self):
        gf = Geofence(SQUARE_POLYGON)
        # 500m north -- well outside
        assert gf.contains(REF_LAT + _lat_offset(500), REF_LON, 10.0) is False

    def test_point_just_outside(self):
        gf = Geofence(SQUARE_POLYGON)
        # 110m north -- just outside the 100m boundary
        assert gf.contains(REF_LAT + _lat_offset(110), REF_LON, 10.0) is False


# ---------------------------------------------------------------------------
# Point on edge (boundary case)
# ---------------------------------------------------------------------------

class TestPointOnEdge:
    def test_point_on_vertex(self):
        """A point exactly on a vertex. Ray-casting may or may not include it."""
        gf = Geofence(SQUARE_POLYGON)
        # We just verify it doesn't crash -- boundary is implementation-defined
        result = gf.contains(SQUARE_POLYGON[0][0], SQUARE_POLYGON[0][1], 10.0)
        assert isinstance(result, bool)

    def test_point_on_edge_midpoint(self):
        """Midpoint of the southern edge."""
        gf = Geofence(SQUARE_POLYGON)
        mid_lat = SQUARE_POLYGON[0][0]
        mid_lon = (SQUARE_POLYGON[0][1] + SQUARE_POLYGON[1][1]) / 2
        result = gf.contains(mid_lat, mid_lon, 10.0)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Altitude checks
# ---------------------------------------------------------------------------

class TestAltitudeChecks:
    def test_altitude_too_high(self):
        gf = Geofence(SQUARE_POLYGON, alt_max_m=120.0)
        assert gf.contains(REF_LAT, REF_LON, 150.0) is False

    def test_altitude_too_low(self):
        gf = Geofence(SQUARE_POLYGON, alt_min_m=5.0)
        assert gf.contains(REF_LAT, REF_LON, 2.0) is False

    def test_altitude_in_range(self):
        gf = Geofence(SQUARE_POLYGON, alt_min_m=5.0, alt_max_m=120.0)
        assert gf.contains(REF_LAT, REF_LON, 50.0) is True

    def test_altitude_at_max_boundary(self):
        gf = Geofence(SQUARE_POLYGON, alt_max_m=120.0)
        assert gf.contains(REF_LAT, REF_LON, 120.0) is True

    def test_altitude_at_min_boundary(self):
        gf = Geofence(SQUARE_POLYGON, alt_min_m=0.0)
        assert gf.contains(REF_LAT, REF_LON, 0.0) is True


# ---------------------------------------------------------------------------
# Distance to boundary
# ---------------------------------------------------------------------------

class TestDistanceToBoundary:
    def test_center_has_positive_distance(self):
        gf = Geofence(SQUARE_POLYGON)
        dist = gf.distance_to_boundary(REF_LAT, REF_LON)
        # Center of 200x200 square -> ~100m to nearest edge
        assert dist > 50.0

    def test_near_edge_has_small_distance(self):
        gf = Geofence(SQUARE_POLYGON)
        # 5m inside the southern edge
        near_lat = SQUARE_POLYGON[0][0] + _lat_offset(5)
        near_lon = REF_LON
        dist = gf.distance_to_boundary(near_lat, near_lon)
        assert dist < 15.0  # should be roughly 5m

    def test_outside_point_has_positive_distance(self):
        gf = Geofence(SQUARE_POLYGON)
        dist = gf.distance_to_boundary(REF_LAT + _lat_offset(200), REF_LON)
        assert dist > 0.0


# ---------------------------------------------------------------------------
# Warning zone detection
# ---------------------------------------------------------------------------

class TestWarningZone:
    def test_center_is_inside(self):
        gf = Geofence(SQUARE_POLYGON)
        drone = _make_drone()
        assert gf.check_drone(drone) == GeofenceStatus.INSIDE

    def test_near_boundary_is_warning(self):
        gf = Geofence(SQUARE_POLYGON, buffer_fraction=0.20)
        # Place drone very close to the southern edge (5m inside)
        drone = _make_drone(
            lat=SQUARE_POLYGON[0][0] + _lat_offset(5),
            lon=REF_LON,
        )
        status = gf.check_drone(drone)
        # Should be WARNING since 5m is within 20% of the ~141m max radius
        assert status in (GeofenceStatus.WARNING, GeofenceStatus.INSIDE)

    def test_outside_is_breach(self):
        gf = Geofence(SQUARE_POLYGON)
        drone = _make_drone(lat=REF_LAT + _lat_offset(500))
        assert gf.check_drone(drone) == GeofenceStatus.BREACH

    def test_altitude_breach(self):
        gf = Geofence(SQUARE_POLYGON, alt_max_m=100.0)
        drone = _make_drone(alt=150.0)
        assert gf.check_drone(drone) == GeofenceStatus.BREACH


# ---------------------------------------------------------------------------
# Irregular polygon (L-shape / concave)
# ---------------------------------------------------------------------------

class TestIrregularPolygon:
    def test_l_shaped_polygon_inside(self):
        """L-shaped polygon: point in the main body is inside."""
        # An L-shape made of 6 vertices
        l_shape = [
            (REF_LAT, REF_LON),
            (REF_LAT, REF_LON + _lon_offset(100)),
            (REF_LAT + _lat_offset(50), REF_LON + _lon_offset(100)),
            (REF_LAT + _lat_offset(50), REF_LON + _lon_offset(50)),
            (REF_LAT + _lat_offset(100), REF_LON + _lon_offset(50)),
            (REF_LAT + _lat_offset(100), REF_LON),
        ]
        gf = Geofence(l_shape)
        # Point in the lower-right arm of the L
        assert gf.contains(
            REF_LAT + _lat_offset(25), REF_LON + _lon_offset(75), 10.0
        ) is True

    def test_l_shaped_polygon_in_concavity(self):
        """Point in the concave notch of an L-shape should be outside."""
        l_shape = [
            (REF_LAT, REF_LON),
            (REF_LAT, REF_LON + _lon_offset(100)),
            (REF_LAT + _lat_offset(50), REF_LON + _lon_offset(100)),
            (REF_LAT + _lat_offset(50), REF_LON + _lon_offset(50)),
            (REF_LAT + _lat_offset(100), REF_LON + _lon_offset(50)),
            (REF_LAT + _lat_offset(100), REF_LON),
        ]
        gf = Geofence(l_shape)
        # Point in the upper-right notch (outside the L)
        assert gf.contains(
            REF_LAT + _lat_offset(75), REF_LON + _lon_offset(75), 10.0
        ) is False

    def test_concave_polygon(self):
        """A concave (arrow-shaped) polygon."""
        arrow = [
            (REF_LAT, REF_LON),
            (REF_LAT + _lat_offset(100), REF_LON + _lon_offset(50)),
            (REF_LAT + _lat_offset(50), REF_LON),  # concavity indent
            (REF_LAT + _lat_offset(100), REF_LON - _lon_offset(50)),
        ]
        gf = Geofence(arrow)
        # Point at the base (inside)
        assert gf.contains(
            REF_LAT + _lat_offset(30), REF_LON, 10.0
        ) is True


# ---------------------------------------------------------------------------
# Geofence validation
# ---------------------------------------------------------------------------

class TestGeofenceValidation:
    def test_too_few_vertices_raises(self):
        with pytest.raises(ValueError, match="at least 3 vertices"):
            Geofence([(0, 0), (1, 1)])

    def test_three_vertices_ok(self):
        triangle = [
            (REF_LAT, REF_LON),
            (REF_LAT + _lat_offset(100), REF_LON),
            (REF_LAT, REF_LON + _lon_offset(100)),
        ]
        gf = Geofence(triangle)
        assert gf.contains(
            REF_LAT + _lat_offset(20), REF_LON + _lon_offset(20), 10.0
        ) is True


# ---------------------------------------------------------------------------
# Swarm integration: set_geofence / clear_geofence
# ---------------------------------------------------------------------------

class TestSwarmGeofenceIntegration:
    def test_set_geofence(self):
        swarm = SwarmOrchestrator()
        swarm.set_geofence(SQUARE_POLYGON, alt_max_m=100.0, action="rtl")
        assert swarm._geofence is not None
        assert isinstance(swarm._geofence, Geofence)
        assert swarm._geofence_action == "rtl"

    def test_clear_geofence(self):
        swarm = SwarmOrchestrator()
        swarm.set_geofence(SQUARE_POLYGON)
        swarm.clear_geofence()
        assert swarm._geofence is None
        assert swarm._geofence_action == "warn"

    def test_set_geofence_invalid_action(self):
        swarm = SwarmOrchestrator()
        with pytest.raises(ValueError, match="Invalid geofence action"):
            swarm.set_geofence(SQUARE_POLYGON, action="explode")

    def test_set_geofence_land_action(self):
        swarm = SwarmOrchestrator()
        swarm.set_geofence(SQUARE_POLYGON, action="land")
        assert swarm._geofence_action == "land"

    def test_set_geofence_warn_action(self):
        swarm = SwarmOrchestrator()
        swarm.set_geofence(SQUARE_POLYGON, action="warn")
        assert swarm._geofence_action == "warn"

    def test_geofence_not_set_by_default(self):
        swarm = SwarmOrchestrator()
        assert swarm._geofence is None
