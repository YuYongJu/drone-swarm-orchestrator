"""Tests for the drone health scoring system (drone_swarm.health).

Covers individual metric scorers, composite scoring, edge cases,
and combined degradation scenarios.
"""

import time

import pytest

from drone_swarm.drone import Drone, DroneRole
from drone_swarm.health import (
    _score_battery,
    _score_comms,
    _score_gps,
    _score_heartbeat,
    _score_vibration,
    compute_health_score,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(**overrides) -> Drone:
    """Create a drone with sensible defaults for health testing."""
    defaults = dict(
        drone_id="alpha",
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
        battery_pct=100.0,
        gps_satellite_count=12,
        last_heartbeat=time.time(),
        vibration_level=-1.0,
        message_loss_rate=-1.0,
    )
    defaults.update(overrides)
    return Drone(**defaults)


# ---------------------------------------------------------------------------
# Full health (all metrics good) = 100
# ---------------------------------------------------------------------------

class TestFullHealth:
    def test_perfect_health_score(self):
        drone = _make_drone(
            battery_pct=100.0,
            gps_satellite_count=12,
            last_heartbeat=time.time(),
            vibration_level=0.0,
            message_loss_rate=0.0,
        )
        score = compute_health_score(drone)
        assert score == pytest.approx(100.0)

    def test_all_good_defaults_high_score(self):
        """With no vibration/comms data (defaults -1), assume OK -> 100."""
        drone = _make_drone()
        score = compute_health_score(drone)
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Low battery = reduced score
# ---------------------------------------------------------------------------

class TestBatteryScoring:
    def test_full_battery(self):
        assert _score_battery(100.0) == 100.0

    def test_above_80_is_100(self):
        assert _score_battery(85.0) == 100.0

    def test_at_80_is_100(self):
        assert _score_battery(80.0) == 100.0

    def test_at_10_is_0(self):
        assert _score_battery(10.0) == 0.0

    def test_below_10_is_0(self):
        assert _score_battery(5.0) == 0.0

    def test_midpoint_45(self):
        # 45% -> (45-10)/(80-10)*100 = 35/70*100 = 50
        assert _score_battery(45.0) == pytest.approx(50.0)

    def test_low_battery_reduces_composite(self):
        drone = _make_drone(battery_pct=10.0)
        score = compute_health_score(drone)
        # Battery is 0, so score = 100*(0.25+0.10+0.10) + 0*0.30 + gps*0.25
        # With full GPS and fresh heartbeat: 70 + 25 = should be ~70
        assert score < 80.0


# ---------------------------------------------------------------------------
# No GPS = reduced score
# ---------------------------------------------------------------------------

class TestGPSScoring:
    def test_many_sats(self):
        assert _score_gps(12) == 100.0

    def test_8_sats(self):
        assert _score_gps(8) == 100.0

    def test_4_sats(self):
        assert _score_gps(4) == 0.0

    def test_0_sats(self):
        assert _score_gps(0) == 0.0

    def test_6_sats(self):
        # (6-4)/(8-4)*100 = 50
        assert _score_gps(6) == pytest.approx(50.0)

    def test_no_gps_reduces_composite(self):
        drone = _make_drone(gps_satellite_count=0)
        score = compute_health_score(drone)
        assert score < 80.0


# ---------------------------------------------------------------------------
# Stale heartbeat = reduced score
# ---------------------------------------------------------------------------

class TestHeartbeatScoring:
    def test_fresh_heartbeat(self):
        assert _score_heartbeat(time.time()) == pytest.approx(100.0, abs=1.0)

    def test_stale_heartbeat(self):
        assert _score_heartbeat(time.time() - 15.0) == 0.0

    def test_no_heartbeat(self):
        assert _score_heartbeat(0.0) == 0.0

    def test_5s_stale(self):
        # (10-5)/(10-1)*100 = 5/9*100 ~= 55.6
        score = _score_heartbeat(time.time() - 5.0)
        assert 50.0 < score < 60.0

    def test_stale_heartbeat_reduces_composite(self):
        drone = _make_drone(last_heartbeat=time.time() - 20.0)
        score = compute_health_score(drone)
        assert score < 80.0


# ---------------------------------------------------------------------------
# Vibration scoring
# ---------------------------------------------------------------------------

class TestVibrationScoring:
    def test_low_vibration(self):
        assert _score_vibration(2.0) == 100.0

    def test_high_vibration(self):
        assert _score_vibration(35.0) == 0.0

    def test_no_data(self):
        assert _score_vibration(-1.0) == 100.0

    def test_mid_vibration(self):
        # 17.5 -> (30-17.5)/(30-5)*100 = 12.5/25*100 = 50
        assert _score_vibration(17.5) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Communication scoring
# ---------------------------------------------------------------------------

class TestCommsScoring:
    def test_no_loss(self):
        assert _score_comms(0.0) == 100.0

    def test_high_loss(self):
        assert _score_comms(0.6) == 0.0

    def test_no_data(self):
        assert _score_comms(-1.0) == 100.0

    def test_25_percent_loss(self):
        # (0.5-0.25)/0.5*100 = 50
        assert _score_comms(0.25) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Combined degradation
# ---------------------------------------------------------------------------

class TestCombinedDegradation:
    def test_multiple_issues(self):
        """Low battery + no GPS + stale heartbeat -> very low score."""
        drone = _make_drone(
            battery_pct=10.0,
            gps_satellite_count=0,
            last_heartbeat=time.time() - 20.0,
        )
        score = compute_health_score(drone)
        assert score < 30.0

    def test_all_bad(self):
        """Everything degraded -> near zero."""
        drone = _make_drone(
            battery_pct=0.0,
            gps_satellite_count=0,
            last_heartbeat=0.0,
            vibration_level=50.0,
            message_loss_rate=1.0,
        )
        score = compute_health_score(drone)
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Score bounds
# ---------------------------------------------------------------------------

class TestScoreBounds:
    def test_score_never_below_0(self):
        drone = _make_drone(
            battery_pct=0.0,
            gps_satellite_count=0,
            last_heartbeat=0.0,
            vibration_level=100.0,
            message_loss_rate=1.0,
        )
        score = compute_health_score(drone)
        assert score >= 0.0

    def test_score_never_above_100(self):
        drone = _make_drone(
            battery_pct=200.0,  # hypothetical over-reading
            gps_satellite_count=30,
            last_heartbeat=time.time() + 10,  # future timestamp
            vibration_level=0.0,
            message_loss_rate=0.0,
        )
        score = compute_health_score(drone)
        assert score <= 100.0
