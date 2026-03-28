"""
Persistent flight logging with JSON export and replay support.

Records telemetry snapshots at configurable intervals and exports
structured flight logs for post-flight analysis, regulatory compliance,
and mission replay.

Uses a ring-buffer per drone for memory efficiency during long flights
(fixed memory regardless of flight duration when buffer is full).

Usage::

    from drone_swarm.flight_log import FlightLogger

    logger = FlightLogger(interval_s=0.5)
    swarm.add_behavior(logger)  # auto-records during flight
    # ... fly ...
    logger.export_json("logs/flight_001.json")

    # Replay
    from drone_swarm.flight_log import load_flight_log
    log = load_flight_log("logs/flight_001.json")
    for drone_id, records in log.drones.items():
        print(f"{drone_id}: {len(records)} snapshots")
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .behavior import Behavior

if TYPE_CHECKING:
    from .drone import Drone
    from .swarm import SwarmOrchestrator

logger = logging.getLogger("drone_swarm.flight_log")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TelemetrySnapshot:
    """A single telemetry reading for one drone at one point in time.

    All fields use SI units. Timestamps are Unix epoch (seconds).
    """

    t: float  # Unix timestamp
    lat: float
    lon: float
    alt: float  # metres AGL
    heading: float  # degrees
    battery_pct: float
    speed_ms: float = 0.0  # ground speed estimate
    health_score: float = 100.0
    gps_sats: int = 0
    status: str = "unknown"


@dataclass
class FlightLog:
    """A complete flight log containing telemetry for all drones.

    Attributes:
        version: Log format version (for forward compatibility).
        start_time: Unix timestamp when logging started.
        end_time: Unix timestamp when logging stopped (0 if still running).
        drones: Mapping of drone_id to list of telemetry snapshots.
        metadata: Arbitrary key-value metadata (mission name, operator, etc.).
    """

    version: int = 1
    start_time: float = 0.0
    end_time: float = 0.0
    drones: dict[str, list[TelemetrySnapshot]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FlightLogger behavior
# ---------------------------------------------------------------------------


class FlightLogger(Behavior):
    """Behavior that records telemetry snapshots to an in-memory log.

    Register on the swarm as a behavior — it automatically captures
    telemetry every ``interval_s`` seconds during the telemetry loop.

    Args:
        interval_s: Minimum time between snapshots (default 0.5s = 2 Hz).
        max_snapshots_per_drone: Ring buffer size per drone. When full,
            oldest snapshots are dropped. Default 36000 (~5 hours at 2 Hz).
        metadata: Optional key-value metadata to include in exports.
    """

    name = "flight_logger"
    priority = -10  # Low priority — runs after safety behaviors

    def __init__(
        self,
        interval_s: float = 0.5,
        max_snapshots_per_drone: int = 36_000,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.interval_s = interval_s
        self.max_snapshots = max_snapshots_per_drone
        self.metadata = metadata or {}
        self._buffers: dict[str, deque[TelemetrySnapshot]] = {}
        self._last_record_time: float = 0.0
        self._start_time: float = 0.0

    async def setup(self, swarm: SwarmOrchestrator) -> None:
        self._start_time = time.time()
        self._buffers.clear()
        logger.info(
            "Flight logging started (interval=%.1fs, buffer=%d per drone)",
            self.interval_s, self.max_snapshots,
        )

    async def on_tick(
        self,
        swarm: SwarmOrchestrator,
        drones: dict[str, Drone],
    ) -> None:
        now = time.time()
        if now - self._last_record_time < self.interval_s:
            return

        self._last_record_time = now
        for drone_id, drone in drones.items():
            if drone_id not in self._buffers:
                self._buffers[drone_id] = deque(maxlen=self.max_snapshots)

            self._buffers[drone_id].append(TelemetrySnapshot(
                t=now,
                lat=drone.lat,
                lon=drone.lon,
                alt=drone.alt,
                heading=drone.heading,
                battery_pct=drone.battery_pct,
                health_score=drone.health_score,
                gps_sats=drone.gps_satellite_count,
                status=drone.status.value,
            ))

    async def teardown(self, swarm: SwarmOrchestrator) -> None:
        total = sum(len(buf) for buf in self._buffers.values())
        logger.info(
            "Flight logging stopped (%d snapshots across %d drones)",
            total, len(self._buffers),
        )

    # -- Export / query -------------------------------------------------------

    def to_flight_log(self) -> FlightLog:
        """Convert the current buffer to a :class:`FlightLog` dataclass."""
        return FlightLog(
            version=1,
            start_time=self._start_time,
            end_time=time.time(),
            drones={
                drone_id: list(buf)
                for drone_id, buf in self._buffers.items()
            },
            metadata=self.metadata,
        )

    def export_json(self, path: str | Path) -> Path:
        """Export the flight log to a JSON file.

        Args:
            path: Output file path. Parent directories are created if needed.

        Returns:
            The resolved output path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        log = self.to_flight_log()
        data = {
            "version": log.version,
            "start_time": log.start_time,
            "end_time": log.end_time,
            "metadata": log.metadata,
            "drones": {
                drone_id: [asdict(s) for s in snapshots]
                for drone_id, snapshots in log.drones.items()
            },
        }

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        total = sum(len(s) for s in log.drones.values())
        logger.info(
            "Flight log exported to %s (%d snapshots, %d drones)",
            path, total, len(log.drones),
        )
        return path.resolve()

    def snapshot_count(self, drone_id: str | None = None) -> int:
        """Return the number of recorded snapshots.

        Args:
            drone_id: If given, count only that drone. Otherwise count all.
        """
        if drone_id is not None:
            buf = self._buffers.get(drone_id)
            return len(buf) if buf else 0
        return sum(len(buf) for buf in self._buffers.values())

    def latest(self, drone_id: str) -> TelemetrySnapshot | None:
        """Return the most recent snapshot for a drone, or ``None``."""
        buf = self._buffers.get(drone_id)
        return buf[-1] if buf else None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_flight_log(path: str | Path) -> FlightLog:
    """Load a flight log from a JSON file exported by :class:`FlightLogger`.

    Args:
        path: Path to the JSON flight log file.

    Returns:
        A :class:`FlightLog` with all telemetry data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unrecognized.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    version = data.get("version", 0)
    if version != 1:
        raise ValueError(
            f"Unsupported flight log version: {version}. Expected 1."
        )

    drones: dict[str, list[TelemetrySnapshot]] = {}
    for drone_id, snapshots in data.get("drones", {}).items():
        drones[drone_id] = [
            TelemetrySnapshot(
                t=s["t"],
                lat=s["lat"],
                lon=s["lon"],
                alt=s["alt"],
                heading=s["heading"],
                battery_pct=s["battery_pct"],
                speed_ms=s.get("speed_ms", 0.0),
                health_score=s.get("health_score", 100.0),
                gps_sats=s.get("gps_sats", 0),
                status=s.get("status", "unknown"),
            )
            for s in snapshots
        ]

    return FlightLog(
        version=1,
        start_time=data.get("start_time", 0.0),
        end_time=data.get("end_time", 0.0),
        drones=drones,
        metadata=data.get("metadata", {}),
    )
