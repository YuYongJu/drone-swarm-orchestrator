"""
SITL integration tests for the drone-swarm SDK.

These tests verify the SDK works end-to-end with a real ArduPilot SITL
instance. They are **not** run in CI -- they require a running SITL process
and are skipped by default.

How to run
----------
1. Start SITL first::

       dso simulate --drones 1

2. Then run the tests::

       pytest tests/test_sitl_integration.py --sitl

All tests connect to ``tcp:127.0.0.1:5760`` (the first SITL instance's
default port). Each test has a 60-second timeout and performs clean shutdown.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from drone_swarm.drone import DroneStatus
from drone_swarm.health import compute_health_score
from drone_swarm.swarm import Swarm

logger = logging.getLogger(__name__)

# Default connection for the first SITL drone started by ``dso simulate``.
SITL_CONNECTION = "tcp:127.0.0.1:5760"
SITL_DRONE_ID = "sitl-0"

# All tests in this module require a running SITL instance.
pytestmark = pytest.mark.sitl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_swarm() -> Swarm:
    """Create a Swarm with one drone registered against the SITL instance."""
    swarm = Swarm()
    swarm.add(SITL_DRONE_ID, SITL_CONNECTION)
    return swarm


async def _safe_shutdown(swarm: Swarm) -> None:
    """Best-effort shutdown that never raises."""
    try:
        await swarm.shutdown()
    except Exception:
        logger.exception("Error during shutdown (suppressed)")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSITLConnect:
    """Verify basic connectivity to SITL."""

    @pytest.mark.asyncio
    async def test_single_drone_connect(self):
        """Connect to one SITL instance; verify CONNECTED status and GPS position."""
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)

            drone = swarm.drones[SITL_DRONE_ID]
            assert drone.status == DroneStatus.CONNECTED, (
                f"Expected CONNECTED, got {drone.status.value}"
            )

            # Wait briefly for telemetry to populate a non-zero position
            for _ in range(20):
                if drone.lat != 0.0 or drone.lon != 0.0:
                    break
                await asyncio.sleep(0.5)

            assert drone.lat != 0.0 or drone.lon != 0.0, (
                "GPS position is still (0, 0) after waiting for telemetry"
            )
        finally:
            await _safe_shutdown(swarm)


class TestSITLTakeoffLand:
    """Verify takeoff and landing through SITL."""

    @pytest.mark.asyncio
    async def test_single_drone_takeoff_land(self):
        """Connect, takeoff to 10m, verify altitude, land, verify altitude drops."""
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)

            # Takeoff to 10 metres
            await asyncio.wait_for(
                swarm.takeoff(SITL_DRONE_ID, altitude=10.0),
                timeout=30.0,
            )

            # Wait for altitude to climb above 5 m
            drone = swarm.drones[SITL_DRONE_ID]
            deadline = asyncio.get_event_loop().time() + 30.0
            while asyncio.get_event_loop().time() < deadline:
                if drone.alt > 5.0:
                    break
                await asyncio.sleep(0.5)

            assert drone.alt > 5.0, (
                f"Expected altitude > 5m after takeoff, got {drone.alt:.1f}m"
            )

            # Land
            await swarm.land(SITL_DRONE_ID)

            # Wait for altitude to drop below 2 m
            deadline = asyncio.get_event_loop().time() + 30.0
            while asyncio.get_event_loop().time() < deadline:
                if drone.alt < 2.0:
                    break
                await asyncio.sleep(0.5)

            assert drone.alt < 2.0, (
                f"Expected altitude < 2m after landing, got {drone.alt:.1f}m"
            )
        finally:
            await _safe_shutdown(swarm)


class TestSITLTelemetry:
    """Verify telemetry data flows from SITL into the drone model."""

    @pytest.mark.asyncio
    async def test_telemetry_flows(self):
        """Connect, wait 5s, verify lat/lon are non-zero and battery > 0."""
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)
            await asyncio.sleep(5.0)

            drone = swarm.drones[SITL_DRONE_ID]

            assert drone.lat != 0.0, "Latitude still 0 after 5s of telemetry"
            assert drone.lon != 0.0, "Longitude still 0 after 5s of telemetry"
            # SITL may not report battery_pct without BATT_MONITOR param,
            # but voltage is always available via BATTERY_STATUS.
            assert drone.battery_pct > 0 or drone.voltage > 0, (
                f"No battery data: pct={drone.battery_pct}, voltage={drone.voltage}"
            )
        finally:
            await _safe_shutdown(swarm)


class TestSITLHealthScore:
    """Verify that the health scoring system works with real telemetry."""

    @pytest.mark.asyncio
    async def test_health_score_computed(self):
        """Connect, wait for telemetry, verify health_score is 0-100."""
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)
            await asyncio.sleep(5.0)

            drone = swarm.drones[SITL_DRONE_ID]
            score = compute_health_score(drone)

            assert 0 <= score <= 100, (
                f"Health score should be 0-100, got {score}"
            )
            # With a fresh SITL and full battery, score should be reasonable
            assert score > 0, "Health score is exactly 0 -- telemetry may not be flowing"
        finally:
            await _safe_shutdown(swarm)


class TestSITLFormation:
    """Verify formation commands don't crash against a real connection."""

    @pytest.mark.asyncio
    async def test_formation_command(self):
        """Connect 1 drone, call formation('v'), verify no crash.

        With a single drone the formation is trivially the drone's own
        position, but the point of this test is to prove the full code path
        (mission planning, MAVLink goto) executes without errors.
        """
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)

            # Takeoff first -- formation requires AIRBORNE status
            await asyncio.wait_for(
                swarm.takeoff(SITL_DRONE_ID, altitude=10.0),
                timeout=30.0,
            )

            # Wait for the drone to actually be airborne
            drone = swarm.drones[SITL_DRONE_ID]
            deadline = asyncio.get_event_loop().time() + 20.0
            while asyncio.get_event_loop().time() < deadline:
                if drone.alt > 5.0:
                    break
                await asyncio.sleep(0.5)

            # Issue a V-formation command -- should not raise
            await asyncio.wait_for(
                swarm.formation("v", spacing=15.0),
                timeout=20.0,
            )
        finally:
            await _safe_shutdown(swarm)


class TestSITLCollisionAvoidance:
    """Verify collision avoidance can be enabled during flight without crashing."""

    @pytest.mark.asyncio
    async def test_collision_avoidance_enabled(self):
        """Enable collision avoidance, takeoff, fly briefly, verify no crash."""
        swarm = _make_swarm()
        try:
            await asyncio.wait_for(swarm.connect(), timeout=30.0)

            # Enable collision avoidance before takeoff
            swarm.enable_collision_avoidance(min_distance_m=5.0)

            # Takeoff
            await asyncio.wait_for(
                swarm.takeoff(SITL_DRONE_ID, altitude=10.0),
                timeout=30.0,
            )

            # Wait for the drone to be airborne
            drone = swarm.drones[SITL_DRONE_ID]
            deadline = asyncio.get_event_loop().time() + 20.0
            while asyncio.get_event_loop().time() < deadline:
                if drone.alt > 5.0:
                    break
                await asyncio.sleep(0.5)

            # Let the telemetry loop run with CA active for a few seconds
            await asyncio.sleep(5.0)

            # If we got here without an exception, collision avoidance
            # integrated cleanly with the flight loop.
            assert drone.status in (
                DroneStatus.AIRBORNE,
                DroneStatus.RETURNING,
            ), f"Unexpected status: {drone.status.value}"
        finally:
            await _safe_shutdown(swarm)
