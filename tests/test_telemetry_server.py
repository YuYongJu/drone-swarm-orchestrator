"""Tests for the WebSocket telemetry server (drone_swarm.telemetry_server).

Tests the server behavior lifecycle and message format without requiring
actual WebSocket connections (mocked where needed).
"""

import json

import pytest

from drone_swarm.drone import Drone, DroneRole, DroneStatus
from drone_swarm.swarm import SwarmOrchestrator
from drone_swarm.telemetry_server import TelemetryServer, _drone_to_dict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(
    drone_id: str = "alpha", lat: float = 35.363, lon: float = -117.669,
) -> Drone:
    d = Drone(drone_id=drone_id, connection_string="udp:127.0.0.1:14550",
              role=DroneRole.RECON)
    d.lat, d.lon, d.alt = lat, lon, 10.0
    d.heading = 90.0
    d.battery_pct = 95.0
    d.status = DroneStatus.AIRBORNE
    d.health_score = 88.0
    d.gps_satellite_count = 12
    return d


# ---------------------------------------------------------------------------
# _drone_to_dict serialization
# ---------------------------------------------------------------------------

class TestDroneToDict:
    def test_contains_required_fields(self):
        d = _make_drone()
        result = _drone_to_dict(d)

        assert result["lat"] == pytest.approx(35.363)
        assert result["lon"] == pytest.approx(-117.669)
        assert result["alt"] == pytest.approx(10.0)
        assert result["heading"] == pytest.approx(90.0)
        assert result["battery_pct"] == pytest.approx(95.0)
        assert result["status"] == "airborne"
        assert result["health_score"] == pytest.approx(88.0)
        assert result["gps_sats"] == 12

    def test_is_json_serializable(self):
        d = _make_drone()
        result = _drone_to_dict(d)
        # Should not raise
        json.dumps(result)


# ---------------------------------------------------------------------------
# TelemetryServer behavior
# ---------------------------------------------------------------------------

class TestTelemetryServerConfig:
    def test_default_config(self):
        server = TelemetryServer()
        assert server.host == "127.0.0.1"
        assert server.port == 8765
        assert server.broadcast_interval == pytest.approx(0.2)
        assert server.client_count == 0

    def test_custom_config(self):
        server = TelemetryServer(host="0.0.0.0", port=9000, broadcast_hz=10.0)
        assert server.host == "0.0.0.0"
        assert server.port == 9000
        assert server.broadcast_interval == pytest.approx(0.1)


class TestTelemetryServerSetup:
    @pytest.mark.asyncio
    async def test_setup_requires_websockets(self):
        """Setup raises ImportError if websockets is not installed."""
        import unittest.mock as mock

        server = TelemetryServer()
        swarm = SwarmOrchestrator()

        # Mock the import to fail
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "websockets":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="websockets is required"):
                await server.setup(swarm)


class TestTelemetryServerMessage:
    def test_build_message_format(self):
        drones = {"alpha": _make_drone()}
        msg = TelemetryServer._build_message(drones)
        data = json.loads(msg)

        assert data["type"] == "telemetry"
        assert "timestamp" in data
        assert "alpha" in data["drones"]
        assert data["drones"]["alpha"]["status"] == "airborne"

    def test_build_message_multiple_drones(self):
        drones = {
            "alpha": _make_drone("alpha"),
            "bravo": _make_drone("bravo", lat=35.364, lon=-117.670),
        }
        msg = TelemetryServer._build_message(drones)
        data = json.loads(msg)

        assert len(data["drones"]) == 2
        assert "alpha" in data["drones"]
        assert "bravo" in data["drones"]

    def test_build_message_empty_drones(self):
        msg = TelemetryServer._build_message({})
        data = json.loads(msg)

        assert data["type"] == "telemetry"
        assert data["drones"] == {}


class TestTelemetryServerTick:
    @pytest.mark.asyncio
    async def test_tick_without_clients_is_noop(self):
        """on_tick does nothing when no clients are connected."""
        server = TelemetryServer()
        swarm = SwarmOrchestrator()
        drones = {"alpha": _make_drone()}

        # Should not raise
        await server.on_tick(swarm, drones)
        assert server._latest_drones is drones
