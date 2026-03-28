"""
Anomaly detection for drone swarm telemetry.

Implements the "compare-to-neighbors" pattern from the telemetry literature
review (Section 3): each drone's metrics are checked both against its own
historical baseline (moving average + z-score) and against the swarm as a
whole.  When one drone deviates significantly from its peers -- e.g. battery
draining 3x faster, GPS jumping while others are stable -- an ``Anomaly``
is raised so the operator (or an automated handler) can react.

Anomaly types detected:
- ``battery_drain``       -- drain rate far exceeds swarm average
- ``gps_jump``            -- sudden position change > 10 m (spoofing indicator)
- ``altitude_drift``      -- slow drift from commanded altitude
- ``vibration_spike``     -- sudden vibration increase (propeller damage)
- ``comms_degradation``   -- message loss rate climbing
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .geo import haversine as _haversine

if TYPE_CHECKING:
    from .drone import Drone

logger = logging.getLogger("drone_swarm.anomaly")

# ---------------------------------------------------------------------------
# Anomaly data model
# ---------------------------------------------------------------------------


@dataclass
class Anomaly:
    """A single detected anomaly for a drone."""

    drone_id: str
    anomaly_type: str  # battery_drain, gps_jump, altitude_drift, vibration_spike, comms_degradation
    severity: float  # 0.0 to 1.0
    message: str
    metric_value: float
    expected_value: float


# ---------------------------------------------------------------------------
# Rolling window helper
# ---------------------------------------------------------------------------


@dataclass
class _RollingWindow:
    """Fixed-size deque with convenience statistics."""

    maxlen: int
    _data: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self._data = deque(maxlen=self.maxlen)

    def append(self, value: float) -> None:
        self._data.append(value)

    def __len__(self) -> int:
        return len(self._data)

    @property
    def values(self) -> list[float]:
        return list(self._data)

    def mean(self) -> float:
        if not self._data:
            return 0.0
        return sum(self._data) / len(self._data)

    def std(self) -> float:
        n = len(self._data)
        if n < 2:
            return 0.0
        mu = self.mean()
        return math.sqrt(sum((x - mu) ** 2 for x in self._data) / n)

    @property
    def last(self) -> float | None:
        return self._data[-1] if self._data else None

    @property
    def previous(self) -> float | None:
        return self._data[-2] if len(self._data) >= 2 else None


# ---------------------------------------------------------------------------
# Per-drone metric tracker
# ---------------------------------------------------------------------------

_TRACKED_METRICS = (
    "battery_pct",
    "lat",
    "lon",
    "alt",
    "vibration_level",
    "message_loss_rate",
)


@dataclass
class _DroneMetrics:
    """Rolling windows for every tracked metric of a single drone."""

    window_size: int
    windows: dict[str, _RollingWindow] = field(init=False)

    def __post_init__(self) -> None:
        self.windows = {m: _RollingWindow(maxlen=self.window_size) for m in _TRACKED_METRICS}


# ---------------------------------------------------------------------------
# AnomalyDetector
# ---------------------------------------------------------------------------

# Thresholds
_GPS_JUMP_THRESHOLD_M = 10.0  # metres between consecutive readings
_Z_SCORE_THRESHOLD = 2.5  # standard deviations for individual anomaly
_SWARM_BATTERY_DRAIN_FACTOR = 3.0  # one drone drains N x faster than average
_SWARM_GPS_STABILITY_FACTOR = 3.0  # GPS jump vs swarm average
_ALTITUDE_DRIFT_M = 5.0  # metres of drift to flag
_VIBRATION_SPIKE_FACTOR = 2.0  # sudden increase factor
_COMMS_DEGRADATION_THRESHOLD = 0.2  # absolute loss-rate jump


class AnomalyDetector:
    """Detect telemetry anomalies for individual drones and across the swarm.

    Parameters
    ----------
    window_size:
        Number of readings retained per metric for rolling statistics.
    """

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size
        self._metrics: dict[str, _DroneMetrics] = {}

    # -- public API ----------------------------------------------------------

    def update(self, drone_id: str, metrics: dict[str, float]) -> None:
        """Feed new telemetry readings for *drone_id*."""
        if drone_id not in self._metrics:
            self._metrics[drone_id] = _DroneMetrics(window_size=self.window_size)
        dm = self._metrics[drone_id]
        for key, value in metrics.items():
            if key in dm.windows:
                dm.windows[key].append(value)

    def check_individual(self, drone_id: str) -> list[Anomaly]:
        """Detect anomalies by comparing a drone's latest readings to its own history."""
        if drone_id not in self._metrics:
            return []
        dm = self._metrics[drone_id]
        anomalies: list[Anomaly] = []

        # --- GPS jump ---
        anomalies.extend(self._check_gps_jump(drone_id, dm))

        # --- Battery drain (individual z-score) ---
        anomalies.extend(self._check_individual_zscore(
            drone_id, dm, "battery_pct", "battery_drain",
            "Battery drain rate anomaly detected",
        ))

        # --- Vibration spike ---
        anomalies.extend(self._check_vibration_spike(drone_id, dm))

        # --- Comms degradation ---
        anomalies.extend(self._check_comms_degradation(drone_id, dm))

        # --- Altitude drift (individual) ---
        anomalies.extend(self._check_altitude_drift_individual(drone_id, dm))

        return anomalies

    def check_swarm(self, drones: dict[str, Drone]) -> list[Anomaly]:
        """Compare each drone to the rest of the swarm (the "compare-to-neighbors" pattern).

        Checks battery drain rate, GPS stability, and vibration level
        relative to the swarm average.
        """
        anomalies: list[Anomaly] = []
        drone_ids = [did for did in drones if did in self._metrics]
        if len(drone_ids) < 2:
            return anomalies

        anomalies.extend(self._check_swarm_battery(drone_ids))
        anomalies.extend(self._check_swarm_gps(drone_ids))
        anomalies.extend(self._check_swarm_vibration(drone_ids))
        anomalies.extend(self._check_swarm_comms(drone_ids))

        return anomalies

    # -- individual checks ---------------------------------------------------

    def _check_gps_jump(self, drone_id: str, dm: _DroneMetrics) -> list[Anomaly]:
        lat_win = dm.windows["lat"]
        lon_win = dm.windows["lon"]
        if len(lat_win) < 2 or len(lon_win) < 2:
            return []
        prev_lat, cur_lat = lat_win.previous, lat_win.last
        prev_lon, cur_lon = lon_win.previous, lon_win.last
        assert prev_lat is not None and cur_lat is not None
        assert prev_lon is not None and cur_lon is not None

        dist = _haversine(prev_lat, prev_lon, cur_lat, cur_lon)
        if dist > _GPS_JUMP_THRESHOLD_M:
            severity = min(1.0, dist / (_GPS_JUMP_THRESHOLD_M * 10))
            return [Anomaly(
                drone_id=drone_id,
                anomaly_type="gps_jump",
                severity=severity,
                message=f"GPS position jumped {dist:.1f}m between consecutive readings",
                metric_value=dist,
                expected_value=0.0,
            )]
        return []

    def _check_individual_zscore(
        self,
        drone_id: str,
        dm: _DroneMetrics,
        metric: str,
        anomaly_type: str,
        message_prefix: str,
    ) -> list[Anomaly]:
        win = dm.windows[metric]
        if len(win) < 5:  # need enough history
            return []
        mu = win.mean()
        sigma = win.std()
        if sigma == 0:
            return []
        latest = win.last
        assert latest is not None
        z = abs(latest - mu) / sigma
        if z > _Z_SCORE_THRESHOLD:
            severity = min(1.0, z / (_Z_SCORE_THRESHOLD * 3))
            return [Anomaly(
                drone_id=drone_id,
                anomaly_type=anomaly_type,
                severity=severity,
                message=f"{message_prefix} (z-score={z:.1f})",
                metric_value=latest,
                expected_value=mu,
            )]
        return []

    def _check_vibration_spike(self, drone_id: str, dm: _DroneMetrics) -> list[Anomaly]:
        win = dm.windows["vibration_level"]
        if len(win) < 3:
            return []
        latest = win.last
        assert latest is not None
        if latest < 0:
            return []
        # Compare latest to the mean of all prior readings
        prior = win.values[:-1]
        prior_valid = [v for v in prior if v >= 0]
        if not prior_valid:
            return []
        prior_mean = sum(prior_valid) / len(prior_valid)
        if prior_mean <= 0:
            return []
        ratio = latest / prior_mean
        if ratio > _VIBRATION_SPIKE_FACTOR:
            severity = min(1.0, (ratio - 1.0) / 4.0)
            return [Anomaly(
                drone_id=drone_id,
                anomaly_type="vibration_spike",
                severity=severity,
                message=f"Vibration spiked to {latest:.1f} ({ratio:.1f}x normal {prior_mean:.1f})",
                metric_value=latest,
                expected_value=prior_mean,
            )]
        return []

    def _check_comms_degradation(self, drone_id: str, dm: _DroneMetrics) -> list[Anomaly]:
        win = dm.windows["message_loss_rate"]
        if len(win) < 3:
            return []
        latest = win.last
        assert latest is not None
        if latest < 0:
            return []
        prior = win.values[:-1]
        prior_valid = [v for v in prior if v >= 0]
        if not prior_valid:
            return []
        prior_mean = sum(prior_valid) / len(prior_valid)
        increase = latest - prior_mean
        if increase > _COMMS_DEGRADATION_THRESHOLD:
            severity = min(1.0, increase / 0.5)
            return [Anomaly(
                drone_id=drone_id,
                anomaly_type="comms_degradation",
                severity=severity,
                message=(
                    f"Message loss rate jumped from {prior_mean:.2f} to {latest:.2f} "
                    f"(+{increase:.2f})"
                ),
                metric_value=latest,
                expected_value=prior_mean,
            )]
        return []

    def _check_altitude_drift_individual(self, drone_id: str, dm: _DroneMetrics) -> list[Anomaly]:
        win = dm.windows["alt"]
        if len(win) < 5:
            return []
        mu = win.mean()
        latest = win.last
        assert latest is not None
        drift = abs(latest - mu)
        if drift > _ALTITUDE_DRIFT_M:
            severity = min(1.0, drift / (_ALTITUDE_DRIFT_M * 4))
            return [Anomaly(
                drone_id=drone_id,
                anomaly_type="altitude_drift",
                severity=severity,
                message=f"Altitude drifted {drift:.1f}m from moving average ({mu:.1f}m)",
                metric_value=latest,
                expected_value=mu,
            )]
        return []

    # -- swarm-level checks --------------------------------------------------

    def _drain_rate(self, drone_id: str) -> float | None:
        """Return battery drain per tick (positive = draining)."""
        win = self._metrics[drone_id].windows["battery_pct"]
        if len(win) < 2:
            return None
        vals = win.values
        return vals[0] - vals[-1]  # positive means battery decreased

    def _gps_jump_magnitude(self, drone_id: str) -> float | None:
        dm = self._metrics[drone_id]
        lat_win = dm.windows["lat"]
        lon_win = dm.windows["lon"]
        if len(lat_win) < 2:
            return None
        return _haversine(
            lat_win.previous, lon_win.previous,  # type: ignore[arg-type]
            lat_win.last, lon_win.last,  # type: ignore[arg-type]
        )

    def _check_swarm_battery(self, drone_ids: list[str]) -> list[Anomaly]:
        rates = {did: self._drain_rate(did) for did in drone_ids}
        valid = {did: r for did, r in rates.items() if r is not None and r > 0}
        if len(valid) < 2:
            return []
        anomalies: list[Anomaly] = []
        for did, rate in valid.items():
            # Compare to *other* drones (exclude self from average)
            others = [r for d, r in valid.items() if d != did]
            if not others:
                continue
            others_avg = sum(others) / len(others)
            if others_avg <= 0:
                continue
            ratio = rate / others_avg
            if ratio > _SWARM_BATTERY_DRAIN_FACTOR:
                severity = min(1.0, (ratio - 1) / 5)
                anomalies.append(Anomaly(
                    drone_id=did,
                    anomaly_type="battery_drain",
                    severity=severity,
                    message=(
                        f"Battery draining {ratio:.1f}x faster than swarm peers "
                        f"({rate:.1f}% vs peers avg {others_avg:.1f}%)"
                    ),
                    metric_value=rate,
                    expected_value=others_avg,
                ))
        return anomalies

    def _check_swarm_gps(self, drone_ids: list[str]) -> list[Anomaly]:
        jumps = {did: self._gps_jump_magnitude(did) for did in drone_ids}
        valid = {did: j for did, j in jumps.items() if j is not None}
        if len(valid) < 2:
            return []
        anomalies: list[Anomaly] = []
        for did, jump in valid.items():
            # Compare to *other* drones (exclude self from average)
            others = [j for d, j in valid.items() if d != did]
            if not others:
                continue
            others_avg = sum(others) / len(others)
            # Flag if jump is large AND much larger than peers
            ratio = jump / max(others_avg, 0.01)
            if (
                jump > _GPS_JUMP_THRESHOLD_M
                and (others_avg <= 0 or ratio > _SWARM_GPS_STABILITY_FACTOR)
            ):
                severity = min(1.0, jump / (_GPS_JUMP_THRESHOLD_M * 10))
                anomalies.append(Anomaly(
                    drone_id=did,
                    anomaly_type="gps_jump",
                    severity=severity,
                    message=(
                        f"GPS jumped {jump:.1f}m while swarm peers average {others_avg:.1f}m"
                    ),
                    metric_value=jump,
                    expected_value=others_avg,
                ))
        return anomalies

    def _check_swarm_vibration(self, drone_ids: list[str]) -> list[Anomaly]:
        levels: dict[str, float] = {}
        for did in drone_ids:
            win = self._metrics[did].windows["vibration_level"]
            if win.last is not None and win.last >= 0:
                levels[did] = win.last
        if len(levels) < 2:
            return []
        anomalies: list[Anomaly] = []
        for did, level in levels.items():
            others = [v for d, v in levels.items() if d != did]
            if not others:
                continue
            others_avg = sum(others) / len(others)
            if others_avg <= 0:
                continue
            ratio = level / others_avg
            if ratio > _VIBRATION_SPIKE_FACTOR:
                severity = min(1.0, (ratio - 1) / 4)
                anomalies.append(Anomaly(
                    drone_id=did,
                    anomaly_type="vibration_spike",
                    severity=severity,
                    message=(
                        f"Vibration {level:.1f} is {ratio:.1f}x swarm peers avg ({others_avg:.1f})"
                    ),
                    metric_value=level,
                    expected_value=others_avg,
                ))
        return anomalies

    def _check_swarm_comms(self, drone_ids: list[str]) -> list[Anomaly]:
        rates: dict[str, float] = {}
        for did in drone_ids:
            win = self._metrics[did].windows["message_loss_rate"]
            if win.last is not None and win.last >= 0:
                rates[did] = win.last
        if len(rates) < 2:
            return []
        anomalies: list[Anomaly] = []
        for did, rate in rates.items():
            others = [r for d, r in rates.items() if d != did]
            if not others:
                continue
            others_avg = sum(others) / len(others)
            excess = rate - others_avg
            if excess > _COMMS_DEGRADATION_THRESHOLD:
                severity = min(1.0, excess / 0.5)
                anomalies.append(Anomaly(
                    drone_id=did,
                    anomaly_type="comms_degradation",
                    severity=severity,
                    message=(
                        f"Message loss {rate:.2f} exceeds swarm peers avg {others_avg:.2f} "
                        f"by {excess:.2f}"
                    ),
                    metric_value=rate,
                    expected_value=others_avg,
                ))
        return anomalies
