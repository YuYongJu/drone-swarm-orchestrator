"""
Drone health scoring -- composite 0-100 score from multiple telemetry inputs.

Aggregates battery level, GPS quality, heartbeat freshness, vibration level,
and communication quality into a single weighted score. The telemetry loop
calls ``compute_health_score`` each cycle to keep the score current.
"""

from __future__ import annotations

import logging
import time

from .drone import Drone

logger = logging.getLogger("drone_swarm.health")


# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

WEIGHT_BATTERY = 0.30
WEIGHT_GPS = 0.25
WEIGHT_HEARTBEAT = 0.25
WEIGHT_VIBRATION = 0.10
WEIGHT_COMMS = 0.10


# ---------------------------------------------------------------------------
# Individual metric scorers (each returns 0-100)
# ---------------------------------------------------------------------------

def _score_battery(battery_pct: float) -> float:
    """
    Battery score: 100 if >80%, linear decrease to 0 at 10%.

    Below 10% -> 0. Above 80% -> 100.
    """
    if battery_pct >= 80.0:
        return 100.0
    if battery_pct <= 10.0:
        return 0.0
    # Linear from 10% -> 0 to 80% -> 100
    return (battery_pct - 10.0) / (80.0 - 10.0) * 100.0


def _score_gps(satellite_count: int) -> float:
    """
    GPS score: 100 if >=8 sats, 0 if <=4 sats, linear between.
    """
    if satellite_count >= 8:
        return 100.0
    if satellite_count <= 4:
        return 0.0
    return (satellite_count - 4) / (8 - 4) * 100.0


def _score_heartbeat(last_heartbeat: float) -> float:
    """
    Heartbeat freshness: 100 if <1s stale, 0 if >10s stale, linear between.

    If last_heartbeat is 0 (never received), returns 0.
    """
    if last_heartbeat <= 0:
        return 0.0
    staleness = time.time() - last_heartbeat
    if staleness <= 1.0:
        return 100.0
    if staleness >= 10.0:
        return 0.0
    return (10.0 - staleness) / (10.0 - 1.0) * 100.0


def _score_vibration(vibration_level: float) -> float:
    """
    Vibration score: 100 if <=5 m/s/s, 0 if >=30 m/s/s, linear between.

    vibration_level is the max of x, y, z vibration values.
    A negative value (or -1 sentinel) means no data -- return 100 (assume OK).
    """
    if vibration_level < 0:
        return 100.0  # no data available, assume OK
    if vibration_level <= 5.0:
        return 100.0
    if vibration_level >= 30.0:
        return 0.0
    return (30.0 - vibration_level) / (30.0 - 5.0) * 100.0


def _score_comms(message_loss_rate: float) -> float:
    """
    Communication quality: 100 if 0% loss, 0 if >=50% loss, linear between.

    message_loss_rate is a fraction [0.0, 1.0].
    A negative value means no data -- return 100.
    """
    if message_loss_rate < 0:
        return 100.0
    if message_loss_rate <= 0.0:
        return 100.0
    if message_loss_rate >= 0.5:
        return 0.0
    return (0.5 - message_loss_rate) / 0.5 * 100.0


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

def compute_health_score(drone: Drone) -> float:
    """
    Compute a composite 0-100 health score for a drone.

    Uses these fields from the Drone dataclass:
    - ``battery_pct``: battery percentage
    - ``gps_satellite_count``: number of visible GPS satellites
    - ``last_heartbeat``: timestamp of last heartbeat
    - ``vibration_level``: max vibration (m/s/s), -1 if unavailable
    - ``message_loss_rate``: fraction of lost messages, -1 if unavailable

    Returns a float clamped to [0, 100].
    """
    battery_score = _score_battery(drone.battery_pct)
    gps_score = _score_gps(getattr(drone, "gps_satellite_count", 0))
    heartbeat_score = _score_heartbeat(drone.last_heartbeat)
    vibration_score = _score_vibration(
        getattr(drone, "vibration_level", -1.0)
    )
    comms_score = _score_comms(
        getattr(drone, "message_loss_rate", -1.0)
    )

    composite = (
        WEIGHT_BATTERY * battery_score
        + WEIGHT_GPS * gps_score
        + WEIGHT_HEARTBEAT * heartbeat_score
        + WEIGHT_VIBRATION * vibration_score
        + WEIGHT_COMMS * comms_score
    )

    # Clamp to [0, 100]
    return max(0.0, min(100.0, composite))
