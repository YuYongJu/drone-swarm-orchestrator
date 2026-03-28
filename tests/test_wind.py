"""Tests for drone_swarm.wind -- wind estimation from tilt angles."""

import math

import pytest

from drone_swarm.drone import Drone, DroneRole, DroneStatus
from drone_swarm.wind import WindEstimate, WindEstimator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(drone_id: str = "alpha", **kwargs) -> Drone:
    defaults = dict(
        drone_id=drone_id,
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
        status=DroneStatus.AIRBORNE,
    )
    defaults.update(kwargs)
    return Drone(**defaults)


# ---------------------------------------------------------------------------
# WindEstimate dataclass
# ---------------------------------------------------------------------------

class TestWindEstimate:
    def test_construction(self):
        est = WindEstimate(speed_ms=5.0, direction_deg=180.0, confidence=0.8)
        assert est.speed_ms == 5.0
        assert est.direction_deg == 180.0
        assert est.confidence == 0.8

    def test_equality(self):
        a = WindEstimate(1.0, 90.0, 0.5)
        b = WindEstimate(1.0, 90.0, 0.5)
        assert a == b


# ---------------------------------------------------------------------------
# Zero tilt = no wind
# ---------------------------------------------------------------------------

class TestZeroTilt:
    def test_zero_tilt_yields_zero_wind(self):
        est = WindEstimator()
        drone = _make_drone()
        est.update(drone, attitude_roll=0.0, attitude_pitch=0.0,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        assert wind.speed_ms == pytest.approx(0.0, abs=0.01)

    def test_zero_tilt_low_confidence(self):
        est = WindEstimator()
        drone = _make_drone()
        est.update(drone, attitude_roll=0.0, attitude_pitch=0.0,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        assert wind.confidence == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# No update = zero wind with zero confidence
# ---------------------------------------------------------------------------

class TestNoUpdate:
    def test_no_update_returns_zero(self):
        est = WindEstimator()
        wind = est.get_wind()
        assert wind.speed_ms == 0.0
        assert wind.confidence == 0.0


# ---------------------------------------------------------------------------
# Known tilt angle = expected wind speed
# ---------------------------------------------------------------------------

class TestKnownTilt:
    def test_pitch_only_gives_expected_speed(self):
        """A 10-degree nose-down pitch with k=9.81 should yield ~1.73 m/s."""
        est = WindEstimator(ema_alpha=1.0)  # no smoothing
        drone = _make_drone()
        pitch = math.radians(10.0)
        est.update(drone, attitude_roll=0.0, attitude_pitch=-pitch,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        expected = 9.81 * math.tan(pitch)
        assert wind.speed_ms == pytest.approx(expected, rel=0.01)

    def test_roll_only_gives_expected_speed(self):
        est = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()
        roll = math.radians(5.0)
        est.update(drone, attitude_roll=-roll, attitude_pitch=0.0,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        expected = 9.81 * math.tan(roll)
        assert wind.speed_ms == pytest.approx(expected, rel=0.01)

    def test_larger_tilt_gives_higher_speed(self):
        est = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()
        small_pitch = math.radians(3.0)
        est.update(drone, 0.0, -small_pitch, 0.0, 0.0)
        w1 = est.get_wind().speed_ms

        est2 = WindEstimator(ema_alpha=1.0)
        big_pitch = math.radians(15.0)
        est2.update(drone, 0.0, -big_pitch, 0.0, 0.0)
        w2 = est2.get_wind().speed_ms

        assert w2 > w1


# ---------------------------------------------------------------------------
# Wind direction from tilt direction
# ---------------------------------------------------------------------------

class TestWindDirection:
    def test_nose_down_heading_north_means_wind_from_north(self):
        """Drone heading north (0 deg), pitched nose-down => tilting toward
        north => wind coming FROM the north (0 deg)."""
        est = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()
        pitch = math.radians(10.0)
        # Nose down = negative pitch in many conventions; the drone tilts
        # forward (toward heading) to fight headwind.
        est.update(drone, attitude_roll=0.0, attitude_pitch=-pitch,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        # Wind from ~0 degrees (north)
        assert wind.direction_deg == pytest.approx(0.0, abs=5.0)

    def test_roll_right_heading_north_means_wind_from_east(self):
        """Drone heading north, rolled right (positive roll removed from east
        side) => tilting east => wind from east (90 deg)."""
        est = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()
        roll = math.radians(10.0)
        est.update(drone, attitude_roll=-roll, attitude_pitch=0.0,
                   groundspeed=0.0, heading=0.0)
        wind = est.get_wind()
        # Wind from ~90 degrees (east)
        assert wind.direction_deg == pytest.approx(90.0, abs=5.0)

    def test_heading_rotation_shifts_direction(self):
        """Same tilt with different headings should shift the wind direction."""
        est1 = WindEstimator(ema_alpha=1.0)
        est2 = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()
        pitch = math.radians(10.0)

        est1.update(drone, 0.0, -pitch, 0.0, heading=0.0)
        est2.update(drone, 0.0, -pitch, 0.0, heading=90.0)

        dir1 = est1.get_wind().direction_deg
        dir2 = est2.get_wind().direction_deg
        # The difference should be ~90 degrees
        diff = (dir2 - dir1) % 360
        assert diff == pytest.approx(90.0, abs=5.0)


# ---------------------------------------------------------------------------
# Max tilt clamping
# ---------------------------------------------------------------------------

class TestMaxTiltClamp:
    def test_extreme_tilt_clamped(self):
        """Tilt beyond max_tilt_rad should be clamped -- speed should not
        exceed k * tan(max_tilt_rad)."""
        est = WindEstimator(ema_alpha=1.0, max_tilt_rad=0.35)
        drone = _make_drone()
        extreme_pitch = math.radians(45.0)  # way beyond 0.35 rad
        est.update(drone, 0.0, -extreme_pitch, 0.0, 0.0)
        wind = est.get_wind()
        max_speed = 9.81 * math.tan(0.35)
        assert wind.speed_ms == pytest.approx(max_speed, rel=0.01)


# ---------------------------------------------------------------------------
# EMA smoothing
# ---------------------------------------------------------------------------

class TestSmoothing:
    def test_smoothing_dampens_transient(self):
        """With low alpha, a single spike should not fully appear in output."""
        est = WindEstimator(ema_alpha=0.1)
        drone = _make_drone()
        pitch = math.radians(15.0)
        est.update(drone, 0.0, -pitch, 0.0, 0.0)
        wind = est.get_wind()
        unsmoothed = 9.81 * math.tan(pitch)
        # With alpha=0.1 and starting from 0, first output ≈ 0.1 * raw
        assert wind.speed_ms < unsmoothed * 0.5


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_confidence_increases_with_speed(self):
        est1 = WindEstimator(ema_alpha=1.0)
        est2 = WindEstimator(ema_alpha=1.0)
        drone = _make_drone()

        est1.update(drone, 0.0, -math.radians(2.0), 0.0, 0.0)
        est2.update(drone, 0.0, -math.radians(15.0), 0.0, 0.0)

        assert est2.get_wind().confidence > est1.get_wind().confidence

    def test_confidence_capped_at_one(self):
        est = WindEstimator(ema_alpha=1.0, k_factor=50.0)
        drone = _make_drone()
        est.update(drone, 0.0, -math.radians(20.0), 0.0, 0.0)
        assert est.get_wind().confidence <= 1.0


# ---------------------------------------------------------------------------
# Swarm averaging
# ---------------------------------------------------------------------------

class TestSwarmWind:
    def test_swarm_average_speed(self):
        """Average of two drones with different speeds should be the mean."""
        d1 = _make_drone("alpha")
        d2 = _make_drone("bravo")
        drones = {"alpha": d1, "bravo": d2}

        e1 = WindEstimator(ema_alpha=1.0)
        e2 = WindEstimator(ema_alpha=1.0)

        # Different pitch angles -> different speeds
        e1.update(d1, 0.0, -math.radians(5.0), 0.0, 0.0)
        e2.update(d2, 0.0, -math.radians(15.0), 0.0, 0.0)

        estimators = {"alpha": e1, "bravo": e2}
        swarm_wind = WindEstimator.get_swarm_wind(drones, estimators)

        s1 = e1.get_wind().speed_ms
        s2 = e2.get_wind().speed_ms
        assert swarm_wind.speed_ms == pytest.approx((s1 + s2) / 2, rel=0.01)

    def test_swarm_no_estimators_returns_zero(self):
        drones = {"alpha": _make_drone()}
        swarm_wind = WindEstimator.get_swarm_wind(drones, {})
        assert swarm_wind.speed_ms == 0.0
        assert swarm_wind.confidence == 0.0

    def test_swarm_single_drone_matches_individual(self):
        d1 = _make_drone()
        e1 = WindEstimator(ema_alpha=1.0)
        e1.update(d1, 0.0, -math.radians(10.0), 0.0, 0.0)

        individual = e1.get_wind()
        swarm = WindEstimator.get_swarm_wind({"alpha": d1}, {"alpha": e1})
        assert swarm.speed_ms == pytest.approx(individual.speed_ms, rel=0.01)

    def test_swarm_averaging_reduces_noise(self):
        """Multiple drones with noisy but same-mean tilt should converge
        closer to the true value than any single drone."""
        # True wind: 10-degree pitch worth of wind
        true_pitch = math.radians(10.0)
        true_speed = 9.81 * math.tan(true_pitch)

        # Create 5 drones with noisy pitch readings around the true value
        import random
        random.seed(42)
        drones = {}
        estimators = {}
        errors = []
        for i in range(5):
            did = f"drone_{i}"
            d = _make_drone(did)
            drones[did] = d
            e = WindEstimator(ema_alpha=1.0)
            noisy_pitch = true_pitch + random.gauss(0, math.radians(2.0))
            e.update(d, 0.0, -noisy_pitch, 0.0, 0.0)
            estimators[did] = e
            errors.append(abs(e.get_wind().speed_ms - true_speed))

        swarm_wind = WindEstimator.get_swarm_wind(drones, estimators)
        swarm_error = abs(swarm_wind.speed_ms - true_speed)
        mean_individual_error = sum(errors) / len(errors)

        # Swarm average should be closer to truth than individual average error
        assert swarm_error < mean_individual_error
