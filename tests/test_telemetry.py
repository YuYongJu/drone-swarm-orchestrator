"""Tests for drone_swarm.telemetry -- synchronous telemetry reader.

All tests run WITHOUT pymavlink or real MAVLink connections. We mock
the drone connection and feed fake MAVLink messages to verify telemetry
updates.
"""

import logging
import time
from unittest.mock import MagicMock

import pytest

from drone_swarm.drone import Drone, DroneRole, DroneStatus
from drone_swarm.telemetry import read_telemetry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(**kwargs) -> Drone:
    """Create a Drone with a mock connection by default."""
    defaults = dict(
        drone_id="alpha",
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
        status=DroneStatus.AIRBORNE,
    )
    defaults.update(kwargs)
    return Drone(**defaults)


def _make_msg(msg_type: str, **fields):
    """Create a mock MAVLink message with a get_type() method."""
    msg = MagicMock()
    msg.get_type.return_value = msg_type
    for k, v in fields.items():
        setattr(msg, k, v)
    return msg


# ---------------------------------------------------------------------------
# HEARTBEAT updates
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_heartbeat_updates_last_heartbeat(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        heartbeat = _make_msg("HEARTBEAT")
        conn.recv_match.side_effect = [heartbeat, None]

        before = time.time()
        read_telemetry(drone)
        after = time.time()

        assert before <= drone.last_heartbeat <= after

    def test_multiple_heartbeats_update_timestamp(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        hb1 = _make_msg("HEARTBEAT")
        hb2 = _make_msg("HEARTBEAT")
        conn.recv_match.side_effect = [hb1, hb2, None]

        read_telemetry(drone)
        # last_heartbeat should be updated (we just verify it's set)
        assert drone.last_heartbeat > 0


# ---------------------------------------------------------------------------
# GLOBAL_POSITION_INT updates
# ---------------------------------------------------------------------------

class TestPositionUpdates:
    def test_position_updates_lat_lon_alt_heading(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        pos = _make_msg(
            "GLOBAL_POSITION_INT",
            lat=349592000,       # 34.9592 * 1e7
            lon=-1178814000,     # -117.8814 * 1e7
            relative_alt=10000,  # 10.0 * 1000
            hdg=18000,           # 180.0 * 100
        )
        conn.recv_match.side_effect = [pos, None]

        read_telemetry(drone)

        assert drone.lat == pytest.approx(34.9592)
        assert drone.lon == pytest.approx(-117.8814)
        assert drone.alt == pytest.approx(10.0)
        assert drone.heading == pytest.approx(180.0)

    def test_zero_position(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        pos = _make_msg(
            "GLOBAL_POSITION_INT",
            lat=0, lon=0, relative_alt=0, hdg=0,
        )
        conn.recv_match.side_effect = [pos, None]

        read_telemetry(drone)

        assert drone.lat == 0.0
        assert drone.lon == 0.0
        assert drone.alt == 0.0
        assert drone.heading == 0.0


# ---------------------------------------------------------------------------
# SYS_STATUS battery updates
# ---------------------------------------------------------------------------

class TestBatteryUpdates:
    def test_battery_pct_updated(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        status = _make_msg("SYS_STATUS", battery_remaining=72)
        conn.recv_match.side_effect = [status, None]

        read_telemetry(drone)

        assert drone.battery_pct == 72

    def test_negative_battery_not_updated(self):
        """battery_remaining < 0 means not configured -- should not update."""
        drone = _make_drone()
        drone.battery_pct = 100.0
        conn = MagicMock()
        drone.connection = conn

        status = _make_msg("SYS_STATUS", battery_remaining=-1)
        conn.recv_match.side_effect = [status, None]

        read_telemetry(drone)

        # Should remain 100.0 because the condition `msg.battery_remaining >= 0` fails
        assert drone.battery_pct == 100.0


# ---------------------------------------------------------------------------
# None connection returns early
# ---------------------------------------------------------------------------

class TestNoneConnection:
    def test_none_connection_returns_early(self):
        drone = _make_drone()
        drone.connection = None
        # Should not raise -- just return immediately
        read_telemetry(drone)

    def test_none_connection_does_not_modify_drone(self):
        drone = _make_drone()
        drone.connection = None
        drone.lat = 1.0
        drone.battery_pct = 50.0

        read_telemetry(drone)

        assert drone.lat == 1.0
        assert drone.battery_pct == 50.0


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    def test_exception_is_logged_not_raised(self, caplog):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn
        conn.recv_match.side_effect = RuntimeError("serial port error")

        with caplog.at_level(logging.DEBUG, logger="drone_swarm.telemetry"):
            read_telemetry(drone)

        # Should not raise, and the error should be logged
        assert any("Telemetry read error" in rec.message for rec in caplog.records)

    def test_exception_on_get_type_is_caught(self, caplog):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        bad_msg = MagicMock()
        bad_msg.get_type.side_effect = AttributeError("broken message")
        conn.recv_match.side_effect = [bad_msg]

        with caplog.at_level(logging.DEBUG, logger="drone_swarm.telemetry"):
            read_telemetry(drone)

        # Should not raise


# ---------------------------------------------------------------------------
# Mixed message sequence
# ---------------------------------------------------------------------------

class TestMixedMessages:
    def test_processes_multiple_message_types(self):
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        hb = _make_msg("HEARTBEAT")
        pos = _make_msg(
            "GLOBAL_POSITION_INT",
            lat=420000000, lon=-710000000, relative_alt=5000, hdg=9000,
        )
        bat = _make_msg("SYS_STATUS", battery_remaining=88)
        unknown = _make_msg("ATTITUDE")  # not handled -- should be skipped
        conn.recv_match.side_effect = [hb, pos, bat, unknown, None]

        read_telemetry(drone)

        assert drone.last_heartbeat > 0
        assert drone.lat == pytest.approx(42.0)
        assert drone.lon == pytest.approx(-71.0)
        assert drone.alt == pytest.approx(5.0)
        assert drone.heading == pytest.approx(90.0)
        assert drone.battery_pct == 88

    def test_drains_up_to_50_messages(self):
        """read_telemetry should process at most 50 messages per call."""
        drone = _make_drone()
        conn = MagicMock()
        drone.connection = conn

        msgs = [_make_msg("HEARTBEAT") for _ in range(60)]
        conn.recv_match.side_effect = msgs

        read_telemetry(drone)

        # recv_match should be called exactly 50 times (the loop limit)
        assert conn.recv_match.call_count == 50
