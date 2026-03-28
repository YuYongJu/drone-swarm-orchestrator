"""
Swarm Orchestrator -- the core engine that manages a fleet of drones.

This is the SDK's main orchestration module. It coordinates connections,
telemetry, missions, state transitions, and emergency procedures across
all registered drones.

Re-exports the high-level ``Swarm`` alias for the simple public API
described in the package ``__init__.py``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None  # type: ignore[assignment]

import contextlib

from .anomaly import AnomalyDetector
from .collision import CollisionAvoidance
from .config import SwarmConfig
from .drone import (
    VALID_TRANSITIONS,
    Drone,
    DroneCapabilities,
    DroneRole,
    DroneStatus,
    Waypoint,
)
from .formation_control import FormationController, FormationGains
from .geofence import Geofence
from .missions import area_sweep, line_formation, orbit_point, v_formation
from .path_planner import PathPlanner
from .safety import emergency_kill as _emergency_kill
from .safety import emergency_land as _emergency_land
from .telemetry import telemetry_loop

logger = logging.getLogger("drone_swarm.swarm")

if TYPE_CHECKING:
    from .simulation import SimulationHarness


class SwarmOrchestrator:
    """
    Central orchestrator that manages a fleet of drones.

    Each drone communicates over its own MAVLink connection.
    All public methods are async coroutines. State access is protected by
    per-drone asyncio locks to prevent race conditions.
    """

    HEARTBEAT_TIMEOUT = 15.0
    BATTERY_RTL_THRESHOLD = 20.0
    BATTERY_CHECK_GRACE_PERIOD = 30.0
    RTL_BASE_ALT_CM = 1500
    RTL_ALT_STAGGER_CM = 500

    def __init__(self, config: SwarmConfig | None = None):
        cfg = config or SwarmConfig()
        self.HEARTBEAT_TIMEOUT = cfg.heartbeat_timeout_s
        self.BATTERY_RTL_THRESHOLD = cfg.battery_rtl_threshold_pct
        self.BATTERY_CHECK_GRACE_PERIOD = cfg.battery_check_grace_period_s
        self.RTL_BASE_ALT_CM = cfg.rtl_base_alt_cm
        self.RTL_ALT_STAGGER_CM = cfg.rtl_alt_stagger_cm
        self._config = cfg

        self.drones: dict[str, Drone] = {}
        self._drone_locks: dict[str, asyncio.Lock] = {}
        self._telemetry_task: asyncio.Task | None = None
        self._mission_tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._collision_avoidance: CollisionAvoidance | None = None
        self._geofence: Geofence | None = None
        self._geofence_action: str = "warn"
        # Formation hold state
        self._formation_controller: FormationController | None = None
        self._formation_leader_id: str | None = None
        # Path planning state
        self._path_planner: PathPlanner | None = None
        self._path_planning_obstacles: list[tuple[float, float, float]] | None = None
        # Anomaly detection state
        self._anomaly_detector: AnomalyDetector | None = None

    # -- Anomaly Detection -----------------------------------------------------

    def enable_anomaly_detection(self, window_size: int = 30) -> None:
        """Enable telemetry anomaly detection (compare-to-neighbors pattern).

        Once enabled, the telemetry loop will feed drone metrics into the
        :class:`AnomalyDetector` every cycle and log any anomalies found.

        Args:
            window_size: Number of readings to retain per metric for
                rolling statistics.
        """
        self._anomaly_detector = AnomalyDetector(window_size=window_size)
        logger.info("Anomaly detection ENABLED (window_size=%d)", window_size)

    def disable_anomaly_detection(self) -> None:
        """Disable anomaly detection."""
        self._anomaly_detector = None
        logger.info("Anomaly detection DISABLED")

    # -- Geofence --------------------------------------------------------------

    def set_geofence(
        self,
        polygon: list[tuple[float, float]],
        alt_max_m: float = 120.0,
        action: str = "rtl",
    ) -> None:
        """
        Configure a geofence for the swarm.

        Args:
            polygon: List of ``(lat, lon)`` vertices defining the boundary.
            alt_max_m: Maximum altitude in metres AGL.
            action: Action on breach -- ``"rtl"``, ``"land"``, or ``"warn"``.
        """
        if action not in ("rtl", "land", "warn"):
            raise ValueError(f"Invalid geofence action: {action!r}. "
                             f"Must be 'rtl', 'land', or 'warn'.")
        self._geofence = Geofence(polygon=polygon, alt_max_m=alt_max_m)
        self._geofence_action = action
        logger.info("Geofence SET (%d vertices, alt_max=%.0fm, action=%s)",
                    len(polygon), alt_max_m, action)

    def clear_geofence(self) -> None:
        """Remove the current geofence."""
        self._geofence = None
        self._geofence_action = "warn"
        logger.info("Geofence CLEARED")

    # -- Collision Avoidance ---------------------------------------------------

    def enable_collision_avoidance(
        self, min_distance_m: float = 5.0, method: str = "orca",
    ) -> None:
        """Enable automatic collision avoidance with the given minimum separation."""
        self._collision_avoidance = CollisionAvoidance(
            min_distance_m=min_distance_m, method=method,
        )
        logger.info(
            "Collision avoidance ENABLED (min_distance=%.1fm, method=%s)",
            min_distance_m, method,
        )

    def disable_collision_avoidance(self) -> None:
        """Disable automatic collision avoidance."""
        self._collision_avoidance = None
        logger.info("Collision avoidance DISABLED")

    # -- Formation Hold --------------------------------------------------------

    def enable_formation_hold(
        self,
        leader_id: str,
        offsets: dict[str, tuple[float, float, float]],
        gains: FormationGains | None = None,
    ) -> None:
        """Enable continuous closed-loop formation correction.

        Once enabled, the telemetry loop will call
        :meth:`FormationController.compute_corrections` every cycle and send
        adjusted ``goto`` commands to keep followers at their target offsets
        from the leader.

        Works alongside the existing :meth:`formation` method:
        ``formation()`` sets the initial positions (open-loop),
        ``enable_formation_hold()`` maintains them (closed-loop).

        Args:
            leader_id: ID of the leader drone (must be registered).
            offsets: Per-follower NED offsets in meters from the leader.
                Keys are follower drone IDs, values are
                ``(north_m, east_m, down_m)`` tuples.
            gains: Optional :class:`FormationGains`. Defaults to
                ``FormationGains()`` (P-only with kp=0.8).

        Raises:
            KeyError: If *leader_id* is not a registered drone.
        """
        if leader_id not in self.drones:
            raise KeyError(f"Leader drone '{leader_id}' is not registered")
        self._formation_controller = FormationController(gains=gains)
        self._formation_controller.set_formation(offsets)
        self._formation_leader_id = leader_id
        logger.info(
            "Formation hold ENABLED (leader='%s', %d followers)",
            leader_id, len(offsets),
        )

    def disable_formation_hold(self) -> None:
        """Stop closed-loop formation correction."""
        self._formation_controller = None
        self._formation_leader_id = None
        logger.info("Formation hold DISABLED")

    # -- Path Planning ---------------------------------------------------------

    def enable_path_planning(
        self,
        obstacles: list[tuple[float, float, float]] | None = None,
        resolution_m: float = 5.0,
    ) -> None:
        """Enable intelligent path planning for ``goto()`` commands.

        When enabled, ``goto()`` automatically routes through the A*
        path planner instead of flying in a direct line.

        Args:
            obstacles: List of ``(lat, lon, radius_m)`` no-fly zones.
            resolution_m: Grid cell size in metres for the planner.
        """
        self._path_planner = PathPlanner(
            resolution_m=resolution_m,
            geofence=self._geofence,
        )
        self._path_planning_obstacles = obstacles
        logger.info(
            "Path planning ENABLED (resolution=%.1fm, %d obstacles)",
            resolution_m, len(obstacles) if obstacles else 0,
        )

    def disable_path_planning(self) -> None:
        """Disable intelligent path planning; ``goto()`` reverts to direct flight."""
        self._path_planner = None
        self._path_planning_obstacles = None
        logger.info("Path planning DISABLED")

    # -- State Machine ---------------------------------------------------------

    async def _transition(self, drone_id: str, new_status: DroneStatus) -> bool:
        async with self._drone_locks[drone_id]:
            drone = self.drones[drone_id]
            allowed = VALID_TRANSITIONS.get(drone.status, set())
            if new_status not in allowed:
                logger.warning("INVALID transition for '%s': %s -> %s",
                               drone_id, drone.status.value, new_status.value)
                return False
            drone.status = new_status
            return True

    # -- Registration & Connection ---------------------------------------------

    def register_drone(
        self,
        drone_id: str,
        connection_string: str,
        role: DroneRole = DroneRole.RECON,
        capabilities: DroneCapabilities | None = None,
    ):
        self.drones[drone_id] = Drone(
            drone_id=drone_id,
            connection_string=connection_string,
            role=role,
            capabilities=capabilities or DroneCapabilities(),
        )
        self._drone_locks[drone_id] = asyncio.Lock()
        cls = self.drones[drone_id].capabilities.hw_class
        logger.info("Registered drone '%s' (Class %s, %s) on %s",
                    drone_id, cls, role.value, connection_string)

    # Convenience alias used by the simplified API
    add = register_drone

    def register_from_fleet(self, fleet_dir: str = "fleet"):
        """Auto-register all drones from fleet registry JSON files."""
        import json
        from pathlib import Path
        fleet_path = Path(fleet_dir)
        if not fleet_path.is_absolute():
            fleet_path = Path(__file__).parent.parent / fleet_dir
        for f in sorted(fleet_path.glob("*.json")):
            with open(f) as fh:
                reg = json.load(fh)
            caps = DroneCapabilities(
                hw_class=reg.get("hw_class", "A"),
                has_camera=reg.get("capabilities", {}).get("has_camera", False),
                has_compute=reg.get("capabilities", {}).get("has_compute", False),
                has_payload=reg.get("capabilities", {}).get("has_payload", False),
            )
            role = DroneRole(reg.get("default_role", "recon"))
            self.register_drone(reg["drone_id"], reg["port"], role, caps)

    async def connect_all(self):
        """Connect to all registered drones and start the telemetry loop."""
        for drone in self.drones.values():
            await self._connect_drone(drone)
        self._running = True
        self._telemetry_task = asyncio.create_task(telemetry_loop(self))

    # Convenience alias
    connect = connect_all

    async def _connect_drone(self, drone: Drone):
        loop = asyncio.get_running_loop()
        try:
            conn = await loop.run_in_executor(
                None,
                lambda: mavutil.mavlink_connection(
                    drone.connection_string,
                    baud=self._config.mavlink_baud,
                ),
            )
            await loop.run_in_executor(
                None,
                lambda: conn.wait_heartbeat(timeout=self._config.heartbeat_wait_timeout_s),
            )
            drone.connection = conn
            # Request all telemetry streams at 4Hz
            conn.mav.request_data_stream_send(
                conn.target_system, conn.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                4,  # 4 Hz
                1,  # start sending
            )
            await self._transition(drone.drone_id, DroneStatus.CONNECTED)
            drone.last_heartbeat = time.time()
            logger.info("Connected to '%s' (sysid=%s)",
                        drone.drone_id, conn.target_system)
        except Exception as e:
            logger.error("Failed to connect to '%s': %s", drone.drone_id, e)

    # -- Flight Commands -------------------------------------------------------

    async def arm(self, drone_id: str, retries: int = 3) -> bool:
        """Arm a drone. Returns True on success, False on failure.

        NOTE: The telemetry loop must be paused before calling this,
        otherwise ``motors_armed_wait()`` will race with the telemetry
        reader for MAVLink messages.
        """
        drone = self.drones[drone_id]
        conn = drone.connection
        loop = asyncio.get_running_loop()
        for attempt in range(1, retries + 1):
            conn.mav.command_long_send(
                conn.target_system, conn.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 1, 0, 0, 0, 0, 0, 0,
            )
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, conn.motors_armed_wait),
                    timeout=10.0,
                )
                await self._transition(drone_id, DroneStatus.ARMED)
                logger.info("'%s' armed", drone_id)
                return True
            except TimeoutError:
                logger.warning("'%s' arm attempt %d/%d timed out, retrying...",
                               drone_id, attempt, retries)
                await asyncio.sleep(2)
        logger.error("'%s' FAILED to arm after %d attempts", drone_id, retries)
        return False

    async def _wait_for_gps(self, drone: Drone, timeout: float = 30.0):
        """Wait until the telemetry loop reports a non-zero position (GPS lock)."""
        start = time.time()
        while time.time() - start < timeout:
            # Check if telemetry has updated the position from 0,0
            if drone.lat != 0.0 or drone.lon != 0.0:
                logger.info("'%s' GPS position ready (%.6f, %.6f)",
                            drone.drone_id, drone.lat, drone.lon)
                return True
            await asyncio.sleep(1.0)
        logger.warning("'%s' GPS wait timed out after %ss", drone.drone_id, timeout)
        return False

    async def takeoff(self, drone_id: str | None = None, altitude: float | None = None):
        """
        Take off a single drone or all drones.

        If *drone_id* is ``None``, all registered drones take off.
        """
        if altitude is None:
            altitude = self._config.default_altitude_m
        if drone_id is None:
            return await self.takeoff_all(altitude)
        drone = self.drones[drone_id]
        conn = drone.connection
        await self._wait_for_gps(drone)
        # Pause telemetry loop so set_mode() and motors_armed_wait()
        # can read from the connection without racing
        self._running = False
        if self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._telemetry_task
        await asyncio.sleep(0.5)

        conn.set_mode("GUIDED")
        await asyncio.sleep(1.0)
        armed = await self.arm(drone_id)
        if not armed:
            logger.error("'%s' takeoff aborted — arming failed", drone_id)
            return
        conn.mav.command_long_send(
            conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, 0, 0, altitude,
        )
        await self._transition(drone_id, DroneStatus.AIRBORNE)
        drone.takeoff_time = time.time()
        logger.info("'%s' taking off to %sm", drone_id, altitude)

        # Restart telemetry loop (was paused for arm sequence)
        # Reset heartbeat timestamps so the loop doesn't immediately mark drones as LOST
        if not self._running:
            now = time.time()
            for d in self.drones.values():
                d.last_heartbeat = now
            self._running = True
            self._telemetry_task = asyncio.create_task(telemetry_loop(self))

    async def goto(self, drone_id: str, waypoint: Waypoint):
        drone = self.drones[drone_id]

        # If path planning is enabled, route through the planner
        if self._path_planner is not None:
            start = Waypoint(lat=drone.lat, lon=drone.lon, alt=drone.alt)
            path = self._path_planner.plan_path(
                start, waypoint, self._path_planning_obstacles,
            )
            # Send each intermediate waypoint (skip the start position)
            for wp in path[1:]:
                await self._send_goto(drone_id, wp)
            return

        await self._send_goto(drone_id, waypoint)

    async def _send_goto(self, drone_id: str, waypoint: Waypoint):
        """Low-level MAVLink goto command (no path planning)."""
        drone = self.drones[drone_id]
        conn = drone.connection
        conn.mav.set_position_target_global_int_send(
            0, conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,
            int(waypoint.lat * 1e7),
            int(waypoint.lon * 1e7),
            waypoint.alt,
            0, 0, 0, 0, 0, 0, 0, 0,
        )
        logger.info("'%s' -> (%.6f, %.6f, %sm)", drone_id, waypoint.lat, waypoint.lon, waypoint.alt)

    async def return_to_launch(self, drone_id: str):
        drone = self.drones[drone_id]
        conn = drone.connection
        drone_index = list(self.drones.keys()).index(drone_id)
        rtl_alt_cm = self.RTL_BASE_ALT_CM + (drone_index * self.RTL_ALT_STAGGER_CM)
        conn.mav.param_set_send(
            conn.target_system, conn.target_component,
            b"RTL_ALT", float(rtl_alt_cm),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )
        logger.info("'%s' RTL altitude set to %.0fm", drone_id, rtl_alt_cm / 100)
        rtl_mode = 6  # ArduCopter RTL mode number
        conn.mav.command_long_send(
            conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 1, rtl_mode, 0, 0, 0, 0, 0,
        )
        await self._transition(drone_id, DroneStatus.RETURNING)
        logger.info("'%s' returning to launch", drone_id)

    async def rtl(self, drone_id: str | None = None):
        """Return-to-launch for a single drone or all drones."""
        if drone_id is None:
            return await self.rtl_all()
        await self.return_to_launch(drone_id)

    async def land(self, drone_id: str):
        drone = self.drones[drone_id]
        conn = drone.connection
        land_mode = 9  # ArduCopter LAND mode number
        conn.mav.command_long_send(
            conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 1, land_mode, 0, 0, 0, 0, 0,
        )
        await self._transition(drone_id, DroneStatus.RETURNING)
        logger.info("'%s' landing", drone_id)

    # -- Emergency -------------------------------------------------------------

    async def emergency_land(self):
        await _emergency_land(self)

    async def emergency_kill(self, confirm: bool = False):
        await _emergency_kill(self, confirm)

    # -- Swarm-wide Commands ---------------------------------------------------

    async def takeoff_all(self, altitude: float | None = None):
        if altitude is None:
            altitude = self._config.default_altitude_m
        for drone_id in self.drones:
            await self.takeoff(drone_id, altitude)

    async def rtl_all(self):
        for drone_id in self.drones:
            await self.return_to_launch(drone_id)

    async def land_all(self):
        for drone_id in self.drones:
            await self.land(drone_id)

    # -- Formation helpers (high-level API) ------------------------------------

    async def formation(
        self,
        pattern: str = "v",
        spacing: float = 15.0,
        heading: float = 0.0,
        center: tuple[float, float] | None = None,
        altitude: float | None = None,
    ):
        """
        Move all drones into a formation pattern.

        Args:
            pattern: ``"v"``, ``"line"``, ``"triangle"``, ``"circle"``,
                     ``"grid"``, or ``"orbit"``.
            spacing: Distance in meters between drones.
            heading: Heading in degrees for the formation.
            center: ``(lat, lon)`` center point; defaults to first drone's position.
            altitude: Altitude in meters; defaults to config default.
        """
        alt = altitude or self._config.default_altitude_m
        drone_ids = list(self.drones.keys())
        n = len(drone_ids)

        if center is None:
            first = self.drones[drone_ids[0]]
            center = (first.lat, first.lon)

        # Aliases: triangle=v (3 drones), circle=orbit, grid=line
        pattern_map = {
            "triangle": "v",
            "circle": "orbit",
            "grid": "line",
        }
        resolved = pattern_map.get(pattern, pattern)

        if resolved == "v":
            plans = v_formation(center[0], center[1], alt, n, spacing, heading)
        elif resolved == "line":
            plans = line_formation(center[0], center[1], alt, n, spacing, heading)
        elif resolved == "orbit":
            plans = orbit_point(center[0], center[1], alt, spacing, n)
        else:
            raise ValueError(
                f"Unknown formation pattern: {pattern!r}. "
                f"Supported: 'v', 'line', 'orbit', 'triangle', 'circle', 'grid'"
            )

        for drone_id, waypoints in zip(drone_ids, plans, strict=False):
            await self.assign_mission(drone_id, waypoints)
        await self.execute_missions()

    async def rotate(
        self,
        degrees: float = 360.0,
        duration_s: float = 30.0,
        spacing: float = 15.0,
    ):
        """
        Rotate the current formation around its centroid.

        Sends a series of formation commands at different headings to
        create a smooth rotation animation. Useful for demos and shows.

        Args:
            degrees: Total rotation in degrees (default 360 = full turn).
            duration_s: Time in seconds for the full rotation.
            spacing: Formation spacing in meters.
        """
        drone_ids = list(self.drones.keys())
        if not drone_ids:
            return

        # Compute centroid of current positions
        lats = [self.drones[d].lat for d in drone_ids]
        lons = [self.drones[d].lon for d in drone_ids]
        center = (sum(lats) / len(lats), sum(lons) / len(lons))
        alt = self.drones[drone_ids[0]].alt or self._config.default_altitude_m

        steps = max(int(abs(degrees) / 10), 1)  # 10-degree increments
        step_time = duration_s / steps
        heading_step = degrees / steps

        for i in range(steps):
            heading = i * heading_step
            plans = v_formation(
                center[0], center[1], alt,
                len(drone_ids), spacing, heading,
            )
            for drone_id, waypoints in zip(drone_ids, plans, strict=False):
                if waypoints:
                    await self.goto(drone_id, waypoints[0])
            await asyncio.sleep(step_time)

    async def sweep(
        self,
        bounds: list[tuple[float, float]],
        altitude: float | None = None,
    ):
        """
        Execute an area-sweep mission.

        Args:
            bounds: ``[(sw_lat, sw_lon), (ne_lat, ne_lon)]`` corners.
            altitude: Altitude in meters; defaults to config default.
        """
        alt = altitude or self._config.default_altitude_m
        drone_ids = list(self.drones.keys())
        n = len(drone_ids)
        sw, ne = bounds[0], bounds[1]

        plans = area_sweep(sw[0], sw[1], ne[0], ne[1], alt, n)
        for drone_id, waypoints in zip(drone_ids, plans, strict=False):
            await self.assign_mission(drone_id, waypoints)
        await self.execute_missions()

    # -- Mission Management ----------------------------------------------------

    async def assign_mission(self, drone_id: str, waypoints: list[Waypoint]):
        self.drones[drone_id].mission = waypoints
        logger.info("Assigned %d waypoints to '%s'", len(waypoints), drone_id)

    async def execute_missions(self):
        for drone_id, drone in self.drones.items():
            if drone.mission and drone.status == DroneStatus.AIRBORNE:
                task = asyncio.create_task(self._run_mission(drone_id))
                self._mission_tasks[drone_id] = task
                logger.info("Launched background mission for '%s'", drone_id)

    async def _run_mission(self, drone_id: str):
        drone = self.drones[drone_id]
        try:
            for i, wp in enumerate(drone.mission):
                if drone.status == DroneStatus.LOST:
                    logger.error("'%s' lost during mission -- aborting", drone_id)
                    return
                if not self._running:
                    logger.warning("'%s' mission aborted -- orchestrator stopping", drone_id)
                    return
                logger.info("'%s' mission waypoint %d/%d", drone_id, i + 1, len(drone.mission))
                await self.goto(drone_id, wp)
                await self._wait_until_reached(drone, wp)
            logger.info("'%s' mission complete", drone_id)
        except asyncio.CancelledError:
            logger.warning("'%s' mission cancelled", drone_id)
        finally:
            self._mission_tasks.pop(drone_id, None)

    async def _wait_until_reached(
        self, drone: Drone, wp: Waypoint,
        threshold_m: float | None = None, timeout_s: float = 120.0,
    ):
        if threshold_m is None:
            threshold_m = self._config.waypoint_reach_threshold_m
        start = time.time()
        while drone.status == DroneStatus.AIRBORNE:
            dist = self._haversine(drone.lat, drone.lon, wp.lat, wp.lon)
            if dist < threshold_m:
                return
            if time.time() - start > timeout_s:
                logger.warning("'%s' waypoint timeout after %ss (still %.1fm away)",
                               drone.drone_id, timeout_s, dist)
                return
            await asyncio.sleep(0.5)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_r = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return earth_r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # -- Status ----------------------------------------------------------------

    def status_report(self) -> str:
        lines = ["=== SWARM STATUS ==="]
        for d in self.drones.values():
            lines.append(
                f"  {d.drone_id} [{d.role.value}] -- {d.status.value} "
                f"| pos=({d.lat:.6f}, {d.lon:.6f}, {d.alt:.1f}m) "
                f"| batt={d.battery_pct:.0f}% "
                f"| hdg={d.heading:.0f}deg"
            )
        return "\n".join(lines)

    # -- Dynamic Replanning ----------------------------------------------------

    def active_drones(self) -> list[str]:
        return [d.drone_id for d in self.drones.values()
                if d.status == DroneStatus.AIRBORNE]

    def replan_on_loss(self, lost_drone_id: str):
        """Redistribute a lost drone's waypoints optimally across active drones.

        Uses the Hungarian algorithm via :func:`~drone_swarm.allocation.replan_optimal`
        when ``scipy`` is available, falling back to nearest-neighbor assignment otherwise.
        """
        try:
            from .allocation import replan_optimal
            replan_optimal(self, lost_drone_id)
        except ImportError:
            # Fallback: nearest-neighbor (original behaviour)
            lost = self.drones[lost_drone_id]
            remaining_wps = lost.mission
            if not remaining_wps:
                return
            active = self.active_drones()
            if not active:
                logger.error("No active drones to absorb mission -- all lost")
                return
            nearest_id = min(
                active,
                key=lambda did: self._haversine(
                    self.drones[did].lat, self.drones[did].lon,
                    lost.lat, lost.lon,
                ),
            )
            nearest = self.drones[nearest_id]
            nearest.mission.extend(remaining_wps)
            lost.mission = []
            logger.info("Replanned: %d waypoints from '%s' -> '%s'",
                        len(remaining_wps), lost_drone_id, nearest_id)

    def validate_role(self, drone_id: str, role: DroneRole) -> bool:
        caps = self.drones[drone_id].capabilities
        role_requirements = {
            DroneRole.RECON: caps.has_camera,
            DroneRole.RELAY: True,
            DroneRole.STRIKE: caps.has_payload,
            DroneRole.DECOY: True,
        }
        return role_requirements.get(role, False)

    def auto_assign_roles(self):
        for drone_id, drone in self.drones.items():
            caps = drone.capabilities
            if caps.has_payload:
                drone.role = DroneRole.STRIKE
            elif caps.has_camera:
                drone.role = DroneRole.RECON
            else:
                drone.role = DroneRole.RELAY
            logger.info("Auto-assigned '%s' -> %s (Class %s)",
                        drone_id, drone.role.value, caps.hw_class)

    async def shutdown(self):
        self._running = False
        for task in self._mission_tasks.values():
            task.cancel()
        self._mission_tasks.clear()
        if self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._telemetry_task
        for drone_id, drone in self.drones.items():
            if drone.status in (DroneStatus.AIRBORNE, DroneStatus.ARMED):
                await self.return_to_launch(drone_id)
        for drone in self.drones.values():
            if drone.connection:
                drone.connection.close()
        logger.info("Shutdown complete")

    # -- Simulation factory ----------------------------------------------------

    @classmethod
    async def simulate(
        cls,
        n_drones: int = 3,
        *,
        config: SwarmConfig | None = None,
        sitl_path: str | None = None,
        base_port: int = 5760,
        home: tuple[float, float] = (35.363261, -117.669056),
        spacing_m: float = 5.0,
        speedup: int = 1,
        auto_connect: bool = True,
    ) -> tuple[SwarmOrchestrator, SimulationHarness]:
        """
        Create a ready-to-fly simulated swarm.

        Launches *n_drones* ArduPilot SITL instances, registers them as
        ``sim-0``, ``sim-1``, ... ``sim-{n-1}``, and optionally connects.

        Returns ``(swarm, sim_harness)`` so the caller can later call
        ``await sim_harness.stop()`` to tear everything down.

        Example::

            swarm, sim = await Swarm.simulate(n_drones=3)
            await swarm.takeoff(altitude=10)
            # ... fly ...
            await swarm.shutdown()
            await sim.stop()
        """
        from .simulation import SimulationHarness

        sim = SimulationHarness(
            n_drones=n_drones,
            sitl_path=sitl_path,
            base_port=base_port,
            home=home,
            spacing_m=spacing_m,
            speedup=speedup,
        )
        await sim.start()

        swarm = cls(config=config)
        for inst in sim.instances:
            drone_name = f"sim-{inst.sysid - 1}"
            swarm.register_drone(drone_name, inst.connection_string)

        if auto_connect:
            await swarm.connect_all()

        return swarm, sim


# High-level alias for the simple public API
Swarm = SwarmOrchestrator
