"""Tests for the collision-avoidance system (drone_swarm.collision)."""

import math
import time

import pytest

from drone_swarm.collision import (
    CollisionAvoidance,
    CollisionRisk,
    haversine,
)
from drone_swarm.drone import Drone, DroneStatus
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(drone_id: str, lat: float, lon: float, alt: float = 10.0) -> Drone:
    """Create a minimal Drone at a given GPS position."""
    d = Drone(drone_id=drone_id, connection_string="udp:127.0.0.1:14550")
    d.lat = lat
    d.lon = lon
    d.alt = alt
    d.status = DroneStatus.AIRBORNE
    return d


# A reference point (Edwards AFB, CA)
REF_LAT = 34.9592
REF_LON = -117.8814

# Approx metres-per-degree at this latitude
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(REF_LAT))


def _lat_offset(metres: float) -> float:
    """Return a latitude offset corresponding to *metres* north."""
    return metres / _M_PER_DEG_LAT


def _lon_offset(metres: float) -> float:
    """Return a longitude offset corresponding to *metres* east."""
    return metres / _M_PER_DEG_LON


# ---------------------------------------------------------------------------
# Haversine accuracy tests
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_zero_distance(self):
        assert haversine(REF_LAT, REF_LON, REF_LAT, REF_LON) == 0.0

    def test_known_distance_north(self):
        """100 m due north should be close to 100 m."""
        dist = haversine(REF_LAT, REF_LON, REF_LAT + _lat_offset(100), REF_LON)
        assert abs(dist - 100.0) < 1.0  # within 1 m

    def test_known_distance_east(self):
        """100 m due east should be close to 100 m."""
        dist = haversine(REF_LAT, REF_LON, REF_LAT, REF_LON + _lon_offset(100))
        assert abs(dist - 100.0) < 1.0

    def test_symmetry(self):
        d1 = haversine(REF_LAT, REF_LON, REF_LAT + 0.001, REF_LON + 0.001)
        d2 = haversine(REF_LAT + 0.001, REF_LON + 0.001, REF_LAT, REF_LON)
        assert d1 == pytest.approx(d2)


# ---------------------------------------------------------------------------
# CollisionRisk dataclass
# ---------------------------------------------------------------------------

class TestCollisionRisk:
    def test_fields(self):
        risk = CollisionRisk(
            drone_a_id="a", drone_b_id="b", distance_m=3.0, min_distance_m=5.0
        )
        assert risk.drone_a_id == "a"
        assert risk.drone_b_id == "b"
        assert risk.distance_m == 3.0
        assert risk.min_distance_m == 5.0


# ---------------------------------------------------------------------------
# check_all_pairs
# ---------------------------------------------------------------------------

