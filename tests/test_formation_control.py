"""Tests for drone_swarm.formation_control -- consensus-based formation hold.

All tests run WITHOUT pymavlink connections or SITL. We exercise the
FormationController's in-memory logic: error computation, PID correction,
clamping, GPS conversion, and SwarmOrchestrator integration.
"""


import pytest

from drone_swarm.drone import Drone, DroneStatus
from drone_swarm.formation_control import (
    FormationController,
    FormationGains,
    compute_formation_error,
    latlon_to_ned,
    ned_to_latlon,
)
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(
    drone_id: str,
    lat: float = 35.0,
    lon: float = -117.0,
    alt: float = 10.0,
    status: DroneStatus = DroneStatus.AIRBORNE,
) -> Drone:
    """Create a drone with a known position (no MAVLink connection)."""
    d = Drone(drone_id=drone_id, connection_string="test://")
    d.lat = lat
    d.lon = lon
    d.alt = alt
    d.status = status
    return d


# ---------------------------------------------------------------------------
# GPS coordinate conversion
# ---------------------------------------------------------------------------

class TestNEDConversion:
    """Test NED <-> lat/lon conversions used by the formation controller."""

    def test_ned_to_latlon_zero_offset(self):
        """Zero NED offset returns the reference point."""
        wp = ned_to_latlon(35.0, -117.0, 10.0, 0.0, 0.0, 0.0)
        assert wp.lat == pytest.approx(35.0, abs=1e-9)
        assert wp.lon == pytest.approx(-117.0, abs=1e-9)
        assert wp.alt == pytest.approx(10.0, abs=1e-6)

    def test_ned_to_latlon_north_offset(self):
        """100m north should increase latitude."""
        wp = ned_to_latlon(35.0, -117.0, 10.0, 100.0, 0.0, 0.0)
        assert wp.lat > 35.0
        # 100m / 111320 m/deg ~ 0.000898 degrees
        assert wp.lat == pytest.approx(35.0 + 100.0 / 111320.0, abs=1e-7)
        assert wp.lon == pytest.approx(-117.0, abs=1e-9)

    def test_ned_to_latlon_east_offset(self):
        """100m east should increase longitude (in northern hemisphere)."""
        wp = ned_to_latlon(35.0, -117.0, 10.0, 0.0, 100.0, 0.0)
        assert wp.lon > -117.0
        assert wp.lat == pytest.approx(35.0, abs=1e-9)

    def test_ned_to_latlon_down_offset(self):
        """Positive down offset should decrease altitude."""
        wp = ned_to_latlon(35.0, -117.0, 10.0, 0.0, 0.0, 5.0)
        assert wp.alt == pytest.approx(5.0, abs=1e-6)

    def test_roundtrip_ned_latlon(self):
        """NED -> lat/lon -> NED should be identity."""
        n, e, d = 50.0, -30.0, 2.0
        wp = ned_to_latlon(35.0, -117.0, 10.0, n, e, d)
        n2, e2, d2 = latlon_to_ned(35.0, -117.0, 10.0, wp.lat, wp.lon, wp.alt)
        assert n2 == pytest.approx(n, abs=0.01)
        assert e2 == pytest.approx(e, abs=0.01)
        assert d2 == pytest.approx(d, abs=0.01)

    def test_latlon_to_ned_same_point(self):
        """Same point returns zero NED offset."""
        n, e, d = latlon_to_ned(35.0, -117.0, 10.0, 35.0, -117.0, 10.0)
        assert n == pytest.approx(0.0, abs=1e-9)
        assert e == pytest.approx(0.0, abs=1e-9)
        assert d == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# FormationGains
# ---------------------------------------------------------------------------

class TestFormationGains:
    def test_defaults(self):
        g = FormationGains()
        assert g.kp == 0.8
        assert g.ki == 0.0
        assert g.kd == 0.0
        assert g.max_correction_m == 5.0

    def test_custom_gains(self):
        g = FormationGains(kp=1.2, ki=0.1, kd=0.05, max_correction_m=10.0)
        assert g.kp == 1.2
        assert g.ki == 0.1
        assert g.kd == 0.05
        assert g.max_correction_m == 10.0


# ---------------------------------------------------------------------------
# compute_formation_error
# ---------------------------------------------------------------------------

