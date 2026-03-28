"""Tests for the flight logging system (drone_swarm.flight_log).

Covers recording, export, import, ring buffer, and roundtrip verification.
"""

import json

import pytest

from drone_swarm.drone import Drone, DroneRole, DroneStatus
from drone_swarm.flight_log import FlightLog, FlightLogger, TelemetrySnapshot, load_flight_log
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drones() -> dict[str, Drone]:
    drones = {}
    for i, name in enumerate(["alpha", "bravo"]):
        d = Drone(
            drone_id=name,
            connection_string=f"udp:127.0.0.1:{14550 + i * 10}",
            role=DroneRole.RECON,
        )
        d.lat = 35.363261 + i * 0.001
        d.lon = -117.669056
        d.alt = 10.0 + i * 5
        d.heading = 90.0
        d.battery_pct = 95.0 - i * 10
        d.status = DroneStatus.AIRBORNE
        d.health_score = 90.0
        d.gps_satellite_count = 12
        drones[name] = d
    return drones


# ---------------------------------------------------------------------------
# FlightLogger behavior
# ---------------------------------------------------------------------------

class TestFlightLogger:
    @pytest.mark.asyncio
    async def test_setup_clears_buffers(self):
        fl = FlightLogger()
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)
        assert fl.snapshot_count() == 0

    @pytest.mark.asyncio
    async def test_tick_records_snapshots(self):
        fl = FlightLogger(interval_s=0.0)  # record every tick
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        drones = _make_drones()
        await fl.on_tick(swarm, drones)

        assert fl.snapshot_count() == 2
        assert fl.snapshot_count("alpha") == 1
        assert fl.snapshot_count("bravo") == 1

    @pytest.mark.asyncio
    async def test_interval_throttling(self):
        fl = FlightLogger(interval_s=999.0)  # will not trigger twice
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        drones = _make_drones()
        await fl.on_tick(swarm, drones)
        await fl.on_tick(swarm, drones)  # should be skipped

        assert fl.snapshot_count() == 2  # only first tick

    @pytest.mark.asyncio
    async def test_ring_buffer_limit(self):
        fl = FlightLogger(interval_s=0.0, max_snapshots_per_drone=3)
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        drones = {"alpha": _make_drones()["alpha"]}
        for _ in range(10):
            fl._last_record_time = 0  # force recording
            await fl.on_tick(swarm, drones)

        assert fl.snapshot_count("alpha") == 3  # capped at 3

    @pytest.mark.asyncio
    async def test_latest_returns_most_recent(self):
        fl = FlightLogger(interval_s=0.0)
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        drones = _make_drones()
        await fl.on_tick(swarm, drones)

        snap = fl.latest("alpha")
        assert snap is not None
        assert snap.lat == pytest.approx(35.363261)
        assert snap.status == "airborne"

    @pytest.mark.asyncio
    async def test_latest_returns_none_for_unknown(self):
        fl = FlightLogger()
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)
        assert fl.latest("nonexistent") is None

    @pytest.mark.asyncio
    async def test_to_flight_log(self):
        fl = FlightLogger(interval_s=0.0, metadata={"mission": "test_001"})
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        await fl.on_tick(swarm, _make_drones())
        log = fl.to_flight_log()

        assert isinstance(log, FlightLog)
        assert log.version == 1
        assert log.start_time > 0
        assert "alpha" in log.drones
        assert log.metadata["mission"] == "test_001"


# ---------------------------------------------------------------------------
# JSON export and import
# ---------------------------------------------------------------------------

class TestFlightLogExport:
    @pytest.mark.asyncio
    async def test_export_creates_file(self, tmp_path):
        fl = FlightLogger(interval_s=0.0)
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)
        await fl.on_tick(swarm, _make_drones())

        out = fl.export_json(tmp_path / "test.json")
        assert out.exists()

    @pytest.mark.asyncio
    async def test_export_valid_json(self, tmp_path):
        fl = FlightLogger(interval_s=0.0)
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)
        await fl.on_tick(swarm, _make_drones())

        path = tmp_path / "test.json"
        fl.export_json(path)

        data = json.loads(path.read_text())
        assert data["version"] == 1
        assert "alpha" in data["drones"]
        assert len(data["drones"]["alpha"]) == 1

    @pytest.mark.asyncio
    async def test_roundtrip(self, tmp_path):
        """Export then load — all data should survive the roundtrip."""
        fl = FlightLogger(interval_s=0.0, metadata={"pilot": "test"})
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)
        await fl.on_tick(swarm, _make_drones())

        path = tmp_path / "roundtrip.json"
        fl.export_json(path)

        loaded = load_flight_log(path)
        assert loaded.version == 1
        assert loaded.metadata["pilot"] == "test"
        assert "alpha" in loaded.drones
        assert "bravo" in loaded.drones

        snap = loaded.drones["alpha"][0]
        assert snap.lat == pytest.approx(35.363261)
        assert snap.battery_pct == pytest.approx(95.0)
        assert snap.status == "airborne"

    @pytest.mark.asyncio
    async def test_empty_log_export(self, tmp_path):
        fl = FlightLogger()
        swarm = SwarmOrchestrator()
        await fl.setup(swarm)

        path = tmp_path / "empty.json"
        fl.export_json(path)

        loaded = load_flight_log(path)
        assert loaded.drones == {}

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_flight_log(tmp_path / "nope.json")

    def test_load_bad_version_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"version": 99}))
        with pytest.raises(ValueError, match="Unsupported flight log version"):
            load_flight_log(path)


# ---------------------------------------------------------------------------
# TelemetrySnapshot
# ---------------------------------------------------------------------------

class TestTelemetrySnapshot:
    def test_fields(self):
        s = TelemetrySnapshot(
            t=1000.0, lat=35.0, lon=-117.0, alt=10.0,
            heading=90.0, battery_pct=80.0,
        )
        assert s.t == 1000.0
        assert s.speed_ms == 0.0  # default
        assert s.status == "unknown"  # default