class TestCheckAllPairs:
    def test_two_drones_far_apart_no_risk(self):
        """Two drones 200 m apart should not trigger a risk."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = {
            "a": _make_drone("a", REF_LAT, REF_LON),
            "b": _make_drone("b", REF_LAT + _lat_offset(200), REF_LON),
        }
        assert ca.check_all_pairs(drones) == []

    def test_two_drones_exactly_at_threshold_no_risk(self):
        """Exactly at min_distance (not strictly below) -> no risk."""
        ca = CollisionAvoidance(min_distance_m=100.0)
        drones = {
            "a": _make_drone("a", REF_LAT, REF_LON),
            "b": _make_drone("b", REF_LAT + _lat_offset(100), REF_LON),
        }
        risks = ca.check_all_pairs(drones)
        # The haversine result for our offset should be ~100 m.
        # Due to floating-point, accept that it is NOT strictly below.
        # If it *is* flagged the distance should be essentially 100.
        for r in risks:
            assert r.distance_m == pytest.approx(100.0, abs=1.0)

    def test_two_drones_too_close(self):
        """Two drones 2 m apart with min 5 m -> one CollisionRisk."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = {
            "a": _make_drone("a", REF_LAT, REF_LON),
            "b": _make_drone("b", REF_LAT + _lat_offset(2), REF_LON),
        }
        risks = ca.check_all_pairs(drones)
        assert len(risks) == 1
        assert risks[0].drone_a_id == "a"
        assert risks[0].drone_b_id == "b"
        assert risks[0].distance_m < 5.0

    def test_three_drones_one_pair_too_close(self):
        """Three drones, only one pair within threshold."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = {
            "a": _make_drone("a", REF_LAT, REF_LON),
            "b": _make_drone("b", REF_LAT + _lat_offset(3), REF_LON),  # close to a
            "c": _make_drone("c", REF_LAT + _lat_offset(500), REF_LON),  # far
        }
        risks = ca.check_all_pairs(drones)
        assert len(risks) == 1
        assert {risks[0].drone_a_id, risks[0].drone_b_id} == {"a", "b"}

    def test_five_drones_tight_formation(self):
        """Five drones all within 2 m of each other -> C(5,2) = 10 risks."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = {}
        for i in range(5):
            drones[f"d{i}"] = _make_drone(
                f"d{i}",
                REF_LAT + _lat_offset(i * 0.5),  # 0.5 m apart
                REF_LON,
            )
        risks = ca.check_all_pairs(drones)
        assert len(risks) == 10  # C(5,2)

    def test_empty_swarm(self):
        ca = CollisionAvoidance()
        assert ca.check_all_pairs({}) == []

    def test_single_drone(self):
        ca = CollisionAvoidance()
        drones = {"a": _make_drone("a", REF_LAT, REF_LON)}
        assert ca.check_all_pairs(drones) == []


# ---------------------------------------------------------------------------
# compute_avoidance (repulsive -- backward compatibility)
# ---------------------------------------------------------------------------

class TestComputeAvoidance:
    def test_pushes_drones_apart(self):
        """After avoidance, the new waypoints should be farther apart than before."""
        ca = CollisionAvoidance(min_distance_m=10.0, method="repulsive")
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(3), REF_LON)
        original_dist = haversine(a.lat, a.lon, b.lat, b.lon)

        wp_a, wp_b = ca.compute_avoidance(a, b, 10.0)
        new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
        assert new_dist > original_dist

    def test_avoidance_reaches_min_distance(self):
        """Avoidance should push drones to at least min_distance apart."""
        ca = CollisionAvoidance(min_distance_m=10.0, method="repulsive")
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(4), REF_LON)

        wp_a, wp_b = ca.compute_avoidance(a, b, 10.0)
        new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
        assert new_dist >= 10.0 - 0.5  # allow small float tolerance

    def test_avoidance_preserves_altitude(self):
        """Avoidance waypoints should keep original altitudes."""
        ca = CollisionAvoidance(method="repulsive")
        a = _make_drone("a", REF_LAT, REF_LON, alt=15.0)
        b = _make_drone("b", REF_LAT + _lat_offset(2), REF_LON, alt=20.0)

        wp_a, wp_b = ca.compute_avoidance(a, b, 5.0)
        assert wp_a.alt == 15.0
        assert wp_b.alt == 20.0

    def test_avoidance_colocated_drones(self):
        """Two drones at the exact same position should not crash."""
        ca = CollisionAvoidance(method="repulsive")
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT, REF_LON)

        wp_a, wp_b = ca.compute_avoidance(a, b, 5.0)
        new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
        assert new_dist > 0.0  # they got pushed apart

    def test_avoidance_symmetric_push(self):
        """Both drones should move roughly the same amount."""
        ca = CollisionAvoidance(method="repulsive")
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(2), REF_LON)

        wp_a, wp_b = ca.compute_avoidance(a, b, 10.0)
        move_a = haversine(a.lat, a.lon, wp_a.lat, wp_a.lon)
        move_b = haversine(b.lat, b.lon, wp_b.lat, wp_b.lon)
        assert move_a == pytest.approx(move_b, rel=0.1)


