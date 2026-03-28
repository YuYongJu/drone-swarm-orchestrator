"""
Wind estimation from multirotor tilt angles.

A hovering multirotor must tilt into the wind to maintain position. The tilt
angle and direction directly encode wind speed and direction:

    wind_speed = k * tan(tilt_angle)

where *k* depends on the drone's weight and thrust characteristics.

References:
- Hattenberger et al., "Estimating Wind Using a Quadrotor", Int. J. Micro Air Vehicles, 2022.
- "Wind Estimation with Multirotor UAVs", Atmosphere, 2022.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .drone import Drone


@dataclass
class WindEstimate:
    """Estimated wind vector at a point in space.

    Attributes:
        speed_ms: Wind speed in metres per second.
        direction_deg: Direction the wind is coming FROM, in degrees
            (meteorological convention, 0 = from north, 90 = from east).
        confidence: Confidence in the estimate, 0.0 (no confidence) to
            1.0 (highly confident).
    """
    speed_ms: float
    direction_deg: float
    confidence: float


@dataclass
class WindEstimator:
    """Per-drone wind estimator using tilt-angle method.

    Parameters:
        k_factor: Proportionality constant relating tilt angle to wind speed.
            Depends on drone mass and rotor thrust.  For a typical ~1.5 kg
            quadrotor, k ~ 9.81 (i.e., weight / mass is g, and
            wind = g * tan(tilt)).  Defaults to ``9.81``.
        max_tilt_rad: Maximum tilt angle (radians) to consider valid.
            Larger tilts are likely aggressive manoeuvres, not wind.
            Default 0.35 rad (~20 deg).
        ema_alpha: Exponential moving average smoothing factor (0-1).
            Higher = more responsive, lower = smoother.  Default 0.3.
    """

    k_factor: float = 9.81
    max_tilt_rad: float = 0.35
    ema_alpha: float = 0.3

    # Internal smoothed state
    _smoothed_speed: float = field(default=0.0, init=False, repr=False)
    _smoothed_dir_x: float = field(default=0.0, init=False, repr=False)
    _smoothed_dir_y: float = field(default=0.0, init=False, repr=False)
    _has_update: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def update(
        self,
        drone: Drone,
        attitude_roll: float,
        attitude_pitch: float,
        groundspeed: float,
        heading: float,
    ) -> None:
        """Ingest a new telemetry sample and update the wind estimate.

        Args:
            drone: The :class:`Drone` instance (currently unused beyond
                identification; reserved for future per-drone calibration).
            attitude_roll: Roll angle in **radians** (positive = right wing down).
            attitude_pitch: Pitch angle in **radians** (positive = nose up).
            groundspeed: Ground speed in m/s (from GPS).
            heading: Heading in **degrees** (0-360, true north).
        """
        # Total tilt magnitude
        tilt = math.sqrt(attitude_roll ** 2 + attitude_pitch ** 2)

        # Clamp to max_tilt_rad -- if exceeded, treat as manoeuvre, not wind
        if tilt > self.max_tilt_rad:
            tilt = self.max_tilt_rad

        # Wind speed from tilt
        raw_speed = self.k_factor * math.tan(tilt)

        # Wind direction: the drone tilts INTO the wind, so the wind is
        # coming from the direction the drone is leaning towards.
        # atan2(-roll, -pitch) gives the tilt direction in body frame
        # (towards which the drone leans); add heading to convert to earth frame.
        if tilt > 1e-6:
            # Body-frame tilt direction (radians, CW from nose)
            tilt_dir_body_rad = math.atan2(-attitude_roll, -attitude_pitch)
            # Convert to earth frame and then to meteorological "from" direction
            wind_from_deg = (math.degrees(tilt_dir_body_rad) + heading) % 360.0
        else:
            wind_from_deg = 0.0

        # Decompose direction into unit vector for circular averaging
        wind_rad = math.radians(wind_from_deg)
        dir_x = math.cos(wind_rad)
        dir_y = math.sin(wind_rad)

        # Exponential moving average
        a = self.ema_alpha
        self._smoothed_speed = a * raw_speed + (1 - a) * self._smoothed_speed
        self._smoothed_dir_x = a * dir_x + (1 - a) * self._smoothed_dir_x
        self._smoothed_dir_y = a * dir_y + (1 - a) * self._smoothed_dir_y
        self._has_update = True

    def get_wind(self) -> WindEstimate:
        """Return the current smoothed wind estimate.

        If no updates have been received yet, returns zero wind with zero
        confidence.
        """
        if not self._has_update:
            return WindEstimate(speed_ms=0.0, direction_deg=0.0, confidence=0.0)

        speed = self._smoothed_speed

        # Recover direction from averaged unit-vector components
        direction_deg = math.degrees(
            math.atan2(self._smoothed_dir_y, self._smoothed_dir_x)
        ) % 360.0

        # Confidence heuristic: higher speed = more confident (tilt signal
        # is stronger relative to noise).  Saturates at 1.0 around 10 m/s.
        confidence = min(1.0, speed / 10.0)

        return WindEstimate(
            speed_ms=round(speed, 4),
            direction_deg=round(direction_deg, 2),
            confidence=round(confidence, 4),
        )

    # ------------------------------------------------------------------ #
    # Swarm-level aggregation
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_swarm_wind(
        drones: dict[str, Drone], estimators: dict[str, WindEstimator],
    ) -> WindEstimate:
        """Average wind estimate from all drones in the swarm.

        Using multiple spatially-distributed drones yields a more accurate
        wind estimate than any single drone (noise averages out).

        Args:
            drones: Mapping of drone_id to :class:`Drone`.
            estimators: Mapping of drone_id to the corresponding
                :class:`WindEstimator` (must have received at least one
                :meth:`update` call).

        Returns:
            A :class:`WindEstimate` with the averaged speed, direction,
            and mean confidence.
        """
        estimates: list[WindEstimate] = []
        for drone_id in drones:
            est = estimators.get(drone_id)
            if est is not None and est._has_update:
                estimates.append(est.get_wind())

        if not estimates:
            return WindEstimate(speed_ms=0.0, direction_deg=0.0, confidence=0.0)

        # Average speed
        avg_speed = sum(e.speed_ms for e in estimates) / len(estimates)

        # Circular average of direction
        sum_x = sum(math.cos(math.radians(e.direction_deg)) for e in estimates)
        sum_y = sum(math.sin(math.radians(e.direction_deg)) for e in estimates)
        avg_dir = math.degrees(math.atan2(sum_y, sum_x)) % 360.0

        # Mean confidence
        avg_conf = sum(e.confidence for e in estimates) / len(estimates)

        return WindEstimate(
            speed_ms=round(avg_speed, 4),
            direction_deg=round(avg_dir, 2),
            confidence=round(avg_conf, 4),
        )
