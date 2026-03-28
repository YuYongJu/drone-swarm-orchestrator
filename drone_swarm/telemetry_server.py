"""
WebSocket telemetry server for real-time external consumers.

Streams live drone telemetry as JSON messages over WebSocket connections.
External dashboards, mobile apps, or analytics tools connect and receive
position/battery/health updates at configurable rates.

Uses ``asyncio`` and the stdlib ``websockets``-compatible protocol via
the lightweight ``websockets`` package.

Usage::

    from drone_swarm.telemetry_server import TelemetryServer

    server = TelemetryServer(port=8765, broadcast_hz=5.0)
    swarm.add_behavior(server)  # starts WebSocket server
    # External clients connect to ws://localhost:8765

Wire format (JSON per message)::

    {
        "type": "telemetry",
        "timestamp": 1711612800.0,
        "drones": {
            "alpha": {
                "lat": 35.363261, "lon": -117.669056, "alt": 10.0,
                "heading": 90.0, "battery_pct": 95.0, "status": "airborne",
                "health_score": 90.0, "gps_sats": 12
            }
        }
    }
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from .behavior import Behavior

if TYPE_CHECKING:
    from .drone import Drone
    from .swarm import SwarmOrchestrator

logger = logging.getLogger("drone_swarm.telemetry_server")


def _drone_to_dict(drone: Drone) -> dict[str, Any]:
    """Serialize a drone's telemetry to a JSON-friendly dict."""
    return {
        "lat": drone.lat,
        "lon": drone.lon,
        "alt": drone.alt,
        "heading": drone.heading,
        "battery_pct": drone.battery_pct,
        "status": drone.status.value,
        "health_score": drone.health_score,
        "gps_sats": drone.gps_satellite_count,
        "roll": drone.roll,
        "pitch": drone.pitch,
        "yaw": drone.yaw,
        "current_a": drone.current_a,
        "voltage": drone.voltage,
    }


class TelemetryServer(Behavior):
    """WebSocket server that broadcasts live telemetry to connected clients.

    Runs as a behavior plugin — the telemetry loop drives the broadcast.
    Clients connect via ``ws://host:port`` and receive JSON telemetry at
    the configured rate.

    Args:
        host: Bind address (default ``"127.0.0.1"`` — localhost only).
        port: WebSocket port (default ``8765``).
        broadcast_hz: Maximum broadcast rate in Hz (default 5.0 = every 200ms).

    Requires the ``websockets`` package::

        pip install websockets
    """

    name = "telemetry_server"
    priority = -20  # Runs after safety and logging behaviors

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        broadcast_hz: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.broadcast_interval = 1.0 / broadcast_hz
        self._clients: set[Any] = set()
        self._server: Any = None
        self._server_task: asyncio.Task | None = None
        self._last_broadcast: float = 0.0
        self._latest_drones: dict[str, Drone] = {}

    async def setup(self, swarm: SwarmOrchestrator) -> None:
        try:
            import websockets  # noqa: F401
        except ImportError:
            raise ImportError(
                "websockets is required for the telemetry server. "
                "Install with: pip install websockets"
            ) from None

        self._server_task = asyncio.create_task(self._start_server())
        logger.info(
            "Telemetry server starting on ws://%s:%d (%.1f Hz)",
            self.host, self.port, 1.0 / self.broadcast_interval,
        )

    async def _start_server(self) -> None:
        import websockets

        async def handler(websocket: Any) -> None:
            self._clients.add(websocket)
            remote = websocket.remote_address
            logger.info("Client connected: %s", remote)
            try:
                # Send current state immediately on connect
                if self._latest_drones:
                    msg = self._build_message(self._latest_drones)
                    await websocket.send(msg)
                # Keep connection alive — client can send pings
                async for _ in websocket:
                    pass  # We don't expect client messages
            except websockets.ConnectionClosed:
                pass
            finally:
                self._clients.discard(websocket)
                logger.info("Client disconnected: %s", remote)

        self._server = await websockets.serve(
            handler, self.host, self.port,
        )

    async def on_tick(
        self,
        swarm: SwarmOrchestrator,
        drones: dict[str, Drone],
    ) -> None:
        self._latest_drones = drones

        now = time.time()
        if now - self._last_broadcast < self.broadcast_interval:
            return
        self._last_broadcast = now

        if not self._clients:
            return

        msg = self._build_message(drones)
        # Broadcast to all connected clients
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(msg)
            except Exception:
                disconnected.add(client)
        self._clients -= disconnected

    async def teardown(self, swarm: SwarmOrchestrator) -> None:
        # Close all client connections
        for client in list(self._clients):
            with contextlib.suppress(Exception):
                await client.close()
        self._clients.clear()

        # Stop the server
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._server_task is not None:
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
            self._server_task = None

        logger.info("Telemetry server stopped")

    @staticmethod
    def _build_message(drones: dict[str, Drone]) -> str:
        """Build a JSON telemetry broadcast message."""
        return json.dumps({
            "type": "telemetry",
            "timestamp": time.time(),
            "drones": {
                drone_id: _drone_to_dict(drone)
                for drone_id, drone in drones.items()
            },
        })

    @property
    def client_count(self) -> int:
        """Number of currently connected WebSocket clients."""
        return len(self._clients)
