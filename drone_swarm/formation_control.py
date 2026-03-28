"""
Consensus-based formation control with PID correction.

Implements a leader-follower formation controller that computes correction
waypoints to maintain formation shape despite GPS drift and wind disturbance.
Works alongside the existing ``formation()`` method: ``formation()`` sets the
initial positions, ``enable_formation_hold()`` maintains them via continuous
closed-loop correction in the telemetry loop.

Algorithm based on the consensus-based leader-follower approach recommended in
``design/FORMATION_CONTROL_LITERATURE_REVIEW.md`` (Section 1).

v0.5 uses proportional control only (kd=0, ki=0). Integral and derivative
terms are stubbed for future use.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from .drone import Drone, Waypoint

logger = logging.getLogger("drone_swarm.formation_control")

# ---------------------------------------------------------------------------
# GPS coordinate helpers (mirrors missions.py but kept local to avoid coupling)
# ---------------------------------------------------------------------------

_METERS_PER_DEG_LAT = 111_320.0


def _meters_per_deg_lon(lat: float) -> float:
    """Meters per degree of longitude at the given latitude."""
    return _METERS_PER_DEG_LAT * math.cos(math.radians(lat))


def ned_to_latlon(
    ref_lat: float, ref_lon: float, ref_alt: float,
    north_m: float, east_m: float, down_m: float,
) -> Waypoint:
    """Convert a NED offset from a reference point to a GPS Waypoint.

    Args:
        ref_lat: Reference latitude (degrees).
        ref_lon: Reference longitude (degrees).
        ref_alt: Reference altitude (meters, relative to home).
        north_m: Offset north in meters.
        east_m: Offset east in meters.
        down_m: Offset down in meters (positive = lower altitude).

    Returns:
        A :class:`Waypoint` at the computed GPS position.
    """
    lat = ref_lat + north_m / _METERS_PER_DEG_LAT
    lon = ref_lon + east_m / _meters_per_deg_lon(ref_lat)
    alt = ref_alt - down_m  # NED: positive down = lower altitude
    return Waypoint(lat=lat, lon=lon, alt=alt)


def latlon_to_ned(
    ref_lat: float, ref_lon: float, ref_alt: float,
    lat: float, lon: float, alt: float,
) -> tuple[float, float, float]:
    """Convert a GPS position to NED offset from a reference point.

    Returns:
        ``(north_m, east_m, down_m)`` tuple.
    """
    north = (lat - ref_lat) * _METERS_PER_DEG_LAT
    east = (lon - ref_lon) * _meters_per_deg_lon(ref_lat)
    down = -(alt - ref_alt)
    return north, east, down


# ---------------------------------------------------------------------------
# FormationGains dataclass
# ---------------------------------------------------------------------------

@dataclass
class FormationGains:
    """PID gains for formation correction.

    v0.5 uses proportional control only. The ``ki`` and ``kd`` fields are
    reserved for future integral and derivative terms.

    Attributes:
        kp: Proportional gain (default 0.8).
        ki: Integral gain (default 0.0 -- unused in v0.5).
        kd: Derivative gain (default 0.0 -- unused in v0.5).
        max_correction_m: Maximum correction magnitude in meters.
            Corrections are clamped to this value per axis to prevent
            over-shooting.
    """
    kp: float = 0.8
    ki: float = 0.0
    kd: float = 0.0
    max_correction_m: float = 5.0


# ---------------------------------------------------------------------------
# FormationController
# ---------------------------------------------------------------------------

class FormationController:
    """Closed-loop formation controller using leader-follower consensus.

    Computes correction waypoints that push follower drones toward their
    target offsets from the leader. The controller is designed to run
    inside the telemetry loop at ~10 Hz.

    Example::

        ctrl = FormationController()
        ctrl.set_formation({
            "bravo": (0, -15, 0),   # 15m left of leader
            "charlie": (0, 15, 0),  # 15m right of leader
        })
        corrections = ctrl.compute_corrections(leader, followers)
        for drone_id, wp in corrections.items():
            await swarm.goto(drone_id, wp)
    """

    def __init__(self, gains: FormationGains | None = None) -> None:
        self.gains = gains or FormationGains()
        self._offsets: dict[str, tuple[float, float, float]] = {}
        # Integral state per drone: accumulated error (north, east, down)
        self._integral: dict[str, tuple[float, float, float]] = {}
        # Previous error per drone for derivative term
        self._prev_error: dict[str, tuple[float, float, float]] = {}

    def set_formation(
        self, offsets: dict[str, tuple[float, float, float]],
    ) -> None:
        """Define target NED offsets (meters) per follower drone from the leader.

        Args:
            offsets: Mapping of ``drone_id`` to ``(north_m, east_m, down_m)``
                offset from the leader's position.
        """
        self._offsets = dict(offsets)
        # Reset controller state when formation changes
        self._integral.clear()
        self._prev_error.clear()
        logger.info(
            "Formation set: %d followers, offsets=%s",
            len(offsets), offsets,
        )

    @property
    def offsets(self) -> dict[str, tuple[float, float, float]]:
        """Currently configured formation offsets."""
        return dict(self._offsets)

    def compute_corrections(
        self,
        leader: Drone,
        followers: dict[str, Drone],
    ) -> dict[str, Waypoint]:
        """Compute correction waypoints for all followers.

        For each follower, computes the error between its current position
        and its target position (leader + offset), applies PID gains, clamps
        the correction, and returns a waypoint at the corrected position.

        Args:
            leader: The leader drone (reference point for offsets).
            followers: Mapping of ``drone_id`` to ``Drone`` for all followers
                that should be corrected.

        Returns:
            Mapping of ``drone_id`` to corrected :class:`Waypoint`.
            Only includes drones that have configured offsets.
        """
        corrections: dict[str, Waypoint] = {}
        gains = self.gains

        for drone_id, drone in followers.items():
            if drone_id not in self._offsets:
                continue

            offset = self._offsets[drone_id]

            # Target position in GPS coordinates
            target = ned_to_latlon(
                leader.lat, leader.lon, leader.alt,
                offset[0], offset[1], offset[2],
            )

            # Current position error in NED meters
            err_north, err_east, err_down = latlon_to_ned(
                drone.lat, drone.lon, drone.alt,
                target.lat, target.lon, target.alt,
            )

            # --- P term ---
            p_north = gains.kp * err_north
            p_east = gains.kp * err_east
            p_down = gains.kp * err_down

            # --- I term (future) ---
            prev_int = self._integral.get(drone_id, (0.0, 0.0, 0.0))
            i_north = prev_int[0] + gains.ki * err_north
            i_east = prev_int[1] + gains.ki * err_east
            i_down = prev_int[2] + gains.ki * err_down
            self._integral[drone_id] = (i_north, i_east, i_down)

            # --- D term (future) ---
            prev_err = self._prev_error.get(drone_id, (0.0, 0.0, 0.0))
            d_north = gains.kd * (err_north - prev_err[0])
            d_east = gains.kd * (err_east - prev_err[1])
            d_down = gains.kd * (err_down - prev_err[2])
            self._prev_error[drone_id] = (err_north, err_east, err_down)

            # Sum PID components
            corr_north = p_north + i_north + d_north
            corr_east = p_east + i_east + d_east
            corr_down = p_down + i_down + d_down

            # Clamp correction magnitude per axis
            max_c = gains.max_correction_m
            corr_north = max(-max_c, min(max_c, corr_north))
            corr_east = max(-max_c, min(max_c, corr_east))
            corr_down = max(-max_c, min(max_c, corr_down))

            # Correction waypoint: current position + correction
            wp = ned_to_latlon(
                drone.lat, drone.lon, drone.alt,
                corr_north, corr_east, corr_down,
            )
            corrections[drone_id] = wp

        return corrections


# ---------------------------------------------------------------------------
# Standalone error computation
# ---------------------------------------------------------------------------

def compute_formation_error(
    leader: Drone,
    followers: dict[str, Drone],
    offsets: dict[str, tuple[float, float, float]],
) -> dict[str, float]:
    """Compute the Euclidean position error (meters) for each follower.

    For each follower with a configured offset, computes the 3D distance
    between its current position and its target position (leader + offset).

    Args:
        leader: The leader drone.
        followers: Mapping of ``drone_id`` to ``Drone``.
        offsets: Mapping of ``drone_id`` to ``(north_m, east_m, down_m)``
            offset from the leader.

    Returns:
        Mapping of ``drone_id`` to error distance in meters.
    """
    errors: dict[str, float] = {}
    for drone_id, drone in followers.items():
        if drone_id not in offsets:
            continue
        offset = offsets[drone_id]
        target = ned_to_latlon(
            leader.lat, leader.lon, leader.alt,
            offset[0], offset[1], offset[2],
        )
        n, e, d = latlon_to_ned(
            drone.lat, drone.lon, drone.alt,
            target.lat, target.lon, target.alt,
        )
        errors[drone_id] = math.sqrt(n * n + e * e + d * d)
    return errors