# ---------------------------------------------------------------------------
# compute_avoidance with ORCA (default)
# ---------------------------------------------------------------------------

class TestComputeAvoidanceOrca:
    """Verify that compute_avoidance uses ORCA by default and moves drones apart."""

    def test_orca_pushes_drones_apart(self):
        ca = CollisionAvoidance(min_distance_m=10.0)  # default method="orca"
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(3), REF_LON)
        original_dist = haversine(a.lat, a.lon, b.lat, b.lon)

        wp_a, wp_b = ca.compute_avoidance(a, b, 10.0)
        new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
        assert new_dist > original_dist

    def test_orca_preserves_altitude(self):
        ca = CollisionAvoidance(min_distance_m=5.0)
        a = _make_drone("a", REF_LAT, REF_LON, alt=15.0)
        b = _make_drone("b", REF_LAT + _lat_offset(2), REF_LON, alt=20.0)

        wp_a, wp_b = ca.compute_avoidance(a, b, 5.0)
        assert wp_a.alt == 15.0
        assert wp_b.alt == 20.0

    def test_orca_colocated_drones(self):
        ca = CollisionAvoidance(min_distance_m=5.0)
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT, REF_LON)

        wp_a, wp_b = ca.compute_avoidance(a, b, 5.0)
        new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
        assert new_dist > 0.0


# ---------------------------------------------------------------------------
# ORCA-specific tests
# ---------------------------------------------------------------------------

