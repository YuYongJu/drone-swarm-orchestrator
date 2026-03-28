"""Tests for drone_swarm.safety -- preflight checks and emergency actions.

All tests run WITHOUT pymavlink or real MAVLink connections. We mock
the connection objects and verify the check logic, result types, and
emergency command sequences.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from drone_swarm.drone import Drone, DroneStatus
from drone_swarm.safety import (
    CheckResult,
    check_battery,
    check_comms,
    check_compass,
    check_failsafes,
    check_gps,
    check_remote_id,
    check_vibration,
    emergency_kill,
    emergency_land,
    preflight_ok,
    run_preflight_checks,
)

# ---------------------------------------------------------------------------
# CheckResult dataclass
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_fields(self):
        r = CheckResult(drone_id="alpha", check="GPS", passed=True, detail="OK")
        assert r.drone_id == "alpha"
        assert r.check == "GPS"
        assert r.passed is True
        assert r.detail == "OK"

    def test_equality(self):
        a = CheckResult("a", "GPS", True, "ok")
        b = CheckResult("a", "GPS", True, "ok")
        assert a == b

    def test_inequality(self):
        a = CheckResult("a", "GPS", True, "ok")
        b = CheckResult("a", "GPS", False, "bad")
        assert a != b


# ---------------------------------------------------------------------------
# preflight_ok()
# ---------------------------------------------------------------------------

class TestPreflightOk:
    def test_all_passed(self):
        results = [
            CheckResult("a", "COMMS", True, "ok"),
            CheckResult("a", "GPS", True, "ok"),
            CheckResult("a", "BATTERY", True, "ok"),
        ]
        assert preflight_ok(results) is True

    def test_one_failed(self):
        results = [
            CheckResult("a", "COMMS", True, "ok"),
            CheckResult("a", "GPS", False, "no fix"),
            CheckResult("a", "BATTERY", True, "ok"),
        ]
        assert preflight_ok(results) is False

    def test_all_failed(self):
        results = [
            CheckResult("a", "COMMS", False, "no hb"),
            CheckResult("a", "GPS", False, "no fix"),
        ]
        assert preflight_ok(results) is False

    def test_empty_list(self):
        assert preflight_ok([]) is True


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

class TestCheckComms:
    def test_heartbeat_ok(self):
        conn = MagicMock()
        conn.wait_heartbeat.return_value = None
        result = check_comms(conn, "alpha", timeout=5.0)
        assert result.check == "COMMS"
        assert result.passed is True
        assert "Heartbeat OK" in result.detail
        conn.wait_heartbeat.assert_called_once_with(timeout=5.0)

    def test_no_heartbeat(self):
        conn = MagicMock()
        conn.wait_heartbeat.side_effect = Exception("timeout")
        result = check_comms(conn, "alpha")
        assert result.passed is False
        assert "No heartbeat" in result.detail


class TestCheckGps:
    def test_good_fix(self):
        conn = MagicMock()
        msg = MagicMock(fix_type=3, satellites_visible=10)
        conn.recv_match.return_value = msg
        result = check_gps(conn, "alpha")
        assert result.passed is True
        assert "10 satellites" in result.detail

    def test_no_data(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_gps(conn, "alpha")
        assert result.passed is False
        assert "No GPS data" in result.detail

    def test_no_3d_fix(self):
        conn = MagicMock()
        msg = MagicMock(fix_type=2, satellites_visible=8)
        conn.recv_match.return_value = msg
        result = check_gps(conn, "alpha")
        assert result.passed is False
        assert "No 3D fix" in result.detail

    def test_too_few_sats(self):
        conn = MagicMock()
        msg = MagicMock(fix_type=3, satellites_visible=4)
        conn.recv_match.return_value = msg
        result = check_gps(conn, "alpha")
        assert result.passed is False
        assert "Only 4 sats" in result.detail


class TestCheckBattery:
    def test_battery_ok(self):
        conn = MagicMock()
        msg = MagicMock(battery_remaining=95, voltage_battery=16800)
        conn.recv_match.return_value = msg
        result = check_battery(conn, "alpha", min_pct=80.0)
        assert result.passed is True
        assert "95%" in result.detail

    def test_battery_low(self):
        conn = MagicMock()
        msg = MagicMock(battery_remaining=50, voltage_battery=14200)
        conn.recv_match.return_value = msg
        result = check_battery(conn, "alpha", min_pct=80.0)
        assert result.passed is False
        assert "50%" in result.detail

    def test_no_data(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_battery(conn, "alpha")
        assert result.passed is False
        assert "No battery data" in result.detail

    def test_battery_monitor_not_configured(self):
        conn = MagicMock()
        msg = MagicMock(battery_remaining=-1, voltage_battery=0)
        conn.recv_match.return_value = msg
        result = check_battery(conn, "alpha")
        assert result.passed is False
        assert "not configured" in result.detail


class TestCheckCompass:
    def test_healthy(self):
        conn = MagicMock()
        msg = MagicMock(
            onboard_control_sensors_present=2,
            onboard_control_sensors_health=2,
        )
        conn.recv_match.return_value = msg
        result = check_compass(conn, "alpha")
        assert result.passed is True

    def test_not_present(self):
        conn = MagicMock()
        msg = MagicMock(
            onboard_control_sensors_present=0,
            onboard_control_sensors_health=0,
        )
        conn.recv_match.return_value = msg
        result = check_compass(conn, "alpha")
        assert result.passed is False
        assert "No compass detected" in result.detail

    def test_unhealthy(self):
        conn = MagicMock()
        msg = MagicMock(
            onboard_control_sensors_present=2,
            onboard_control_sensors_health=0,
        )
        conn.recv_match.return_value = msg
        result = check_compass(conn, "alpha")
        assert result.passed is False
        assert "unhealthy" in result.detail

    def test_no_data(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_compass(conn, "alpha")
        assert result.passed is False


class TestCheckRemoteId:
    def test_enabled(self):
        conn = MagicMock()
        msg = MagicMock(param_value=1.0)
        conn.recv_match.return_value = msg
        result = check_remote_id(conn, "alpha")
        assert result.passed is True
        assert "Remote ID enabled" in result.detail

    def test_disabled(self):
        conn = MagicMock()
        msg = MagicMock(param_value=0.0)
        conn.recv_match.return_value = msg
        result = check_remote_id(conn, "alpha")
        assert result.passed is False
        assert "DID_ENABLE=0" in result.detail

    def test_no_response(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_remote_id(conn, "alpha")
        assert result.passed is False
        assert "No response" in result.detail


class TestCheckVibration:
    def test_ok(self):
        conn = MagicMock()
        msg = MagicMock(vibration_x=5.0, vibration_y=3.0, vibration_z=4.0)
        conn.recv_match.return_value = msg
        result = check_vibration(conn, "alpha")
        assert result.passed is True
        assert "OK" in result.detail

    def test_excessive(self):
        conn = MagicMock()
        msg = MagicMock(vibration_x=35.0, vibration_y=10.0, vibration_z=10.0)
        conn.recv_match.return_value = msg
        result = check_vibration(conn, "alpha", threshold=30.0)
        assert result.passed is False
        assert "EXCESSIVE" in result.detail

    def test_no_data(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_vibration(conn, "alpha")
        assert result.passed is False


class TestCheckFailsafes:
    def test_all_correct(self):
        conn = MagicMock()
        # Return correct param values in order: FS_THR_ENABLE=1, FS_GCS_ENABLE=2, FENCE_ENABLE=1
        conn.recv_match.side_effect = [
            MagicMock(param_value=1.0),
            MagicMock(param_value=2.0),
            MagicMock(param_value=1.0),
        ]
        result = check_failsafes(conn, "alpha")
        assert result.passed is True
        assert "All failsafes configured" in result.detail

    def test_wrong_value(self):
        conn = MagicMock()
        conn.recv_match.side_effect = [
            MagicMock(param_value=0.0),  # FS_THR_ENABLE wrong
            MagicMock(param_value=2.0),
            MagicMock(param_value=1.0),
        ]
        result = check_failsafes(conn, "alpha")
        assert result.passed is False
        assert "FS_THR_ENABLE" in result.detail

    def test_no_response(self):
        conn = MagicMock()
        conn.recv_match.return_value = None
        result = check_failsafes(conn, "alpha")
        assert result.passed is False
        assert "no response" in result.detail


# ---------------------------------------------------------------------------
# run_preflight_checks()
# ---------------------------------------------------------------------------

class TestRunPreflightChecks:
    @patch("drone_swarm.safety.mavutil")
    def test_runs_all_checks(self, mock_mavutil):
        mock_conn = MagicMock()
        mock_mavutil.mavlink_connection.return_value = mock_conn

        # Set up mock to handle all the recv_match calls
        mock_conn.wait_heartbeat.return_value = None
        gps_msg = MagicMock(fix_type=3, satellites_visible=10)
        battery_msg = MagicMock(battery_remaining=95, voltage_battery=16800)
        MagicMock(
            onboard_control_sensors_present=2,
            onboard_control_sensors_health=2,
        )
        # failsafes (3 params) + remote_id (1 param) = 4 PARAM_VALUE responses
        param_msgs = [
            MagicMock(param_value=1.0),  # FS_THR_ENABLE
            MagicMock(param_value=2.0),  # FS_GCS_ENABLE
            MagicMock(param_value=1.0),  # FENCE_ENABLE
            MagicMock(param_value=1.0),  # DID_ENABLE
        ]
        vibration_msg = MagicMock(vibration_x=2.0, vibration_y=3.0, vibration_z=1.0)

        def recv_match_side_effect(type=None, blocking=True, timeout=10):
            if type == "GPS_RAW_INT":
                return gps_msg
            elif type == "SYS_STATUS":
                return battery_msg  # used by both battery and compass
            elif type == "PARAM_VALUE":
                return param_msgs.pop(0) if param_msgs else None
            elif type == "VIBRATION":
                return vibration_msg
            return None

        mock_conn.recv_match.side_effect = recv_match_side_effect

        results = run_preflight_checks("/dev/ttyUSB0", "alpha")

        assert len(results) == 7
        assert all(isinstance(r, CheckResult) for r in results)
        mock_mavutil.mavlink_connection.assert_called_once_with("/dev/ttyUSB0", baud=57600)
        mock_conn.close.assert_called_once()

    @patch("drone_swarm.safety.mavutil")
    def test_connection_closed_on_error(self, mock_mavutil):
        mock_conn = MagicMock()
        mock_mavutil.mavlink_connection.return_value = mock_conn
        mock_conn.wait_heartbeat.side_effect = RuntimeError("boom")

        # check_comms catches the exception, but check_gps might blow up
        mock_conn.recv_match.side_effect = RuntimeError("boom")

        # Even if checks raise, connection should still be closed
        with pytest.raises(RuntimeError):
            run_preflight_checks("/dev/ttyUSB0", "alpha")
        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Behavior when pymavlink is not installed (mavutil is None)
# ---------------------------------------------------------------------------

class TestMavutilNotInstalled:
    @patch("drone_swarm.safety.mavutil", None)
    def test_run_preflight_checks_fails_gracefully(self):
        """When pymavlink is not installed, mavutil is None and calling
        run_preflight_checks raises ImportError with a clear message."""
        with pytest.raises(ImportError, match="pymavlink is required"):
            run_preflight_checks("/dev/ttyUSB0", "alpha")


# ---------------------------------------------------------------------------
# emergency_land()
# ---------------------------------------------------------------------------

class TestEmergencyLand:
    @pytest.mark.asyncio
    async def test_sets_land_mode_on_airborne_drones(self):
        mock_conn = MagicMock()
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.AIRBORNE,
        )
        drone.connection = mock_conn

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        await emergency_land(orch)

        mock_conn.set_mode.assert_called_once_with("LAND")
        assert orch._running is False
        assert drone.status == DroneStatus.LANDING

    @pytest.mark.asyncio
    async def test_skips_disconnected_drones(self):
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.DISCONNECTED,
        )
        drone.connection = MagicMock()

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        await emergency_land(orch)

        # DISCONNECTED is not in the allowed statuses, so set_mode should not be called
        drone.connection.set_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_drone_with_no_connection(self):
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.AIRBORNE,
        )
        drone.connection = None

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        await emergency_land(orch)
        # Should not raise -- just skip

    @pytest.mark.asyncio
    async def test_cancels_mission_tasks(self):
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.LANDED,
        )
        drone.connection = None

        task = MagicMock()
        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {"alpha": task}

        await emergency_land(orch)

        task.cancel.assert_called_once()
        assert len(orch._mission_tasks) == 0


# ---------------------------------------------------------------------------
# emergency_kill()
# ---------------------------------------------------------------------------

class TestEmergencyKill:
    @pytest.mark.asyncio
    async def test_requires_confirm_true(self):
        orch = MagicMock()
        orch._running = True
        orch.drones = {}
        orch._mission_tasks = {}

        await emergency_kill(orch, confirm=False)

        # Should NOT set _running to False when confirm is not True
        assert orch._running is True

    @pytest.mark.asyncio
    async def test_sends_force_disarm_command(self):
        mock_conn = MagicMock()
        mock_conn.target_system = 1
        mock_conn.target_component = 1

        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.AIRBORNE,
        )
        drone.connection = mock_conn

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        with patch("drone_swarm.safety.mavutil"):
            # Patch the import inside emergency_kill
            mock_mavlink = MagicMock()
            mock_mavlink.MAV_CMD_COMPONENT_ARM_DISARM = 400

            mods = {"pymavlink": MagicMock(), "pymavlink.mavutil": MagicMock()}
            with patch.dict("sys.modules", mods):
                # The function does its own `from pymavlink import mavutil`
                with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
                    MagicMock(mavutil=MagicMock(mavlink=mock_mavlink))
                    if name == "pymavlink" else __import__(name, *a, **kw)
                )):
                    await emergency_kill(orch, confirm=True)

        assert orch._running is False
        mock_conn.mav.command_long_send.assert_called_once()
        # Verify the magic disarm value 21196 is in the call args
        call_args = mock_conn.mav.command_long_send.call_args[0]
        assert 21196 in call_args
        assert drone.status == DroneStatus.LANDED

    @pytest.mark.asyncio
    async def test_skips_landed_drones(self):
        mock_conn = MagicMock()
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.LANDED,
        )
        drone.connection = mock_conn

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        await emergency_kill(orch, confirm=True)

        # LANDED is excluded, so command_long_send should not be called
        mock_conn.mav.command_long_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_disconnected_drones(self):
        mock_conn = MagicMock()
        drone = Drone(
            drone_id="alpha",
            connection_string="udp:127.0.0.1:14550",
            status=DroneStatus.DISCONNECTED,
        )
        drone.connection = mock_conn

        orch = MagicMock()
        orch._running = True
        orch.drones = {"alpha": drone}
        orch._drone_locks = {"alpha": asyncio.Lock()}
        orch._mission_tasks = {}

        await emergency_kill(orch, confirm=True)

        mock_conn.mav.command_long_send.assert_not_called()
