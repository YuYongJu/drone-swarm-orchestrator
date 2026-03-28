"""
Safety module -- preflight checks and emergency actions.

Combines functionality from src/preflight.py (individual drone checks) and
the emergency methods from src/swarm.py into a single safety-focused module.
"""

import logging
import time
from dataclasses import dataclass

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None  # type: ignore[assignment]

from .drone import DroneStatus

logger = logging.getLogger("drone_swarm.safety")

# ---------------------------------------------------------------------------
# Preflight check result
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single preflight check on one drone."""
    drone_id: str
    check: str
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_comms(conn, drone_id: str, timeout: float = 10.0) -> CheckResult:
    """Verify MAVLink heartbeat."""
    start = time.time()
    try:
        conn.wait_heartbeat(timeout=timeout)
        latency_ms = (time.time() - start) * 1000
        return CheckResult(drone_id, "COMMS", True, f"Heartbeat OK ({latency_ms:.0f}ms)")
    except Exception:
        return CheckResult(drone_id, "COMMS", False, "No heartbeat -- check radio connection")


def check_gps(conn, drone_id: str) -> CheckResult:
    """Verify GPS fix with sufficient satellites."""
    msg = conn.recv_match(type="GPS_RAW_INT", blocking=True, timeout=10)
    if msg is None:
        return CheckResult(drone_id, "GPS", False, "No GPS data received")
    fix = msg.fix_type
    sats = msg.satellites_visible
    if fix < 3:
        return CheckResult(drone_id, "GPS", False,
                           f"No 3D fix (fix_type={fix}, sats={sats}) -- wait for clear sky")
    if sats < 6:
        return CheckResult(drone_id, "GPS", False,
                           f"Only {sats} sats (need >=6) -- move to open area")
    return CheckResult(drone_id, "GPS", True, f"3D fix, {sats} satellites")


def check_battery(conn, drone_id: str, min_pct: float = 80.0) -> CheckResult:
    """Verify battery is sufficiently charged."""
    msg = conn.recv_match(type="SYS_STATUS", blocking=True, timeout=10)
    if msg is None:
        return CheckResult(drone_id, "BATTERY", False, "No battery data")
    pct = msg.battery_remaining
    voltage = msg.voltage_battery / 1000.0
    if pct < 0:
        return CheckResult(drone_id, "BATTERY", False, "Battery monitor not configured")
    if pct < min_pct:
        return CheckResult(drone_id, "BATTERY", False,
                           f"{pct}% ({voltage:.1f}V) -- need >={min_pct}%")
    return CheckResult(drone_id, "BATTERY", True, f"{pct}% ({voltage:.1f}V)")


def check_compass(conn, drone_id: str) -> CheckResult:
    """Check compass health from SYS_STATUS sensor flags."""
    msg = conn.recv_match(type="SYS_STATUS", blocking=True, timeout=10)
    if msg is None:
        return CheckResult(drone_id, "COMPASS", False, "No status data")
    compass_present = msg.onboard_control_sensors_present & 2
    compass_healthy = msg.onboard_control_sensors_health & 2
    if not compass_present:
        return CheckResult(drone_id, "COMPASS", False, "No compass detected -- check BN-880 wiring")
    if not compass_healthy:
        return CheckResult(drone_id, "COMPASS", False, "Compass unhealthy -- needs calibration")
    return CheckResult(drone_id, "COMPASS", True, "Calibrated and healthy")


def check_remote_id(conn, drone_id: str) -> CheckResult:
    """Verify Remote ID (DID_ENABLE) is configured for FAA compliance."""
    conn.mav.param_request_read_send(
        conn.target_system, conn.target_component, b"DID_ENABLE", -1,
    )
    msg = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)
    if msg is None:
        return CheckResult(drone_id, "REMOTE_ID", False,
                           "No response for DID_ENABLE -- firmware may not support Remote ID")
    if int(msg.param_value) != 1:
        return CheckResult(drone_id, "REMOTE_ID", False,
                           f"DID_ENABLE={int(msg.param_value)}, need 1 -- Remote ID not enabled")
    return CheckResult(drone_id, "REMOTE_ID", True, "Remote ID enabled (DID_ENABLE=1)")


def check_vibration(conn, drone_id: str, threshold: float = 30.0) -> CheckResult:
    """Check vibration levels from the VIBRATION MAVLink message."""
    msg = conn.recv_match(type="VIBRATION", blocking=True, timeout=10)
    if msg is None:
        return CheckResult(drone_id, "VIBRATION", False,
                           "No VIBRATION data received -- check firmware version")
    vibe_x = msg.vibration_x
    vibe_y = msg.vibration_y
    vibe_z = msg.vibration_z
    max_vibe = max(vibe_x, vibe_y, vibe_z)
    detail = f"x={vibe_x:.1f} y={vibe_y:.1f} z={vibe_z:.1f} m/s/s"
    if max_vibe >= threshold:
        return CheckResult(drone_id, "VIBRATION", False,
                           f"EXCESSIVE vibration ({detail}) -- check props, motors, mounting")
    return CheckResult(drone_id, "VIBRATION", True, f"OK ({detail})")


def check_failsafes(conn, drone_id: str) -> CheckResult:
    """Verify critical failsafe parameters are set."""
    required = {
        "FS_THR_ENABLE": (1, "RC failsafe must be RTL"),
        "FS_GCS_ENABLE": (2, "GCS failsafe must be RTL"),
        "FENCE_ENABLE": (1, "Geofence must be on"),
    }
    issues = []
    for param, (expected, reason) in required.items():
        conn.mav.param_request_read_send(
            conn.target_system, conn.target_component, param.encode("utf-8"), -1,
        )
        msg = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)
        if msg is None:
            issues.append(f"{param}: no response")
        elif int(msg.param_value) != expected:
            issues.append(f"{param}={int(msg.param_value)}, need {expected} ({reason})")
    if issues:
        return CheckResult(drone_id, "FAILSAFE", False, "; ".join(issues))
    return CheckResult(drone_id, "FAILSAFE", True, "All failsafes configured correctly")


# ---------------------------------------------------------------------------
# Preflight runner
# ---------------------------------------------------------------------------

def run_preflight_checks(
    connection_string: str,
    drone_id: str,
    min_battery_pct: float = 80.0,
) -> list[CheckResult]:
    """
    Run the full preflight check suite against a single drone.

    Args:
        connection_string: MAVLink connection string (e.g. ``/dev/ttyUSB0``).
        drone_id: Human-readable drone identifier.
        min_battery_pct: Minimum battery percentage to pass.

    Returns:
        List of :class:`CheckResult` instances (one per check).
    """
    if mavutil is None:
        raise ImportError(
            "pymavlink is required for preflight checks. "
            "Install with: pip install pymavlink"
        )
    conn = mavutil.mavlink_connection(connection_string, baud=57600)
    try:
        results = [
            check_comms(conn, drone_id),
            check_gps(conn, drone_id),
            check_battery(conn, drone_id, min_battery_pct),
            check_compass(conn, drone_id),
            check_failsafes(conn, drone_id),
            check_remote_id(conn, drone_id),
            check_vibration(conn, drone_id),
        ]
    finally:
        conn.close()
    return results


def preflight_ok(results: list[CheckResult]) -> bool:
    """Return ``True`` if every check in *results* passed."""
    return all(r.passed for r in results)


# ---------------------------------------------------------------------------
# Emergency actions (async, used by SwarmOrchestrator)
# ---------------------------------------------------------------------------

async def emergency_land(orchestrator) -> None:
    """
    EMERGENCY: Command all drones to land immediately (controlled descent).

    This is the default emergency action -- drones descend under flight-
    controller control, which is safer than a motor kill.
    """
    logger.error("*** EMERGENCY LAND -- all drones switching to LAND mode ***")
    orchestrator._running = False
    for drone_id, drone in orchestrator.drones.items():
        if drone.connection and drone.status in (
            DroneStatus.AIRBORNE, DroneStatus.RETURNING, DroneStatus.LANDING, DroneStatus.ARMED
        ):
            try:
                drone.connection.set_mode("LAND")
                async with orchestrator._drone_locks[drone_id]:
                    drone.status = DroneStatus.LANDING
                logger.info("'%s' -> LAND mode", drone_id)
            except Exception as e:
                logger.error("Failed to land '%s': %s", drone_id, e)
    for task in orchestrator._mission_tasks.values():
        task.cancel()
    orchestrator._mission_tasks.clear()


async def emergency_kill(orchestrator, confirm: bool = False) -> None:
    """
    EMERGENCY: Force disarm ALL motors immediately.

    Drones will fall from the sky. This is a LAST RESORT.
    Requires ``confirm=True`` to prevent accidental invocation.
    """
    try:
        from pymavlink import mavutil as _mavutil
    except ImportError:
        _mavutil = None  # type: ignore[assignment]

    if not confirm:
        logger.warning("emergency_kill() requires confirm=True. "
                       "This will force-disarm all motors -- drones will FALL.")
        return
    logger.error("*** EMERGENCY KILL -- force disarming ALL motors ***")
    orchestrator._running = False
    for drone_id, drone in orchestrator.drones.items():
        if drone.connection and drone.status not in (
            DroneStatus.DISCONNECTED, DroneStatus.LANDED
        ):
            try:
                conn = drone.connection
                conn.mav.command_long_send(
                    conn.target_system, conn.target_component,
                    _mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0, 0, 21196, 0, 0, 0, 0, 0,
                )
                async with orchestrator._drone_locks[drone_id]:
                    drone.status = DroneStatus.LANDED
                logger.error("'%s' MOTORS KILLED", drone_id)
            except Exception as e:
                logger.error("Failed to kill '%s': %s", drone_id, e)
    for task in orchestrator._mission_tasks.values():
        task.cancel()
    orchestrator._mission_tasks.clear()