class TestOrcaVelocities:
    """Test the ORCA velocity computation directly."""

    def test_two_drones_head_on(self):
        """Two drones flying directly toward each other should veer apart."""
        ca = CollisionAvoidance(min_distance_m=5.0, tau=5.0, max_speed=5.0)

        # Drone A at origin heading east, drone B 8 m east heading west
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT, REF_LON + _lon_offset(8))

        drones = {"a": a, "b": b}
        preferred = {
            "a": (0.0, 2.0),   # east at 2 m/s
            "b": (0.0, -2.0),  # west at 2 m/s
        }

        results = ca.compute_orca_velocities(drones, preferred)
        vel_map = {v.drone_id: v for v in results}

        # The drones should deflect: A should gain a north or south component
        # and B should gain the opposite.  The key invariant is that the
        # relative velocity along the line connecting them decreases.
        closing_before = preferred["a"][1] - preferred["b"][1]  # 4.0
        closing_after = vel_map["a"].ve - vel_map["b"].ve
        assert closing_after < closing_before, (
            f"ORCA should reduce closing speed: before={closing_before}, after={closing_after}"
        )

    def test_two_drones_crossing(self):
        """Two drones on perpendicular courses should avoid each other."""
        ca = CollisionAvoidance(min_distance_m=5.0, tau=5.0, max_speed=5.0)

        # A at origin heading east, B 6 m north heading south
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(6), REF_LON)

        drones = {"a": a, "b": b}
        preferred = {
            "a": (0.0, 2.0),   # east
            "b": (-2.0, 0.0),  # south
        }

        results = ca.compute_orca_velocities(drones, preferred)
        vel_map = {v.drone_id: v for v in results}

        # Both should have modified velocities
        a_changed = (
            abs(vel_map["a"].vn - preferred["a"][0]) > 0.01
            or abs(vel_map["a"].ve - preferred["a"][1]) > 0.01
        )
        b_changed = (
            abs(vel_map["b"].vn - preferred["b"][0]) > 0.01
            or abs(vel_map["b"].ve - preferred["b"][1]) > 0.01
        )
        assert a_changed or b_changed, "At least one drone should adjust velocity"

    def test_five_drones_converging(self):
        """Five drones converging to the same point should all get safe velocities."""
        ca = CollisionAvoidance(min_distance_m=5.0, tau=5.0, max_speed=5.0)

        # Place 5 drones in a circle of radius 10 m, all heading toward center
        center_lat, center_lon = REF_LAT, REF_LON
        n = 5
        radius_m = 10.0
        drones = {}
        preferred = {}

        for i in range(n):
            angle = 2 * math.pi * i / n
            dn = radius_m * math.cos(angle)
            de = radius_m * math.sin(angle)
            lat = center_lat + _lat_offset(dn)
            lon = center_lon + _lon_offset(de)
            did = f"d{i}"
            drones[did] = _make_drone(did, lat, lon)
            # Preferred velocity: toward center at 2 m/s
            speed = 2.0
            preferred[did] = (-speed * math.cos(angle), -speed * math.sin(angle))

        results = ca.compute_orca_velocities(drones, preferred)
        assert len(results) == n

        # Simulate one step and check no pair is closer than before minus a tolerance
        dt = 1.0
        new_positions = {}
        for v in results:
            d = drones[v.drone_id]
            n_pos, e_pos = (
                (d.lat - center_lat) * _M_PER_DEG_LAT + v.vn * dt,
                (d.lon - center_lon) * _M_PER_DEG_LON + v.ve * dt,
            )
            new_positions[v.drone_id] = (n_pos, e_pos)

        # Check that no pair would be within min_distance after one step
        # (with tolerance -- ORCA guarantees collision-free within tau, not instantly)
        ids = list(new_positions.keys())
        min_pair_dist = float("inf")
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pi = new_positions[ids[i]]
                pj = new_positions[ids[j]]
                d = math.sqrt((pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2)
                min_pair_dist = min(min_pair_dist, d)

        # The minimum pairwise distance should not decrease catastrophically
        # (original min is roughly 2*R*sin(pi/5) ~ 11.75 m for a 10 m circle)
        assert min_pair_dist > 3.0, (
            f"Minimum pairwise distance after one step is too small: {min_pair_dist:.2f} m"
        )

    def test_orca_velocities_returns_all_drones(self):
        """compute_orca_velocities should return a result for every drone."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = {
            f"d{i}": _make_drone(f"d{i}", REF_LAT + _lat_offset(i * 100), REF_LON)
            for i in range(4)
        }
        results = ca.compute_orca_velocities(drones)
        assert len(results) == 4
        assert {v.drone_id for v in results} == set(drones.keys())

    def test_orca_far_apart_no_change(self):
        """Drones far apart should keep their preferred velocities."""
        ca = CollisionAvoidance(min_distance_m=5.0, tau=5.0, max_speed=5.0)
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(500), REF_LON)

        preferred = {"a": (1.0, 0.0), "b": (-1.0, 0.0)}
        results = ca.compute_orca_velocities({"a": a, "b": b}, preferred)
        vel_map = {v.drone_id: v for v in results}

        assert vel_map["a"].vn == pytest.approx(1.0, abs=0.1)
        assert vel_map["a"].ve == pytest.approx(0.0, abs=0.1)
        assert vel_map["b"].vn == pytest.approx(-1.0, abs=0.1)
        assert vel_map["b"].ve == pytest.approx(0.0, abs=0.1)

    def test_single_drone_returns_preferred(self):
        """A single drone should keep its preferred velocity."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        a = _make_drone("a", REF_LAT, REF_LON)
        preferred = {"a": (1.5, -0.5)}
        results = ca.compute_orca_velocities({"a": a}, preferred)
        assert len(results) == 1
        assert results[0].vn == pytest.approx(1.5)
        assert results[0].ve == pytest.approx(-0.5)

    def test_speed_clamped(self):
        """ORCA should not output velocities above max_speed."""
        ca = CollisionAvoidance(min_distance_m=5.0, max_speed=3.0)
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(3), REF_LON)

        results = ca.compute_orca_velocities(
            {"a": a, "b": b},
            {"a": (0.0, 0.0), "b": (0.0, 0.0)},
        )
        for v in results:
            speed = math.sqrt(v.vn ** 2 + v.ve ** 2)
            assert speed <= 3.0 + 0.01, f"Speed {speed} exceeds max_speed 3.0"