class TestComputeFormationError:
    def test_zero_error_when_at_target(self):
        """Drones exactly at their target offsets should have zero error."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        # Place follower exactly 100m north of leader
        target = ned_to_latlon(35.0, -117.0, 10.0, 100.0, 0.0, 0.0)
        follower = _make_drone("f1", lat=target.lat, lon=target.lon, alt=target.alt)

        offsets = {"f1": (100.0, 0.0, 0.0)}
        errors = compute_formation_error(leader, {"f1": follower}, offsets)
        assert errors["f1"] == pytest.approx(0.0, abs=0.1)

    def test_known_error(self):
        """Follower 10m away from target should have ~10m error."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        # Target is 50m north; place follower 40m north (10m short)
        target_40m = ned_to_latlon(35.0, -117.0, 10.0, 40.0, 0.0, 0.0)
        follower = _make_drone("f1", lat=target_40m.lat, lon=target_40m.lon, alt=target_40m.alt)

        offsets = {"f1": (50.0, 0.0, 0.0)}
        errors = compute_formation_error(leader, {"f1": follower}, offsets)
        assert errors["f1"] == pytest.approx(10.0, abs=0.5)

    def test_3d_error(self):
        """Error computation includes altitude component."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        # Target: 0m north, 0m east, 5m down (alt=5). Place at alt=10 (5m too high).
        follower = _make_drone("f1", lat=35.0, lon=-117.0, alt=10.0)

        offsets = {"f1": (0.0, 0.0, 5.0)}  # 5m down = alt 5
        errors = compute_formation_error(leader, {"f1": follower}, offsets)
        assert errors["f1"] == pytest.approx(5.0, abs=0.5)

    def test_missing_offset_excluded(self):
        """Drones without offsets are not included in the error dict."""
        leader = _make_drone("leader")
        f1 = _make_drone("f1")
        f2 = _make_drone("f2")
        offsets = {"f1": (10.0, 0.0, 0.0)}  # no offset for f2
        errors = compute_formation_error(leader, {"f1": f1, "f2": f2}, offsets)
        assert "f1" in errors
        assert "f2" not in errors


# ---------------------------------------------------------------------------
# FormationController
# ---------------------------------------------------------------------------

class TestFormationController:
    def test_default_gains(self):
        ctrl = FormationController()
        assert ctrl.gains.kp == 0.8
        assert ctrl.gains.ki == 0.0
        assert ctrl.gains.kd == 0.0

    def test_custom_gains(self):
        g = FormationGains(kp=1.0)
        ctrl = FormationController(gains=g)
        assert ctrl.gains.kp == 1.0

    def test_set_formation(self):
        ctrl = FormationController()
        offsets = {"f1": (10.0, 0.0, 0.0), "f2": (0.0, 10.0, 0.0)}
        ctrl.set_formation(offsets)
        assert ctrl.offsets == offsets

    def test_set_formation_resets_state(self):
        ctrl = FormationController()
        ctrl._integral["f1"] = (1.0, 2.0, 3.0)
        ctrl._prev_error["f1"] = (4.0, 5.0, 6.0)
        ctrl.set_formation({"f1": (10.0, 0.0, 0.0)})
        assert ctrl._integral == {}
        assert ctrl._prev_error == {}

    def test_zero_error_produces_no_movement(self):
        """When a follower is at target, correction should be near current pos."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        target = ned_to_latlon(35.0, -117.0, 10.0, 50.0, 0.0, 0.0)
        f1 = _make_drone("f1", lat=target.lat, lon=target.lon, alt=target.alt)

        ctrl = FormationController()
        ctrl.set_formation({"f1": (50.0, 0.0, 0.0)})
        corrections = ctrl.compute_corrections(leader, {"f1": f1})

        wp = corrections["f1"]
        # Correction waypoint should be very close to current position
        n, e, d = latlon_to_ned(f1.lat, f1.lon, f1.alt, wp.lat, wp.lon, wp.alt)
        assert abs(n) < 0.1
        assert abs(e) < 0.1
        assert abs(d) < 0.1

    def test_correction_pushes_toward_target(self):
        """Correction should move the drone toward its target offset."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        # Target is 50m north, but follower is at leader's position (50m error)
        f1 = _make_drone("f1", lat=35.0, lon=-117.0, alt=10.0)

        ctrl = FormationController(gains=FormationGains(kp=0.5))
        ctrl.set_formation({"f1": (50.0, 0.0, 0.0)})
        corrections = ctrl.compute_corrections(leader, {"f1": f1})

        wp = corrections["f1"]
        # Correction should push north (positive latitude)
        n, e, d = latlon_to_ned(f1.lat, f1.lon, f1.alt, wp.lat, wp.lon, wp.alt)
        assert n > 0  # Pushed northward toward target

    def test_max_correction_clamping(self):
        """Corrections should be clamped to max_correction_m."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        # Follower 100m off target -- correction would be 80m with kp=0.8
        f1 = _make_drone("f1", lat=35.0, lon=-117.0, alt=10.0)

        gains = FormationGains(kp=0.8, max_correction_m=3.0)
        ctrl = FormationController(gains=gains)
        ctrl.set_formation({"f1": (100.0, 0.0, 0.0)})
        corrections = ctrl.compute_corrections(leader, {"f1": f1})

        wp = corrections["f1"]
        n, e, d = latlon_to_ned(f1.lat, f1.lon, f1.alt, wp.lat, wp.lon, wp.alt)
        # Each axis should be clamped to 3.0m
        assert abs(n) <= 3.0 + 0.01
        assert abs(e) <= 3.0 + 0.01
        assert abs(d) <= 3.0 + 0.01

    def test_max_correction_clamping_all_axes(self):
        """Clamping should work on each axis independently."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        f1 = _make_drone("f1", lat=35.0, lon=-117.0, alt=10.0)

        gains = FormationGains(kp=1.0, max_correction_m=2.0)
        ctrl = FormationController(gains=gains)
        # Large offset on all three axes
        ctrl.set_formation({"f1": (100.0, 100.0, -100.0)})
        corrections = ctrl.compute_corrections(leader, {"f1": f1})

        wp = corrections["f1"]
        n, e, d = latlon_to_ned(f1.lat, f1.lon, f1.alt, wp.lat, wp.lon, wp.alt)
        assert abs(n) <= 2.0 + 0.01
        assert abs(e) <= 2.0 + 0.01
        assert abs(d) <= 2.0 + 0.01

    def test_follower_without_offset_excluded(self):
        """Followers not in the offset dict should not get corrections."""
        leader = _make_drone("leader")
        f1 = _make_drone("f1")
        f2 = _make_drone("f2")

        ctrl = FormationController()
        ctrl.set_formation({"f1": (10.0, 0.0, 0.0)})
        corrections = ctrl.compute_corrections(leader, {"f1": f1, "f2": f2})

        assert "f1" in corrections
        assert "f2" not in corrections

    def test_multiple_followers(self):
        """Controller handles multiple followers simultaneously."""
        leader = _make_drone("leader", lat=35.0, lon=-117.0, alt=10.0)
        f1 = _make_drone("f1", lat=35.0, lon=-117.0, alt=10.0)
        f2 = _make_drone("f2", lat=35.0, lon=-117.0, alt=10.0)

        ctrl = FormationController()
        ctrl.set_formation({
            "f1": (15.0, -15.0, 0.0),
            "f2": (-15.0, 15.0, 0.0),
        })
        corrections = ctrl.compute_corrections(leader, {"f1": f1, "f2": f2})

        assert "f1" in corrections
        assert "f2" in corrections
        # They should be pushed in opposite directions
        c1 = corrections["f1"]
        n1, e1, _ = latlon_to_ned(
            f1.lat, f1.lon, f1.alt, c1.lat, c1.lon, c1.alt,
        )
        c2 = corrections["f2"]
        n2, e2, _ = latlon_to_ned(
            f2.lat, f2.lon, f2.alt, c2.lat, c2.lon, c2.alt,
        )
        assert n1 > 0  # pushed north
        assert n2 < 0  # pushed south
        assert e1 < 0  # pushed west
        assert e2 > 0  # pushed east


# ---------------------------------------------------------------------------
# SwarmOrchestrator integration
# ---------------------------------------------------------------------------

class TestSwarmFormationHold:
    def test_enable_formation_hold(self):
        orch = SwarmOrchestrator()
        orch.register_drone("leader", "test://1")
        orch.register_drone("f1", "test://2")

        offsets = {"f1": (10.0, 0.0, 0.0)}
        orch.enable_formation_hold("leader", offsets)

        assert orch._formation_controller is not None
        assert orch._formation_leader_id == "leader"
        assert orch._formation_controller.offsets == offsets

    def test_enable_formation_hold_with_custom_gains(self):
        orch = SwarmOrchestrator()
        orch.register_drone("leader", "test://1")

        gains = FormationGains(kp=1.5, max_correction_m=8.0)
        orch.enable_formation_hold("leader", {}, gains=gains)

        assert orch._formation_controller.gains.kp == 1.5
        assert orch._formation_controller.gains.max_correction_m == 8.0

    def test_enable_formation_hold_unknown_leader_raises(self):
        orch = SwarmOrchestrator()
        with pytest.raises(KeyError, match="not_registered"):
            orch.enable_formation_hold("not_registered", {})

    def test_disable_formation_hold(self):
        orch = SwarmOrchestrator()
        orch.register_drone("leader", "test://1")
        orch.enable_formation_hold("leader", {"f1": (10.0, 0.0, 0.0)})

        orch.disable_formation_hold()
        assert orch._formation_controller is None
        assert orch._formation_leader_id is None

    def test_formation_hold_initially_disabled(self):
        orch = SwarmOrchestrator()
        assert orch._formation_controller is None
        assert orch._formation_leader_id is None