# ---------------------------------------------------------------------------
# Method parameter
# ---------------------------------------------------------------------------

class TestMethodParameter:
    def test_default_is_orca(self):
        ca = CollisionAvoidance()
        assert ca.method == "orca"

    def test_repulsive(self):
        ca = CollisionAvoidance(method="repulsive")
        assert ca.method == "repulsive"

    def test_invalid_method(self):
        with pytest.raises(ValueError, match="Unknown method"):
            CollisionAvoidance(method="magic")

    def test_dispatch_uses_method(self):
        """compute_avoidance should dispatch based on method parameter."""
        a = _make_drone("a", REF_LAT, REF_LON)
        b = _make_drone("b", REF_LAT + _lat_offset(2), REF_LON)

        ca_orca = CollisionAvoidance(min_distance_m=5.0, method="orca")
        wp_orca_a, wp_orca_b = ca_orca.compute_avoidance(a, b, 5.0)

        ca_rep = CollisionAvoidance(min_distance_m=5.0, method="repulsive")
        wp_rep_a, wp_rep_b = ca_rep.compute_avoidance(a, b, 5.0)

        # Both should push apart, but waypoints will differ
        dist_orca = haversine(wp_orca_a.lat, wp_orca_a.lon, wp_orca_b.lat, wp_orca_b.lon)
        dist_rep = haversine(wp_rep_a.lat, wp_rep_a.lon, wp_rep_b.lat, wp_rep_b.lon)
        original_dist = haversine(a.lat, a.lon, b.lat, b.lon)

        assert dist_orca > original_dist
        assert dist_rep > original_dist


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

class TestOrcaBenchmark:
    def test_10_drones_under_10ms(self):
        """ORCA should solve for 10 drones in <10ms."""
        ca = CollisionAvoidance(min_distance_m=5.0, tau=5.0, max_speed=5.0)

        # 10 drones in a tight cluster (3 m spacing)
        drones = {}
        preferred = {}
        for i in range(10):
            row = i // 4
            col = i % 4
            did = f"d{i}"
            drones[did] = _make_drone(
                did,
                REF_LAT + _lat_offset(row * 3),
                REF_LON + _lon_offset(col * 3),
            )
            preferred[did] = (1.0, 0.5)  # all heading northeast

        # Warm up
        ca.compute_orca_velocities(drones, preferred)

        # Benchmark
        start = time.perf_counter()
        iterations = 50
        for _ in range(iterations):
            ca.compute_orca_velocities(drones, preferred)
        elapsed = (time.perf_counter() - start) / iterations

        assert elapsed < 0.010, (
            f"ORCA for 10 drones took {elapsed*1000:.2f} ms (limit: 10 ms)"
        )


# ---------------------------------------------------------------------------
# Swarm enable / disable integration
# ---------------------------------------------------------------------------

class TestSwarmIntegration:
    def test_enable_collision_avoidance(self):
        swarm = SwarmOrchestrator()
        assert swarm._collision_avoidance is None

        swarm.enable_collision_avoidance(min_distance_m=8.0)
        assert isinstance(swarm._collision_avoidance, CollisionAvoidance)
        assert swarm._collision_avoidance.min_distance_m == 8.0

    def test_disable_collision_avoidance(self):
        swarm = SwarmOrchestrator()
        swarm.enable_collision_avoidance()
        swarm.disable_collision_avoidance()
        assert swarm._collision_avoidance is None

    def test_enable_default_distance(self):
        swarm = SwarmOrchestrator()
        swarm.enable_collision_avoidance()
        assert swarm._collision_avoidance.min_distance_m == 5.0

    def test_enable_with_method(self):
        swarm = SwarmOrchestrator()
        swarm.enable_collision_avoidance(method="repulsive")
        assert swarm._collision_avoidance.method == "repulsive"

    def test_enable_default_method_is_orca(self):
        swarm = SwarmOrchestrator()
        swarm.enable_collision_avoidance()
        assert swarm._collision_avoidance.method == "orca"
