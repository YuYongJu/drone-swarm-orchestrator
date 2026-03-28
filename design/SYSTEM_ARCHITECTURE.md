---
title: System Architecture
type: design
status: active
created: 2026-03-26
updated: 2026-03-27
tags: [drone-swarm, architecture, sdk, platform]
---

# Drone Swarm Orchestrator -- System Architecture

**Version:** 2.0
**Last Updated:** 2026-03-27
**Status:** Technical Blueprint (Updated for SDK Platform Pivot)

---

## Table of Contents

0. [Platform Architecture (SDK Model)](#0-platform-architecture-sdk-model)
1. [System Overview](#1-system-overview)
2. [Python Backend Architecture](#2-python-backend-architecture)
3. [Next.js Frontend Architecture](#3-nextjs-frontend-architecture)
4. [Communication Protocol (Backend <-> Frontend)](#4-communication-protocol-backend--frontend)
5. [Data Storage](#5-data-storage)
6. [Formation Maintenance Algorithm](#6-formation-maintenance-algorithm)
7. [Dynamic Replanning Algorithm](#7-dynamic-replanning-algorithm)
8. [Security Architecture](#8-security-architecture)
9. [Failure Modes & Recovery](#9-failure-modes--recovery)
10. [Scalability Path](#10-scalability-path)
11. [Payload Compatibility System](#11-payload-compatibility-system)

---

## 0. Platform Architecture (SDK Model)

> **Strategic Context:** As of 2026-03-27, DSO is repositioned from a military end-user
> product to an open-source developer platform -- "Stripe for Drones." The SDK is the
> product; the cloud services are the revenue; defense is one vertical, not the only one.

### Platform Layer Diagram

```
 DEVELOPER APPLICATIONS (built by third parties)
 ═══════════════════════════════════════════════════════════════════

 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐
 │ Agriculture  │  │ Search &     │  │ Infrastructure│  │ Defense /       │
 │ Spraying App │  │ Rescue App   │  │ Inspection App│  │ Enterprise App  │
 └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬─────────┘
        │                 │                  │                   │
        └────────────┬────┴──────────────────┴───────┬──────────┘
                     │                               │
                     ▼                               ▼
 SDK LAYER (open source, pip install drone-swarm)
 ═══════════════════════════════════════════════════════════════════

 ┌─────────────────────────────────────────────────────────────────┐
 │                    drone-swarm SDK (Python)                      │
 │                                                                  │
 │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
 │  │   Swarm   │  │ Missions  │  │  Safety   │  │  Simulation │  │
 │  │ Orchestr. │  │ (V, grid, │  │ (preflight│  │  (SITL      │  │
 │  │           │  │  orbit,   │  │  failsafe,│  │   harness)  │  │
 │  │ connect() │  │  sweep,   │  │  e-stop)  │  │             │  │
 │  │ takeoff() │  │  custom)  │  │           │  │ simulate()  │  │
 │  │ formation│  │           │  │           │  │             │  │
 │  │ rtl()    │  │           │  │           │  │             │  │
 │  └─────┬─────┘  └───────────┘  └───────────┘  └─────────────┘  │
 │        │                                                         │
 │  ┌─────┴─────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
 │  │ Telemetry │  │  Config   │  │  Plugin   │  │  Autopilot  │  │
 │  │ Aggregator│  │  (YAML)   │  │  Hooks    │  │  Abstraction│  │
 │  │           │  │           │  │  (new)    │  │  (MAVLink)  │  │
 │  └───────────┘  └───────────┘  └───────────┘  └──────┬──────┘  │
 └───────────────────────────────────────────────────────┼─────────┘
                                                         │
 CLOUD LAYER (paid service — THIS IS THE REVENUE)        │
 ═══════════════════════════════════════════════════════  │
                                                         │
 ┌───────────────────────────────────────────────────┐   │
 │              DSO Cloud (Future)                    │   │
 │                                                    │   │
 │  ┌────────────┐  ┌─────────────┐  ┌────────────┐ │   │
 │  │ Telemetry  │  │   Mission   │  │    OTA     │ │   │
 │  │ Dashboard  │  │   Logging   │  │   Updates  │ │   │
 │  │ & Replay   │  │   & Replay  │  │            │ │   │
 │  └────────────┘  └─────────────┘  └────────────┘ │   │
 │                                                    │   │
 │  ┌────────────┐  ┌─────────────┐  ┌────────────┐ │   │
 │  │   Fleet    │  │ Marketplace │  │  Compliance│ │   │
 │  │  Analytics │  │ (algorithms,│  │  (ITAR,    │ │   │
 │  │            │  │  plugins)   │  │   FIPS)    │ │   │
 │  └────────────┘  └─────────────┘  └────────────┘ │   │
 └───────────────────────────────────────────────────┘   │
                                                         │
 AUTOPILOT LAYER (existing open source)                  │
 ═══════════════════════════════════════════════════════  │
                                                         │
 ┌───────────────────────────────────────────────────┐   │
 │  ArduPilot  ◄──── MAVLink v2 ────────────────────┼───┘
 │  PX4 (future)                                     │
 └──────────────────────┬────────────────────────────┘
                        │
 HARDWARE LAYER (any)   │
 ═══════════════════════╧══════════════════════════════

 ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
 │  F450    │  │  5" FPV  │  │  DJI     │  │  Custom      │
 │  ($15)   │  │  ($200)  │  │  ($$$$)  │  │  Airframe    │
 └──────────┘  └──────────┘  └──────────┘  └──────────────┘
```

### SDK Package Structure

```
drone_swarm/                  # pip install drone-swarm
├── __init__.py              # Public API: Swarm, Drone, DroneRole, Waypoint
├── swarm.py                 # SwarmOrchestrator — core state machine + coordination
├── drone.py                 # Drone, DroneRole, DroneStatus, DroneCapabilities, Waypoint
├── missions.py              # v_formation, line_formation, area_sweep, orbit_point
├── safety.py                # run_preflight_checks, emergency_land, emergency_kill
├── telemetry.py             # TelemetryReader — async MAVLink message processing
├── config.py                # SwarmConfig — YAML/dict config, replaces hardcoded constants
├── simulation.py            # SimulationHarness — spawn SITL instances programmatically
└── _version.py              # Semantic version (0.1.0)
```

### Business Model Tiers

| Tier | What's Included | Price | Target |
|------|----------------|-------|--------|
| **Free (AGPL)** | Full SDK, simulate up to N drones, community support | $0 | Hobbyists, students, researchers |
| **Cloud** | Hosted telemetry, mission logging, fleet analytics, OTA | $0.01/drone-min | Startups, small commercial teams |
| **Enterprise** | ITAR distribution, encrypted C2, FIPS, audit trails, SLA | $50-200K/year | Defense contractors, utilities, agencies |
| **Marketplace** | Third-party algorithms, hardware certs, training courses | Revenue share | Ecosystem partners |

### Competitive Positioning

| | DSO | Swarmer | Auterion | Shield AI |
|---|---|---|---|---|
| **Type** | Developer SDK | End-user product | OS + hardware | Proprietary AI |
| **Open source** | Yes (AGPL) | No | Partially (PX4) | No |
| **Hardware req.** | Any MAVLink | Any | Skynode only | V-BAT only |
| **Autopilot** | ArduPilot (+ PX4 planned) | Unknown | PX4 only | Proprietary |
| **Price** | Free SDK + paid cloud | Per-unit licensing | Opaque enterprise | Opaque enterprise |
| **Target** | Developers | Military | Military/Enterprise | Military |

---

## 1. System Overview

### High-Level Architecture Diagram

```
 AIRSPACE                         GROUND
 ════════════════════════         ══════════════════════════════════════════════════════

 ┌──────────┐                    ┌──────────────────────────────────────────────────┐
 │  Drone 1 │◄──── SiK Radio ──►│                                                  │
 │ (alpha)  │      433/915 MHz   │            PYTHON BACKEND                        │
 └──────────┘                    │                                                  │
                                 │  ┌──────────────────────────────────────────┐    │
 ┌──────────┐                    │  │         SwarmOrchestrator (swarm.py)      │    │
 │  Drone 2 │◄──── SiK Radio ──►│  │                                          │    │
 │ (bravo)  │      433/915 MHz   │  │  ┌─────────────┐  ┌──────────────────┐  │    │
 └──────────┘                    │  │  │   Fleet      │  │  Mission         │  │    │
                                 │  │  │   Registry   │  │  Planner         │  │    │
 ┌──────────┐                    │  │  └─────────────┘  └──────────────────┘  │    │
 │  Drone 3 │◄──── SiK Radio ──►│  │                                          │    │
 │ (charlie)│      433/915 MHz   │  │  ┌─────────────┐  ┌──────────────────┐  │    │
 └──────────┘                    │  │  │  Telemetry   │  │  Command         │  │    │
                                 │  │  │  Aggregator  │  │  Dispatcher      │  │    │
      │                          │  │  └──────┬──────┘  └────────▲─────────┘  │    │
      │  MAVLink v2              │  │         │                  │             │    │
      │  (serial/UDP)            │  │  ┌──────┴──────┐  ┌───────┴──────────┐  │    │
      │                          │  │  │  Failsafe   │  │  Formation       │  │    │
      ▼                          │  │  │  Manager    │  │  Controller      │  │    │
 ┌──────────┐                    │  │  └─────────────┘  └──────────────────┘  │    │
 │   USB    │                    │  │                                          │    │
 │   Hub    │◄── USB serial ────►│  │  ┌─────────────┐  ┌──────────────────┐  │    │
 │ (powered)│                    │  │  │  Task        │  │  Geofence        │  │    │
 └──────────┘                    │  │  │  Allocator   │  │  Manager         │  │    │
                                 │  │  └─────────────┘  └──────────────────┘  │    │
                                 │  │                                          │    │
                                 │  │  ┌─────────────┐  ┌──────────────────┐  │    │
                                 │  │  │  Mission     │  │  Mesh Bridge     │  │    │
                                 │  │  │  Logger      │  │  (future)        │  │    │
                                 │  │  └─────────────┘  └──────────────────┘  │    │
                                 │  └──────────────────────────────────────────┘    │
                                 │                                                  │
                                 │  ┌──────────────┐    ┌──────────────────────┐   │
                                 │  │  FastAPI      │    │  WebSocket Server    │   │
                                 │  │  REST API     │    │  (Tornado/FastAPI)   │   │
                                 │  │  :8000        │    │  :8001               │   │
                                 │  └──────┬───────┘    └──────────┬───────────┘   │
                                 └─────────┼───────────────────────┼────────────────┘
                                           │                       │
                                      HTTP/REST              WebSocket
                                      (commands)          (telemetry stream)
                                           │                       │
                                 ┌─────────┴───────────────────────┴────────────────┐
                                 │                                                  │
                                 │            NEXT.JS FRONTEND                      │
                                 │            Ground Station UI                     │
                                 │            :3000                                 │
                                 │                                                  │
                                 │  ┌──────────────────────────────────────────┐    │
                                 │  │           Zustand State Store             │    │
                                 │  │  ┌────────┐ ┌─────────┐ ┌───────────┐   │    │
                                 │  │  │ Drone  │ │ Mission │ │    UI     │   │    │
                                 │  │  │ State  │ │  State  │ │   State   │   │    │
                                 │  │  └────────┘ └─────────┘ └───────────┘   │    │
                                 │  └──────────────────────────────────────────┘    │
                                 │                                                  │
                                 │  ┌──────────┐ ┌──────────┐ ┌───────────────┐    │
                                 │  │  Map     │ │ Mission  │ │  Fleet        │    │
                                 │  │  View    │ │ Control  │ │  Manager      │    │
                                 │  │ (Leaflet)│ │  Panel   │ │  Panel        │    │
                                 │  └──────────┘ └──────────┘ └───────────────┘    │
                                 │                                                  │
                                 │  ┌──────────┐ ┌──────────┐ ┌───────────────┐    │
                                 │  │ Telemetry│ │  Alert   │ │  Geofence     │    │
                                 │  │  Charts  │ │  Banner  │ │  Editor       │    │
                                 │  └──────────┘ └──────────┘ └───────────────┘    │
                                 │                                                  │
                                 └──────────────────────────────────────────────────┘
                                                       │
                                                    Browser
                                                   (Operator)
```

### Data Flow Summary

```
Drone → MAVLink → SiK Radio → USB → Python Backend → WebSocket → Zustand → React → UI
User → UI → REST API → Python Backend → MAVLink → SiK Radio → Drone
```

### Component Inventory

| Component             | Language/Framework | Role                                      |
|-----------------------|-------------------|-------------------------------------------|
| SwarmOrchestrator     | Python 3.11+      | Core coordination, MAVLink, state machine  |
| Telemetry Aggregator  | Python            | Normalize + publish drone telemetry        |
| Command Dispatcher    | Python / FastAPI  | Validate + route operator commands         |
| Failsafe Manager      | Python            | Monitor hazards, trigger emergency actions |
| Mission Logger        | Python / SQLite   | Persist telemetry + events for replay      |
| Formation Controller  | Python            | PID-based formation station-keeping        |
| Task Allocator        | Python            | Optimal drone-to-role assignment           |
| Geofence Manager      | Python            | Boundary enforcement, point-in-polygon     |
| Mesh Bridge (future)  | Python / ESP-IDF  | SiK-to-ESP32 mesh gateway                 |
| Ground Station UI     | Next.js 14+ / React | Operator interface, map, controls        |
| Map View              | Leaflet / React-Leaflet | Real-time drone positions, paths      |
| State Store           | Zustand           | Client-side state management               |

---

## 2. Python Backend Architecture

### 2.1 Module Breakdown

#### `swarm.py` -- Core Orchestrator (existing, evolving)

The existing `SwarmOrchestrator` class is the foundation. It currently handles:
- Drone registration (in-memory and from fleet JSON files)
- MAVLink connections via pymavlink (serial and UDP)
- Background telemetry coroutine (10Hz, async)
- Flight commands: arm, takeoff, goto, RTL, land
- Mission execution (one asyncio task per active mission)
- Basic replanning on drone loss (greedy nearest-neighbor reassignment)
- Role validation against hardware capabilities
- Auto-role assignment based on capability classes (A/B/C/D)

**Evolution plan:**

The orchestrator will be refactored to become a thinner coordination layer that delegates to specialized modules. Current responsibilities will be extracted as follows:

```
Current swarm.py                    Extracted to
──────────────────────────────      ──────────────────────────────
_telemetry_loop()                → telemetry_aggregator.py
_read_telemetry()                → telemetry_aggregator.py
goto(), arm(), takeoff(), etc.   → command_dispatcher.py (MAVLink send)
replan_on_loss()                 → task_allocator.py (improved algorithm)
Battery/heartbeat checks         → failsafe_manager.py
(new) Formation PID              → formation_controller.py
(new) Logging                    → mission_logger.py
(new) Geofence enforcement       → geofence_manager.py
```

Post-refactor, `swarm.py` retains:
- The `Drone`, `DroneRole`, `DroneStatus`, `Waypoint`, `DroneCapabilities` data classes
- The `SwarmOrchestrator` class as the top-level coordinator
- Lifecycle management: `connect_all()`, `shutdown()`
- Module initialization and dependency wiring
- The public API surface that other modules call into

```python
# Post-refactor swarm.py (structural sketch)
class SwarmOrchestrator:
    def __init__(self):
        self.drones: dict[str, Drone] = {}
        self.telemetry = TelemetryAggregator(self)
        self.commands = CommandDispatcher(self)
        self.failsafe = FailsafeManager(self)
        self.logger = MissionLogger()
        self.formation = FormationController(self)
        self.allocator = TaskAllocator(self)
        self.geofence = GeofenceManager()

    def connect_all(self):
        # Connect MAVLink, start telemetry, start failsafe monitor
        ...

    def shutdown(self):
        # Graceful shutdown: RTL all, close connections, flush logs
        ...
```

#### `telemetry_aggregator.py` -- Telemetry Collection & Publishing

Extracts the telemetry loop from `swarm.py` and adds normalization, buffering, and WebSocket publishing.

```python
class TelemetryAggregator:
    """
    Reads MAVLink telemetry from all connected drones at 10Hz,
    normalizes into a common format, updates drone state objects,
    and publishes to all connected WebSocket clients.
    """

    POLL_RATE_HZ = 10            # Telemetry read rate
    SNAPSHOT_RATE_HZ = 1         # Full swarm snapshot rate
    BUFFER_SIZE = 100            # Ring buffer per drone for smoothing

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator
        self.ws_clients: list[WebSocket] = []
        self._running = False

    async def start(self):
        """Start the telemetry polling coroutine as an asyncio task."""
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        loop = asyncio.get_running_loop()
        snapshot_counter = 0
        while self._running:
            for drone in self.orchestrator.drones.values():
                if drone.connection is None:
                    continue
                # Blocking pymavlink I/O runs in executor to avoid stalling the event loop
                await loop.run_in_executor(None, self._read_and_normalize, drone)
                self._publish_telemetry_update(drone)

            snapshot_counter += 1
            if snapshot_counter >= self.POLL_RATE_HZ:  # Every 1 second
                self._publish_swarm_snapshot()
                snapshot_counter = 0

            await asyncio.sleep(1.0 / self.POLL_RATE_HZ)

    def _read_and_normalize(self, drone: Drone):
        """Read all available MAVLink messages, update drone state."""
        conn = drone.connection
        while True:
            msg = conn.recv_match(blocking=False)
            if msg is None:
                break
            msg_type = msg.get_type()
            if msg_type == "HEARTBEAT":
                drone.last_heartbeat = time.time()
            elif msg_type == "GLOBAL_POSITION_INT":
                drone.lat = msg.lat / 1e7
                drone.lon = msg.lon / 1e7
                drone.alt = msg.relative_alt / 1000.0
                drone.heading = msg.hdg / 100.0
            elif msg_type == "SYS_STATUS":
                if msg.battery_remaining >= 0:
                    drone.battery_pct = msg.battery_remaining
            elif msg_type == "GPS_RAW_INT":
                drone.gps_fix = msg.fix_type
                drone.satellites = msg.satellites_visible
            elif msg_type == "VFR_HUD":
                drone.groundspeed = msg.groundspeed
                drone.airspeed = msg.airspeed
                drone.climb_rate = msg.climb

    def _publish_telemetry_update(self, drone: Drone):
        """Send per-drone telemetry to all WebSocket clients."""
        msg = {
            "type": "telemetry_update",
            "drone_id": drone.drone_id,
            "timestamp": time.time(),
            "lat": drone.lat,
            "lon": drone.lon,
            "alt": drone.alt,
            "heading": drone.heading,
            "battery_pct": drone.battery_pct,
            "status": drone.status.value,
            "groundspeed": getattr(drone, "groundspeed", 0.0),
        }
        self._broadcast_ws(msg)

    def _publish_swarm_snapshot(self):
        """Send full swarm state to all WebSocket clients."""
        msg = {
            "type": "swarm_status",
            "timestamp": time.time(),
            "drones": {
                d.drone_id: {
                    "role": d.role.value,
                    "status": d.status.value,
                    "lat": d.lat, "lon": d.lon, "alt": d.alt,
                    "heading": d.heading,
                    "battery_pct": d.battery_pct,
                    "mission_progress": self._mission_progress(d),
                }
                for d in self.orchestrator.drones.values()
            },
        }
        self._broadcast_ws(msg)
```

**Key design decisions:**
- Drain all available MAVLink messages per drone per tick (non-blocking recv loop) to prevent serial buffer overflow
- Per-drone telemetry at 10Hz base rate; adaptive rates per client (10Hz selected, 2Hz active, 0.5Hz idle)
- Per-client async message queue (max depth 100, drop oldest) prevents slow clients from causing backpressure
- Ring buffer per drone enables smoothing/interpolation on the frontend

#### `command_dispatcher.py` -- Command Routing & Validation

```python
class CommandDispatcher:
    """
    Receives commands from the REST API, validates them against
    current swarm state, and translates to MAVLink commands.
    """

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator

    def takeoff(self, drone_ids: list[str] | None, altitude: float = 10.0) -> dict:
        """Takeoff specified drones or all. Returns result per drone."""
        targets = drone_ids or list(self.orchestrator.drones.keys())
        results = {}
        for did in targets:
            drone = self.orchestrator.drones.get(did)
            if drone is None:
                results[did] = {"ok": False, "error": "unknown_drone"}
                continue
            if drone.status not in (DroneStatus.CONNECTED, DroneStatus.ARMED):
                results[did] = {"ok": False, "error": f"invalid_state:{drone.status.value}"}
                continue
            if not self.orchestrator.geofence.check_altitude(altitude):
                results[did] = {"ok": False, "error": "altitude_exceeds_geofence"}
                continue
            try:
                self._mavlink_takeoff(drone, altitude)
                results[did] = {"ok": True}
            except Exception as e:
                results[did] = {"ok": False, "error": str(e)}
        return results

    def goto(self, drone_id: str, lat: float, lon: float, alt: float) -> dict:
        """Send a single drone to a waypoint."""
        drone = self.orchestrator.drones.get(drone_id)
        if drone is None:
            return {"ok": False, "error": "unknown_drone"}
        if drone.status != DroneStatus.AIRBORNE:
            return {"ok": False, "error": f"not_airborne:{drone.status.value}"}
        if not self.orchestrator.geofence.contains(lat, lon):
            return {"ok": False, "error": "waypoint_outside_geofence"}
        self._mavlink_goto(drone, Waypoint(lat, lon, alt))
        return {"ok": True}

    def emergency_stop(self) -> dict:
        """Immediate motor kill on all drones. USE WITH EXTREME CAUTION."""
        for drone in self.orchestrator.drones.values():
            if drone.connection:
                conn = drone.connection
                # MAV_CMD_COMPONENT_ARM_DISARM with param2=21196 = force disarm
                conn.mav.command_long_send(
                    conn.target_system, conn.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0, 0, 21196, 0, 0, 0, 0, 0,
                )
        return {"ok": True, "warning": "ALL MOTORS KILLED"}

    # ... rtl, land, assign_mission, execute_mission, change_role ...
```

**Validation pipeline for every command:**
1. Drone exists in registry
2. Drone is in a valid state for the command
3. Geofence constraints are satisfied
4. Hardware capabilities match (e.g., recon role requires camera)
5. Failsafe conditions are not blocking (e.g., battery too low to take off)
6. Command is translated to MAVLink and sent
7. Result is returned to the caller (REST API) with success/failure detail

#### Async Command Queue

All commands from the REST API flow through an async command queue rather than being dispatched directly to MAVLink. This decouples the API response time from radio link latency and provides reliable delivery with acknowledgment tracking.

```python
class CommandQueue:
    """
    Async command queue with ACK tracking and retry logic.
    Commands are enqueued by the REST API and processed by a
    dedicated MAVLink sender coroutine.
    """

    def __init__(self, orchestrator):
        self.queue = asyncio.Queue()
        self.pending: dict[str, CommandEntry] = {}  # command_id -> entry
        self.max_retries = 3
        self.retry_backoff_ms = 500

    async def enqueue(self, command: dict) -> str:
        """Add command to queue. Returns command_id immediately."""
        command_id = str(uuid.uuid4())
        entry = CommandEntry(
            command_id=command_id,
            command=command,
            status="queued",
            retries=0,
            created_at=time.time(),
        )
        self.pending[command_id] = entry
        await self.queue.put(entry)
        return command_id

    async def process_loop(self):
        """Main sender loop. Sends commands and waits for MAVLink ACK."""
        while True:
            entry = await self.queue.get()
            success = await self._send_and_wait_ack(entry)
            if not success and entry.retries < self.max_retries:
                entry.retries += 1
                entry.status = "retrying"
                await asyncio.sleep(self.retry_backoff_ms * entry.retries / 1000)
                await self.queue.put(entry)
            elif not success:
                entry.status = "failed"
                await self._publish_status(entry)  # WebSocket alert
            else:
                entry.status = "acked"
                await self._publish_status(entry)  # WebSocket confirmation
```

**Command lifecycle:**
1. REST API handler calls `command_queue.enqueue(command)` and receives a `command_id`
2. API returns `{"ok": true, "command_id": "<uuid>"}` immediately to the client
3. The MAVLink sender coroutine dequeues the command, sends it, and waits for `COMMAND_ACK`
4. ACK/NACK status is published via WebSocket with the `command_id` so the frontend can update UI
5. Unacknowledged commands (no ACK within 2 seconds) are retried up to 3 times with 500ms backoff (500ms, 1000ms, 1500ms)
6. After 3 failed retries, the command is marked `FAILED` and an alert is published via WebSocket

#### `failsafe_manager.py` -- Hazard Monitoring & Escalation

```python
class FailsafeManager:
    """
    Continuously monitors all drones for hazardous conditions.
    Implements an escalation chain: warn → auto-action → alert operator.
    """

    # Thresholds
    HEARTBEAT_TIMEOUT_S = 5.0
    BATTERY_WARNING_PCT = 30.0
    BATTERY_CRITICAL_PCT = 20.0
    BATTERY_EMERGENCY_PCT = 10.0
    MAX_ALTITUDE_M = 120.0        # Regulatory ceiling
    MIN_SEPARATION_M = 5.0        # Collision avoidance

    # Escalation levels
    class Level(Enum):
        INFO = "info"
        WARNING = "warning"
        CRITICAL = "critical"
        EMERGENCY = "emergency"

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        while self._running:
            for drone in self.orchestrator.drones.values():
                self._check_heartbeat(drone)
                self._check_battery(drone)
                self._check_altitude(drone)
                self._check_geofence(drone)
            self._check_separation()
            await asyncio.sleep(0.5)  # 2Hz check rate

    def _check_heartbeat(self, drone: Drone):
        if drone.connection is None:
            return
        elapsed = time.time() - drone.last_heartbeat
        if elapsed > self.HEARTBEAT_TIMEOUT_S:
            if drone.status != DroneStatus.LOST:
                drone.status = DroneStatus.LOST
                self._escalate(
                    self.Level.CRITICAL,
                    f"Lost contact with '{drone.drone_id}' ({elapsed:.1f}s)",
                    drone_id=drone.drone_id,
                    action="replan",
                )
                self.orchestrator.allocator.replan_on_loss(drone.drone_id)

    def _check_battery(self, drone: Drone):
        if drone.status != DroneStatus.AIRBORNE:
            return
        if drone.battery_pct < self.BATTERY_EMERGENCY_PCT:
            self._escalate(self.Level.EMERGENCY, f"Battery emergency {drone.drone_id}: {drone.battery_pct}%",
                          drone_id=drone.drone_id, action="land_immediate")
            self.orchestrator.commands.land(drone.drone_id)
        elif drone.battery_pct < self.BATTERY_CRITICAL_PCT:
            self._escalate(self.Level.CRITICAL, f"Battery critical {drone.drone_id}: {drone.battery_pct}%",
                          drone_id=drone.drone_id, action="rtl")
            self.orchestrator.commands.rtl(drone.drone_id)
        elif drone.battery_pct < self.BATTERY_WARNING_PCT:
            self._escalate(self.Level.WARNING, f"Battery low {drone.drone_id}: {drone.battery_pct}%",
                          drone_id=drone.drone_id, action="none")

    def _check_altitude(self, drone: Drone):
        if drone.alt > self.MAX_ALTITUDE_M:
            self._escalate(self.Level.WARNING, f"Altitude breach {drone.drone_id}: {drone.alt:.1f}m",
                          drone_id=drone.drone_id, action="descend")

    def _check_geofence(self, drone: Drone):
        if drone.status != DroneStatus.AIRBORNE:
            return
        if not self.orchestrator.geofence.contains(drone.lat, drone.lon):
            self._escalate(self.Level.CRITICAL, f"Geofence breach {drone.drone_id}",
                          drone_id=drone.drone_id, action="rtl")
            self.orchestrator.commands.rtl(drone.drone_id)

    def _check_separation(self):
        """Check minimum separation between all active drone pairs."""
        active = [d for d in self.orchestrator.drones.values()
                  if d.status == DroneStatus.AIRBORNE]
        for i, d1 in enumerate(active):
            for d2 in active[i+1:]:
                dist = SwarmOrchestrator._haversine(d1.lat, d1.lon, d2.lat, d2.lon)
                if dist < self.MIN_SEPARATION_M:
                    self._escalate(
                        self.Level.EMERGENCY,
                        f"Collision risk: {d1.drone_id} <-> {d2.drone_id} = {dist:.1f}m",
                        action="separate",
                    )

    def _escalate(self, level: 'Level', message: str, drone_id: str = None, action: str = None):
        """Log the event, send WebSocket alert, record to mission logger."""
        event = {
            "type": "alert" if level in (self.Level.CRITICAL, self.Level.EMERGENCY) else "event",
            "level": level.value,
            "message": message,
            "drone_id": drone_id,
            "action": action,
            "timestamp": time.time(),
        }
        self.orchestrator.telemetry.broadcast_event(event)
        self.orchestrator.logger.log_event(event)
```

**Escalation chain:**

```
INFO      → Log only, no action
WARNING   → Log + WebSocket event + UI indicator (yellow)
CRITICAL  → Log + WebSocket alert + automatic safety action (RTL/replan) + UI alarm (red)
EMERGENCY → Log + WebSocket alert + immediate motor action + UI alarm + audio alert
```

#### `mission_logger.py` -- Persistence & Replay

```python
class MissionLogger:
    """
    Records all telemetry and events to SQLite for post-flight analysis
    and mission replay.
    """

    def __init__(self, db_path: str = "data/missions.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._lock = asyncio.Lock()
        self._init_schema()
        self._current_flight_id: str | None = None

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS flights (
                flight_id TEXT PRIMARY KEY,
                start_time REAL NOT NULL,
                end_time REAL,
                drone_count INTEGER,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_id TEXT NOT NULL,
                drone_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                lat REAL, lon REAL, alt REAL,
                heading REAL, battery_pct REAL,
                groundspeed REAL, status TEXT,
                FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                drone_id TEXT,
                event_type TEXT NOT NULL,
                level TEXT,
                detail TEXT,
                FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
            );
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                waypoints_json TEXT NOT NULL,
                formation TEXT,
                drone_assignments_json TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_telemetry_flight
                ON telemetry(flight_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_telemetry_drone
                ON telemetry(flight_id, drone_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_flight
                ON events(flight_id, timestamp);
        """)

    def start_flight(self, drone_count: int) -> str:
        flight_id = f"flight_{int(time.time())}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO flights (flight_id, start_time, drone_count) VALUES (?, ?, ?)",
                (flight_id, time.time(), drone_count),
            )
            self._conn.commit()
        self._current_flight_id = flight_id
        return flight_id

    def log_telemetry(self, drone: Drone):
        if not self._current_flight_id:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO telemetry (flight_id, drone_id, timestamp, lat, lon, alt, "
                "heading, battery_pct, groundspeed, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self._current_flight_id, drone.drone_id, time.time(),
                 drone.lat, drone.lon, drone.alt, drone.heading,
                 drone.battery_pct, getattr(drone, "groundspeed", 0.0),
                 drone.status.value),
            )
            # Commit in batches (every 100 rows) for performance
            ...

    def log_event(self, event: dict):
        if not self._current_flight_id:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (flight_id, timestamp, drone_id, event_type, level, detail) "
                "VALUES (?,?,?,?,?,?)",
                (self._current_flight_id, event["timestamp"], event.get("drone_id"),
                 event.get("action", "unknown"), event.get("level", "info"),
                 event.get("message", "")),
            )
            self._conn.commit()

    def end_flight(self):
        if self._current_flight_id:
            with self._lock:
                self._conn.execute(
                    "UPDATE flights SET end_time = ? WHERE flight_id = ?",
                    (time.time(), self._current_flight_id),
                )
                self._conn.commit()
            self._current_flight_id = None

    def get_telemetry_history(self, flight_id: str, drone_id: str = None,
                              start_time: float = None, end_time: float = None) -> list[dict]:
        """Retrieve telemetry for replay. Supports filtering by drone and time range."""
        ...

    def get_event_log(self, flight_id: str = None, level: str = None,
                      limit: int = 100) -> list[dict]:
        """Retrieve events with optional filters."""
        ...
```

**Logging rates and storage estimates:**
- Telemetry: 10Hz per drone x 3 drones = 30 rows/sec = ~108K rows/hour
- Row size: ~120 bytes -> ~13 MB/hour (manageable for SQLite)
- Events: sporadic, typically 10-100 per flight
- Batch commit every 100 telemetry rows to avoid write amplification

#### `formation_controller.py` -- PID-Based Station-Keeping

See [Section 6](#6-formation-maintenance-algorithm) for the full algorithm description.

```python
class FormationController:
    """
    Active formation maintenance using PID control.
    Runs at 5Hz, issuing velocity corrections to keep drones on station.
    """

    UPDATE_RATE_HZ = 5
    DEAD_ZONE_M = 1.0         # No correction if within 1m
    MAX_CORRECTION_MPS = 2.0   # Safety speed limit

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator
        self.formation_targets: dict[str, Waypoint] = {}  # drone_id -> target position
        self.pids: dict[str, PIDController] = {}
        self._active = False

    def set_formation(self, formation_type: str, center: Waypoint, params: dict):
        """Compute target positions for a formation and assign to drones."""
        # Uses mission_planner.py functions to compute positions
        ...

    async def start(self):
        self._active = True
        self._task = asyncio.create_task(self._control_loop())

    async def _control_loop(self):
        while self._active:
            for drone_id, target in self.formation_targets.items():
                drone = self.orchestrator.drones.get(drone_id)
                if drone is None or drone.status != DroneStatus.AIRBORNE:
                    continue
                error = self._compute_error(drone, target)
                if error.magnitude < self.DEAD_ZONE_M:
                    continue
                correction = self.pids[drone_id].update(error)
                correction = correction.clamp(self.MAX_CORRECTION_MPS)
                self._send_velocity_command(drone, correction)
            await asyncio.sleep(1.0 / self.UPDATE_RATE_HZ)
```

#### `task_allocator.py` -- Optimal Role Assignment

```python
class TaskAllocator:
    """
    Assigns drones to mission roles and waypoints using the Hungarian algorithm
    for optimal assignment, falling back to greedy for real-time replanning.
    """

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator

    def optimal_assign(self, mission_roles: list[dict]) -> dict[str, str]:
        """
        Given a list of required roles with capabilities, find the optimal
        assignment of drones to roles minimizing total cost (distance + capability mismatch).

        Uses scipy.optimize.linear_sum_assignment (Hungarian algorithm).
        """
        from scipy.optimize import linear_sum_assignment
        import numpy as np

        active = [d for d in self.orchestrator.drones.values()
                  if d.status in (DroneStatus.CONNECTED, DroneStatus.AIRBORNE)]
        n_drones = len(active)
        n_roles = len(mission_roles)

        # Build cost matrix: drones x roles
        cost = np.full((n_drones, n_roles), 1e9)
        for i, drone in enumerate(active):
            for j, role in enumerate(mission_roles):
                if not self._can_fulfill(drone, role):
                    continue  # Leave at 1e9 (infeasible)
                dist = SwarmOrchestrator._haversine(
                    drone.lat, drone.lon,
                    role["waypoint"].lat, role["waypoint"].lon,
                )
                cost[i][j] = dist

        row_ind, col_ind = linear_sum_assignment(cost)
        assignments = {}
        for r, c in zip(row_ind, col_ind):
            if cost[r][c] < 1e9:
                assignments[active[r].drone_id] = mission_roles[c]["role_name"]
        return assignments

    def replan_on_loss(self, lost_drone_id: str):
        """
        Redistribute a lost drone's waypoints to active drones.
        Uses greedy nearest-neighbor for speed (must complete within one control cycle).
        """
        lost = self.orchestrator.drones[lost_drone_id]
        remaining = lost.mission[:]
        lost.mission = []

        if not remaining:
            return

        active = [d for d in self.orchestrator.drones.values()
                  if d.status == DroneStatus.AIRBORNE and d.drone_id != lost_drone_id]

        if not active:
            self.orchestrator.failsafe._escalate(
                FailsafeManager.Level.EMERGENCY,
                "No active drones remain -- mission aborted",
            )
            return

        # Check if lost drone had a critical role
        lost_role = lost.role
        if lost_role == DroneRole.RECON and lost.capabilities.has_camera:
            replacement = next(
                (d for d in active if d.capabilities.has_camera and d.role != DroneRole.RECON),
                None,
            )
            if replacement:
                replacement.role = DroneRole.RECON
                self.orchestrator.failsafe._escalate(
                    FailsafeManager.Level.WARNING,
                    f"RECON reassigned: {lost_drone_id} -> {replacement.drone_id}",
                )
            else:
                self.orchestrator.failsafe._escalate(
                    FailsafeManager.Level.CRITICAL,
                    "RECON capability lost -- mission degraded",
                )

        # Greedy assignment: for each orphaned waypoint, assign to nearest active drone
        for wp in remaining:
            nearest = min(active, key=lambda d: SwarmOrchestrator._haversine(
                d.lat, d.lon, wp.lat, wp.lon))
            nearest.mission.append(wp)

    def replan_on_add(self, new_drone_id: str):
        """When a drone joins mid-mission, offload waypoints from the most burdened drone."""
        new_drone = self.orchestrator.drones[new_drone_id]
        active = [d for d in self.orchestrator.drones.values()
                  if d.status == DroneStatus.AIRBORNE and d.drone_id != new_drone_id]

        if not active:
            return

        # Find the most overloaded drone
        most_loaded = max(active, key=lambda d: len(d.mission))
        if len(most_loaded.mission) <= 1:
            return  # Nothing worth redistributing

        # Transfer the second half of waypoints to the new drone
        split = len(most_loaded.mission) // 2
        new_drone.mission = most_loaded.mission[split:]
        most_loaded.mission = most_loaded.mission[:split]
```

#### `geofence_manager.py` -- Boundary Enforcement

```python
class GeofenceManager:
    """
    Loads, saves, and enforces geofence polygons.
    Uses ray-casting algorithm for point-in-polygon checks.
    """

    def __init__(self, geofence_dir: str = "geofences"):
        self.geofence_dir = Path(geofence_dir)
        self.active_polygon: list[tuple[float, float]] | None = None  # [(lat, lon), ...]
        self.max_altitude: float = 120.0
        self.min_altitude: float = 0.0

    def load(self, name: str = "default"):
        path = self.geofence_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            self.active_polygon = [(p["lat"], p["lon"]) for p in data["polygon"]]
            self.max_altitude = data.get("max_altitude", 120.0)
            self.min_altitude = data.get("min_altitude", 0.0)

    def save(self, name: str = "default"):
        self.geofence_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "polygon": [{"lat": p[0], "lon": p[1]} for p in self.active_polygon],
            "max_altitude": self.max_altitude,
            "min_altitude": self.min_altitude,
        }
        with open(self.geofence_dir / f"{name}.json", "w") as f:
            json.dump(data, f, indent=2)

    def contains(self, lat: float, lon: float) -> bool:
        """Ray-casting point-in-polygon test."""
        if self.active_polygon is None:
            return True  # No geofence = unrestricted

        n = len(self.active_polygon)
        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = self.active_polygon[i]
            yj, xj = self.active_polygon[j]
            if ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def check_altitude(self, alt: float) -> bool:
        return self.min_altitude <= alt <= self.max_altitude
```

#### `mesh_bridge.py` (Future) -- SiK-to-ESP32 Mesh Gateway

This module is planned for the 10+ drone scale, where the star topology of SiK radios becomes a bottleneck.

**Concept:**
- ESP32 modules on each drone form a mesh network (ESP-NOW or custom protocol)
- A single ESP32 on the ground acts as a gateway
- `mesh_bridge.py` translates between MAVLink-over-serial (SiK) and MAVLink-over-mesh (ESP32)
- Enables multi-hop communication: drones relay messages for drones that are out of direct radio range

**Architecture (planned):**
```
Drone (far) → ESP32 mesh → Drone (relay) → ESP32 mesh → Ground ESP32 → USB → mesh_bridge.py → orchestrator
```

This module is not implemented in the current version. The interface is reserved so that other modules can be written against it today and gain mesh support later without refactoring.

#### `video_manager.py` -- Video Stream Management

Manages video streams from camera-equipped drones (Class B+). Receives analog FPV video via a multi-channel receiver connected to a USB capture device, or IP streams from RPi cameras (Class C) over the WiFi mesh. Transcodes incoming feeds to WebRTC for low-latency browser playback.

**Responsibilities:**
- Enumerate available video sources (analog channels mapped to drone IDs, or IP stream URLs from RPi cameras)
- Transcode analog capture (V4L2 / DirectShow) and RTSP streams to WebRTC via GStreamer or aiortc
- Route multiple feeds simultaneously (up to 6 concurrent streams)
- Publish `video_stream_available` WebSocket messages when a drone's camera comes online or goes offline
- Provide STUN/TURN signaling endpoint for WebRTC negotiation with the frontend
- Overlay HUD data (altitude, speed, heading) server-side for analog feeds that lack on-screen display

```python
class VideoManager:
    MAX_CONCURRENT_STREAMS = 6

    def __init__(self, orchestrator: SwarmOrchestrator):
        self.orchestrator = orchestrator
        self.active_streams: dict[str, VideoStream] = {}  # drone_id → stream

    async def start_stream(self, drone_id: str) -> WebRTCOffer: ...
    async def stop_stream(self, drone_id: str) -> None: ...
    def get_active_feeds(self) -> list[str]: ...
```

#### Connection Type Tracking

The `Drone` dataclass gains a `connection_type` field to track how each drone communicates with the ground station:

```python
class ConnectionType(str, Enum):
    RADIO = "radio"       # SiK 915MHz / 433MHz
    FIBER = "fiber"       # Fiber optic tether
    MESH = "mesh"         # ESP32 WiFi mesh
    LORA = "lora"         # LoRa SX1276
    LTE = "lte"           # 4G/LTE cellular

@dataclass
class Drone:
    # ... existing fields ...
    connection_type: ConnectionType = ConnectionType.RADIO
    spool_remaining_m: float | None = None  # Fiber drones only: meters of spool left
    spool_anchor: tuple[float, float] | None = None  # Fiber: lat/lon of spool position
```

The connection type is declared in the fleet registry JSON and confirmed at registration. For fiber drones, the orchestrator tracks spool consumption in real-time based on distance traveled from the anchor point, and broadcasts `spool_status` messages over WebSocket.

#### Fiber Tether Constraints in Path Planner

Fiber-optic drones are physically tethered, which imposes hard constraints on the path planner and formation controller:

- **No loops**: The path must not cross itself, as the fiber would tangle. The planner validates that no path segment intersects a previous segment.
- **Straight-line or fan-out only**: Fiber drones are restricted to straight-line outbound paths or fan-out patterns from the spool anchor. Circular orbits and complex formations are not permitted.
- **Max spool length**: The total path length from anchor to drone must not exceed the spool length. The planner rejects waypoints that would exceed `spool_remaining_m` and triggers a `spool_low` warning at 80% usage.
- **RTL path**: Return-to-launch for fiber drones follows the reverse of the outbound path (rewinding the spool) rather than a direct line.

### 2.2 Process Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MAIN PROCESS (PID 1)                         │
│                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │
│  │   Main Event Loop    │  │   FastAPI Server (uvicorn)           │ │
│  │                      │  │                                      │ │
│  │   - Startup          │  │   - REST API endpoints               │ │
│  │   - Signal handling  │  │   - WebSocket upgrade handler        │ │
│  │   - Shutdown         │  │   - Runs on the asyncio event loop   │ │
│  │                      │  │                                      │ │
│  └──────────────────────┘  └──────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │
│  │   Telemetry Task     │  │   Failsafe Monitor Task             │ │
│  │   (asyncio coroutine)│  │   (asyncio coroutine)               │ │
│  │   - 10Hz poll loop   │  │   - 2Hz check loop                  │ │
│  │   - MAVLink recv     │  │   - Heartbeat timeout detection     │ │
│  │     (run_in_executor)│  │   - Battery monitoring              │ │
│  │   - State update     │  │   - Geofence enforcement            │ │
│  │   - WS broadcast     │  │   - Separation checks               │ │
│  └──────────────────────┘  └──────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │
│  │   Formation Task     │  │   Mission Task(s)                    │ │
│  │   (asyncio coroutine)│  │   (asyncio coroutines)              │ │
│  │   - 5Hz PID loop     │  │   - One asyncio task per mission    │ │
│  │   - Position control │  │   - Sequential waypoint execution   │ │
│  │   - Velocity cmds    │  │   - Created/cancelled dynamically   │ │
│  │                      │  │                                      │ │
│  └──────────────────────┘  └──────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────┐                                           │
│  │   Logger Task        │                                           │
│  │   (asyncio coroutine)│                                           │
│  │   - Batched SQLite   │                                           │
│  │     writes           │                                           │
│  │   - Flush on event   │                                           │
│  │                      │                                           │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

**Asyncio concurrency model:**
- **Single process, single event loop** keeps deployment simple (one Python process, no IPC overhead)
- **Telemetry coroutine** runs at consistent 10Hz; blocking pymavlink I/O is offloaded via `run_in_executor()` so it does not stall the event loop
- **Failsafe coroutine** is a separate asyncio task from telemetry so a telemetry stall does not prevent failsafe detection
- **Formation coroutine** runs its own tight loop at 5Hz; decoupling from telemetry keeps PID timing consistent
- **Mission tasks** are created per-mission via `asyncio.create_task()` and cancelled on completion or abort; they `await` on `_wait_until_reached` which yields control to the event loop between checks
- **Logger task** (optional) decouples SQLite writes from the telemetry hot path; writes are queued and batched
- **FastAPI** shares the same asyncio event loop; REST handlers are thin async wrappers that call into the orchestrator

**Concurrency safety:**
- `Drone` dataclass fields are updated by the telemetry coroutine (single-writer pattern)
- Per-drone `asyncio.Lock` protects state transitions in `SwarmOrchestrator`
- SQLite access is serialized via `MissionLogger._lock` (asyncio.Lock)
- WebSocket client list is protected by a lock in the telemetry aggregator

### 2.3 FastAPI Application Structure

```python
# api.py — FastAPI application

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Drone Swarm Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator: SwarmOrchestrator = None

@app.on_event("startup")
async def startup():
    global orchestrator
    orchestrator = SwarmOrchestrator()
    orchestrator.register_from_fleet()
    orchestrator.connect_all()

@app.on_event("shutdown")
async def shutdown():
    orchestrator.shutdown()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    orchestrator.telemetry.ws_clients.append(ws)
    try:
        while True:
            # Keep connection alive; client may send pings
            data = await ws.receive_text()
    except WebSocketDisconnect:
        orchestrator.telemetry.ws_clients.remove(ws)

# REST endpoints (see Section 4 for full list)
@app.post("/api/swarm/takeoff")
async def swarm_takeoff(body: TakeoffRequest):
    return orchestrator.commands.takeoff(body.drone_ids, body.altitude)

# ... (all endpoints listed in Section 4)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 3. Next.js Frontend Architecture

### 3.1 App Router File Tree

```
ground-station/
├── package.json
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── public/
│   ├── drone-icon.svg
│   ├── drone-icon-lost.svg
│   └── marker-shadow.png
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout: sidebar + alert banner
│   │   ├── page.tsx                # Dashboard: map + telemetry overview
│   │   ├── globals.css
│   │   ├── fleet/
│   │   │   ├── page.tsx            # Fleet management: list, register, remove
│   │   │   └── [id]/
│   │   │       └── page.tsx        # Single drone detail: telemetry charts, role, config
│   │   ├── mission/
│   │   │   ├── page.tsx            # Mission planner: formation editor, waypoint drawing
│   │   │   ├── active/
│   │   │   │   └── page.tsx        # Active mission monitor: progress, drone assignments
│   │   │   └── history/
│   │   │       ├── page.tsx        # Mission history list
│   │   │       └── [id]/
│   │   │           └── page.tsx    # Mission replay: playback with timeline scrubber
│   │   ├── geofence/
│   │   │   └── page.tsx            # Geofence editor: draw/edit polygons on map
│   │   ├── logs/
│   │   │   └── page.tsx            # Event log viewer with filters
│   │   └── settings/
│   │       └── page.tsx            # System settings: connection config, thresholds
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx         # Navigation sidebar with status indicators
│   │   │   ├── AlertBanner.tsx     # Top-of-screen critical alerts
│   │   │   └── Header.tsx          # Connection status, swarm summary
│   │   ├── map/
│   │   │   ├── MapView.tsx         # Leaflet map container
│   │   │   ├── DroneMarker.tsx     # Custom rotatable drone icon with status color
│   │   │   ├── DronePath.tsx       # Polyline showing drone trail
│   │   │   ├── WaypointMarker.tsx  # Numbered waypoint markers
│   │   │   ├── GeofenceOverlay.tsx # Polygon overlay for geofence
│   │   │   ├── FormationOverlay.tsx# Ghost markers showing formation targets
│   │   │   └── MapControls.tsx     # Zoom-to-swarm, follow mode toggle
│   │   ├── telemetry/
│   │   │   ├── DroneCard.tsx       # Status card per drone (battery, alt, speed)
│   │   │   ├── SwarmSummary.tsx    # Aggregate swarm stats
│   │   │   ├── BatteryGauge.tsx    # Circular battery indicator with color coding
│   │   │   ├── AltitudeChart.tsx   # Real-time altitude line chart
│   │   │   └── TelemetryGrid.tsx   # Grid of all drone cards
│   │   ├── mission/
│   │   │   ├── MissionBuilder.tsx  # Drag-and-drop mission designer
│   │   │   ├── FormationPicker.tsx # Select formation type (line, V, orbit, sweep)
│   │   │   ├── WaypointEditor.tsx  # Edit waypoint list with lat/lon/alt
│   │   │   ├── MissionTimeline.tsx # Progress bar per drone in active mission
│   │   │   └── ReplayPlayer.tsx    # Timeline scrubber for flight replay
│   │   ├── fleet/
│   │   │   ├── FleetTable.tsx      # Sortable table of all drones
│   │   │   ├── RegisterDrone.tsx   # Registration form
│   │   │   └── DroneRoleSelector.tsx # Role assignment dropdown with validation
│   │   ├── controls/
│   │   │   ├── SwarmControls.tsx   # Takeoff/Land/RTL/Emergency buttons
│   │   │   ├── EmergencyButton.tsx # Large red emergency stop with confirmation
│   │   │   └── DroneCommands.tsx   # Per-drone command panel
│   │   ├── video/
│   │   │   ├── VideoFeed.tsx       # Single drone camera feed with HUD overlay (WebRTC)
│   │   │   ├── PiPOverlay.tsx      # Picture-in-Picture container (max 4, corner-pinned)
│   │   │   └── MultiFeedGrid.tsx   # 2x2 or 3x2 grid of all active camera feeds
│   │   ├── geofence/
│   │   │   ├── GeofenceDrawer.tsx  # Polygon drawing tool on map
│   │   │   └── GeofenceSettings.tsx# Altitude limits, save/load
│   │   └── shared/
│   │       ├── StatusBadge.tsx     # Colored badge for drone status
│   │       ├── ConfirmDialog.tsx   # Confirmation modal for dangerous actions
│   │       └── LoadingSpinner.tsx
│   ├── stores/
│   │   ├── droneStore.ts          # Zustand: per-drone telemetry state
│   │   ├── missionStore.ts        # Zustand: active mission state
│   │   ├── uiStore.ts             # Zustand: UI preferences, selected drone, view mode
│   │   └── alertStore.ts          # Zustand: active alerts queue
│   ├── lib/
│   │   ├── websocket.ts           # WebSocket client with auto-reconnect
│   │   ├── webrtc.ts              # WebRTC client for receiving video streams from Python backend
│   │   ├── api.ts                 # Typed REST client (fetch wrapper)
│   │   ├── types.ts               # TypeScript interfaces for all data models
│   │   └── geo.ts                 # Haversine, bearing, coordinate utils
│   └── hooks/
│       ├── useSwarmWebSocket.ts   # Hook: connect WS, route messages to stores
│       ├── useDrone.ts            # Hook: get single drone state
│       ├── useSwarmStatus.ts      # Hook: get aggregate swarm state
│       └── useMapFollow.ts        # Hook: auto-pan map to selected drone
```

### 3.2 Component Hierarchy (Dashboard Page)

```
layout.tsx
├── Header
│   ├── ConnectionIndicator (green/red dot)
│   └── SwarmSummary (3 drones | 2 airborne | 1 connected)
├── AlertBanner (conditionally rendered when alerts exist)
│   └── Alert[] (dismissible, color-coded by severity)
├── Sidebar
│   ├── NavLink (Dashboard)
│   ├── NavLink (Fleet)
│   ├── NavLink (Mission)
│   ├── NavLink (Geofence)
│   ├── NavLink (Logs)
│   └── NavLink (Settings)
└── page.tsx (Dashboard)
    ├── MapView (70% width)
    │   ├── DroneMarker[] (one per drone, rotated to heading)
    │   ├── DronePath[] (recent trail polyline)
    │   ├── WaypointMarker[] (if mission active)
    │   ├── GeofenceOverlay
    │   ├── FormationOverlay (ghost target positions)
    │   └── MapControls
    ├── TelemetryGrid (30% width, right panel)
    │   └── DroneCard[] (one per drone)
    │       ├── StatusBadge
    │       ├── BatteryGauge
    │       ├── Position (lat, lon, alt)
    │       └── MiniChart (altitude sparkline)
    └── SwarmControls (bottom bar)
        ├── TakeoffAll button
        ├── LandAll button
        ├── RTLAll button
        └── EmergencyButton (red, with ConfirmDialog)
```

### 3.3 State Management (Zustand)

```typescript
// stores/droneStore.ts

interface DroneState {
  drone_id: string;
  role: string;
  status: string;
  lat: number;
  lon: number;
  alt: number;
  heading: number;
  battery_pct: number;
  groundspeed: number;
  mission_progress: number;     // 0.0 - 1.0
  trail: [number, number][];    // recent positions for path rendering
  last_update: number;          // timestamp
}

interface DroneStore {
  drones: Record<string, DroneState>;
  selectedDroneId: string | null;

  // Actions
  updateTelemetry: (drone_id: string, data: Partial<DroneState>) => void;
  updateSwarmSnapshot: (snapshot: Record<string, DroneState>) => void;
  selectDrone: (drone_id: string | null) => void;
  removeDrone: (drone_id: string) => void;
}

export const useDroneStore = create<DroneStore>((set, get) => ({
  drones: {},
  selectedDroneId: null,

  updateTelemetry: (drone_id, data) =>
    set((state) => {
      const existing = state.drones[drone_id] || {};
      const trail = existing.trail || [];
      if (data.lat !== undefined && data.lon !== undefined) {
        trail.push([data.lat, data.lon]);
        if (trail.length > 200) trail.shift();  // Keep last 200 points
      }
      return {
        drones: {
          ...state.drones,
          [drone_id]: { ...existing, ...data, trail, last_update: Date.now() },
        },
      };
    }),

  updateSwarmSnapshot: (snapshot) =>
    set((state) => {
      const updated = { ...state.drones };
      for (const [id, data] of Object.entries(snapshot)) {
        updated[id] = { ...updated[id], ...data, last_update: Date.now() };
      }
      return { drones: updated };
    }),

  selectDrone: (drone_id) => set({ selectedDroneId: drone_id }),
  removeDrone: (drone_id) =>
    set((state) => {
      const { [drone_id]: _, ...rest } = state.drones;
      return { drones: rest };
    }),
}));
```

```typescript
// stores/missionStore.ts

interface MissionStore {
  activeMission: {
    mission_id: string;
    name: string;
    status: "planning" | "executing" | "paused" | "completed" | "aborted";
    formation: string;
    waypoints: Waypoint[];
    droneAssignments: Record<string, string[]>;  // drone_id -> waypoint_ids
    startTime: number | null;
  } | null;
  missionHistory: MissionSummary[];

  // Actions
  setActiveMission: (mission: MissionStore["activeMission"]) => void;
  clearActiveMission: () => void;
  addToHistory: (summary: MissionSummary) => void;
}
```

```typescript
// stores/alertStore.ts

interface Alert {
  id: string;
  level: "info" | "warning" | "critical" | "emergency";
  message: string;
  drone_id?: string;
  timestamp: number;
  dismissed: boolean;
}

interface AlertStore {
  alerts: Alert[];
  addAlert: (alert: Omit<Alert, "id" | "dismissed">) => void;
  dismissAlert: (id: string) => void;
  dismissAll: () => void;
  activeAlerts: () => Alert[];    // Non-dismissed, sorted by severity
}
```

### 3.4 WebSocket Client

```typescript
// lib/websocket.ts

class SwarmWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectDelay = 1000;    // Start at 1s, exponential backoff
  private maxReconnectDelay = 30000; // Cap at 30s
  private messageQueue: string[] = []; // Queue messages during disconnect
  private maxQueueSize = 100;

  constructor(url: string = "ws://localhost:8000/ws") {
    this.url = url;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("[WS] Connected");
      this.reconnectDelay = 1000;  // Reset backoff
      this.flushQueue();
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.routeMessage(msg);
    };

    this.ws.onclose = () => {
      console.log(`[WS] Disconnected. Reconnecting in ${this.reconnectDelay}ms...`);
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    };

    this.ws.onerror = (err) => {
      console.error("[WS] Error:", err);
      this.ws?.close();
    };
  }

  private routeMessage(msg: any) {
    switch (msg.type) {
      case "telemetry_update":
        useDroneStore.getState().updateTelemetry(msg.drone_id, msg);
        break;
      case "swarm_status":
        useDroneStore.getState().updateSwarmSnapshot(msg.drones);
        break;
      case "event":
        useAlertStore.getState().addAlert({
          level: msg.level,
          message: msg.message,
          drone_id: msg.drone_id,
          timestamp: msg.timestamp,
        });
        break;
      case "alert":
        useAlertStore.getState().addAlert({
          level: msg.level || "critical",
          message: msg.message,
          drone_id: msg.drone_id,
          timestamp: msg.timestamp,
        });
        // Play audio alert for critical/emergency
        if (msg.level === "critical" || msg.level === "emergency") {
          new Audio("/alert.mp3").play().catch(() => {});
        }
        break;
    }
  }

  private flushQueue() {
    while (this.messageQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(this.messageQueue.shift()!);
    }
  }

  send(data: any) {
    const msg = JSON.stringify(data);
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(msg);
    } else {
      if (this.messageQueue.length < this.maxQueueSize) {
        this.messageQueue.push(msg);
      }
      // Backpressure: drop oldest if queue full
    }
  }
}
```

### 3.5 REST Client

```typescript
// lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiCall<T>(method: string, path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${getToken()}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail);
  }
  return res.json();
}

export const swarmApi = {
  // Swarm commands
  takeoff:     (drone_ids?: string[], altitude?: number) =>
    apiCall("POST", "/api/swarm/takeoff", { drone_ids, altitude }),
  rtl:         () => apiCall("POST", "/api/swarm/rtl", {}),
  land:        () => apiCall("POST", "/api/swarm/land", {}),
  emergency:   () => apiCall("POST", "/api/swarm/emergency", {}),
  goto:        (drone_id: string, lat: number, lon: number, alt: number) =>
    apiCall("POST", "/api/swarm/goto", { drone_id, lat, lon, alt }),

  // Mission
  assignMission: (data: MissionAssignment) =>
    apiCall("POST", "/api/mission/assign", data),
  executeMission: () =>
    apiCall("POST", "/api/mission/execute", {}),
  getMissionStatus: () =>
    apiCall<MissionStatus>("GET", "/api/mission/status"),

  // Fleet
  getFleet:       () => apiCall<DroneInfo[]>("GET", "/api/fleet"),
  registerDrone:  (data: DroneRegistration) =>
    apiCall("POST", "/api/fleet/register", data),
  removeDrone:    (id: string) => apiCall("DELETE", `/api/fleet/${id}`),
  setDroneRole:   (id: string, role: string) =>
    apiCall("POST", `/api/drone/${id}/role`, { role }),

  // Geofence
  getGeofence:    () => apiCall<GeofenceData>("GET", "/api/geofence"),
  setGeofence:    (polygon: LatLon[], maxAlt: number) =>
    apiCall("POST", "/api/geofence", { polygon, max_altitude: maxAlt }),

  // Telemetry & Logs
  getTelemetryHistory: (flight_id: string, params?: TelemetryQuery) =>
    apiCall<TelemetryRecord[]>("GET", `/api/telemetry/history?flight_id=${flight_id}`),
  getLogs:         (params?: LogQuery) =>
    apiCall<EventRecord[]>("GET", "/api/logs"),
};
```

### 3.6 Map Integration

**Technology:** React-Leaflet with OpenStreetMap tiles (offline-capable via tile caching).

**Drone marker rendering:**
- Custom SVG icon rotated to match `heading` from telemetry
- Color-coded by status:
  - Green = airborne
  - Blue = connected/armed
  - Yellow = returning
  - Red = lost
  - Gray = disconnected
- Pulsing ring animation on selected drone
- Tooltip on hover: drone_id, altitude, battery, role

**Path rendering:**
- Polyline from `trail` array in drone store (last 200 positions)
- Color matches drone marker
- Opacity gradient: most recent segment = solid, oldest = faint

**Waypoint rendering:**
- Numbered circle markers on mission waypoints
- Dashed line connecting waypoints in order
- Completed waypoints shown as filled circles
- Current target waypoint shown with pulsing ring

**Geofence rendering:**
- Red-dashed polygon border
- Semi-transparent red fill (10% opacity)
- Editable with Leaflet Draw plugin
- Vertex drag handles for adjustment

**Performance considerations:**
- Canvas renderer instead of SVG for 10+ drones (Leaflet `preferCanvas: true`)
- Throttle trail updates to 2Hz on the rendering side even though telemetry arrives at 10Hz
- Off-screen drones skip marker position updates (Leaflet handles this via viewport culling)

---

## 4. Communication Protocol (Backend <-> Frontend)

### 4.1 WebSocket Messages (JSON)

All messages share a common envelope:

```json
{
  "type": "<message_type>",
  "timestamp": 1711411200.123
}
```

#### `telemetry_update` -- Per-Drone Position (10Hz)

```json
{
  "type": "telemetry_update",
  "drone_id": "alpha",
  "timestamp": 1711411200.123,
  "lat": 34.052235,
  "lon": -118.243683,
  "alt": 25.3,
  "heading": 187.5,
  "battery_pct": 74.0,
  "groundspeed": 3.2,
  "status": "airborne"
}
```

**Bandwidth estimate (3 drones):** ~200 bytes/msg x 10 Hz x 3 drones = ~6 KB/s. Negligible.

**Adaptive Telemetry Rate (scaling to 50+ drones):**

At 50 drones with a flat 10Hz rate, the WebSocket layer must handle 500 msg/s (~100 KB/s per client). This does not scale, especially over WiFi to tablets in the field. The backend implements adaptive telemetry rates based on drone relevance to the operator:

| Drone State | Telemetry Rate | Rationale |
|-------------|---------------|-----------|
| Selected (operator is viewing) | 10 Hz | Full fidelity for the drone under active control |
| Active (airborne, executing mission) | 2 Hz | Sufficient for map updates and situational awareness |
| Idle (grounded, connected, not armed) | 0.5 Hz | Battery/status heartbeat only |

For a typical 50-drone mission where 1 drone is selected, ~20 are active, and ~29 are idle: `(1 x 10) + (20 x 2) + (29 x 0.5) = 64.5 msg/s` -- an 87% reduction from the flat 500 msg/s.

The frontend sends a `set_focus` WebSocket message when the operator selects a drone, and the backend adjusts per-client telemetry rates accordingly.

**Per-client message queuing:** Each WebSocket client has a dedicated async queue with a max depth of 100 messages. If a client is slow (e.g., tablet on flaky WiFi), the oldest messages are dropped rather than applying backpressure to the telemetry pipeline. This prevents a single slow client from degrading the system.

**Binary encoding option:** For bandwidth-constrained deployments, the backend supports MessagePack encoding instead of JSON. Clients opt in by sending `{"encoding": "msgpack"}` after connection. MessagePack reduces per-message size by 60-70% (~60 bytes vs ~200 bytes for telemetry), which matters at scale over radio links.

**Alternative: Server-Sent Events (SSE):** For deployments where the frontend only needs one-way telemetry (no command channel over the same connection), SSE (`text/event-stream`) is a simpler alternative to WebSocket. SSE works through HTTP proxies and load balancers without upgrade negotiation. The REST API already handles commands, so the WebSocket's bidirectional capability is only used for `set_focus` messages -- which could alternatively be a REST call. SSE should be evaluated as a simpler transport for Phase 2+ cloud deployments.

#### `swarm_status` -- Full Swarm Snapshot (1Hz)

```json
{
  "type": "swarm_status",
  "timestamp": 1711411200.000,
  "drone_count": 3,
  "active_count": 2,
  "drones": {
    "alpha": {
      "role": "recon",
      "status": "airborne",
      "lat": 34.052235, "lon": -118.243683, "alt": 25.3,
      "heading": 187.5,
      "battery_pct": 74.0,
      "groundspeed": 3.2,
      "mission_progress": 0.65,
      "mission_waypoint": 4,
      "mission_total_waypoints": 6
    },
    "bravo": { ... },
    "charlie": { ... }
  },
  "formation": {
    "type": "v_formation",
    "active": true,
    "errors": {"alpha": 0.3, "bravo": 1.2, "charlie": 0.8}
  },
  "geofence_active": true
}
```

#### `event` -- Timestamped Swarm Event

```json
{
  "type": "event",
  "timestamp": 1711411205.456,
  "level": "info",
  "drone_id": "alpha",
  "event_type": "waypoint_reached",
  "message": "alpha reached waypoint 3/6",
  "detail": {"waypoint_index": 3, "lat": 34.053, "lon": -118.244}
}
```

Event types:
- `waypoint_reached` -- drone arrived at a mission waypoint
- `mission_complete` -- drone finished all waypoints
- `drone_lost` -- heartbeat timeout triggered
- `drone_recovered` -- heartbeat resumed after loss
- `replan` -- mission waypoints redistributed
- `role_changed` -- drone role reassigned
- `formation_set` -- new formation activated
- `geofence_breach` -- drone exited geofence boundary
- `battery_warning` -- battery below warning threshold
- `battery_critical` -- battery below critical threshold
- `separation_warning` -- two drones too close

#### `alert` -- Critical Alert Requiring Operator Attention

```json
{
  "type": "alert",
  "timestamp": 1711411210.789,
  "level": "critical",
  "drone_id": "charlie",
  "message": "RECON capability lost -- mission degraded",
  "action_taken": "rtl",
  "requires_ack": true
}
```

Alert levels:
- `warning` -- operator should be aware (yellow banner)
- `critical` -- automatic action taken, operator must acknowledge (red banner + audio)
- `emergency` -- immediate safety action taken (flashing red + continuous audio)

#### `video_stream_available` -- Camera Feed Status Change

Notifies the frontend when a drone's camera feed becomes available or unavailable. The frontend uses this to enable/disable the Tap-to-View video panel, update the Multi-Feed Grid, and manage PiP slots.

```json
{
  "type": "video_stream_available",
  "timestamp": 1711411215.456,
  "drone_id": "bravo",
  "available": true,
  "stream_type": "analog_fpv",
  "resolution": [640, 480],
  "fps": 30
}
```

- `stream_type`: `"analog_fpv"` (Class B, via capture card) or `"ip_camera"` (Class C, RPi camera via RTSP)
- When `available` is `false`, the frontend tears down the WebRTC connection for that drone and shows a "Feed Lost" overlay.

#### `spool_status` -- Fiber Tether Spool Update

For fiber-connected drones, reports the remaining spool length at 1Hz. The frontend uses this to render the tether line on the map and display the spool remaining indicator on the connection badge.

```json
{
  "type": "spool_status",
  "timestamp": 1711411216.789,
  "drone_id": "delta",
  "spool_remaining_m": 2340,
  "spool_total_m": 5000,
  "spool_anchor": [34.0522, -118.2437],
  "tether_angle_deg": 47.3
}
```

- `spool_remaining_m` decreasing below 20% of `spool_total_m` triggers a `spool_low` event (sent as a separate `event` message).
- `tether_angle_deg`: bearing from anchor to drone, used to draw the tether line on the map.

### 4.2 REST API Endpoints

#### Swarm Commands

| Method | Endpoint | Request Body | Response | Description |
|--------|----------|-------------|----------|-------------|
| POST | `/api/swarm/takeoff` | `{"drone_ids": ["alpha","bravo"], "altitude": 10.0}` | `{"alpha": {"ok": true}, "bravo": {"ok": true}}` | Takeoff specified drones (or all if drone_ids is null) |
| POST | `/api/swarm/rtl` | `{"drone_ids": null}` | `{"ok": true}` | Return to launch, all or specified |
| POST | `/api/swarm/land` | `{"drone_ids": null}` | `{"ok": true}` | Land in place, all or specified |
| POST | `/api/swarm/emergency` | `{}` | `{"ok": true, "warning": "ALL MOTORS KILLED"}` | Emergency stop -- motors off immediately |
| POST | `/api/swarm/goto` | `{"drone_id": "alpha", "lat": 34.05, "lon": -118.24, "alt": 20}` | `{"ok": true}` | Send single drone to waypoint |

#### Mission Management

| Method | Endpoint | Request Body | Response | Description |
|--------|----------|-------------|----------|-------------|
| POST | `/api/mission/assign` | `{"name": "area_sweep", "formation": "line", "waypoints": [...], "drone_assignments": {...}}` | `{"mission_id": "m_1711411200"}` | Create and assign a mission |
| POST | `/api/mission/execute` | `{"mission_id": "m_1711411200"}` | `{"ok": true, "flight_id": "flight_1711411200"}` | Start executing the assigned mission |
| GET | `/api/mission/status` | -- | `{"status": "executing", "progress": 0.45, "drones": {...}}` | Get current mission state |

#### Fleet Management

| Method | Endpoint | Request Body | Response | Description |
|--------|----------|-------------|----------|-------------|
| GET | `/api/fleet` | -- | `[{"drone_id": "alpha", "sysid": 1, ...}]` | List all registered drones |
| POST | `/api/fleet/register` | `{"drone_id": "delta", "sysid": 4, "port": "COM6", "hw_class": "B", ...}` | `{"ok": true}` | Register a new drone |
| DELETE | `/api/fleet/{id}` | -- | `{"ok": true}` | Remove a drone from the fleet |
| POST | `/api/drone/{id}/role` | `{"role": "recon"}` | `{"ok": true}` or `{"ok": false, "error": "missing_camera"}` | Change drone role (validated against capabilities) |

#### Geofence

| Method | Endpoint | Request Body | Response | Description |
|--------|----------|-------------|----------|-------------|
| GET | `/api/geofence` | -- | `{"polygon": [...], "max_altitude": 120.0}` | Get active geofence |
| POST | `/api/geofence` | `{"polygon": [{"lat":34.05,"lon":-118.24}, ...], "max_altitude": 120.0}` | `{"ok": true}` | Set geofence polygon |

#### Telemetry & Logs

| Method | Endpoint | Query Params | Response | Description |
|--------|----------|-------------|----------|-------------|
| GET | `/api/telemetry/history` | `flight_id`, `drone_id` (opt), `start` (opt), `end` (opt) | `[{"timestamp":..., "lat":..., ...}]` | Historical telemetry for replay |
| GET | `/api/logs` | `flight_id` (opt), `level` (opt), `drone_id` (opt), `limit` (opt) | `[{"timestamp":..., "event_type":..., ...}]` | Event log with filters |

---

## 5. Data Storage

### 5.1 Storage Layout

```
drone-swarm-orchestrator/
├── fleet/                       # Fleet registry (JSON files)
│   ├── alpha.json
│   ├── bravo.json
│   └── charlie.json
├── geofences/                   # Geofence definitions (JSON files)
│   ├── default.json
│   ├── test_field.json
│   └── competition.json
├── config/                      # System configuration
│   └── swarm_config.yaml
├── data/                        # Runtime data
│   └── missions.db              # SQLite database
```

### 5.2 Fleet Registry (JSON Files)

Each drone has a JSON file in `fleet/`. This is the existing format from `fleet_registry.py`.

```json
// fleet/alpha.json
{
  "drone_id": "alpha",
  "sysid": 1,
  "net_id": 25,
  "port": "/dev/ttyUSB0",
  "hw_class": "B",
  "capabilities": {
    "name": "Sensor",
    "has_camera": true,
    "has_compute": false,
    "has_payload": false,
    "roles": ["recon", "relay", "decoy"]
  },
  "default_role": "recon"
}
```

**Rationale for JSON files over database:** Fleet registration is a low-frequency operation done before flights. JSON files are human-readable, easy to version control, and can be edited manually. The registry is small (3-50 files at most).

### 5.3 SQLite Database Schema (`missions.db`)

```sql
-- Flights: one row per flight session
CREATE TABLE flights (
    flight_id   TEXT PRIMARY KEY,        -- "flight_1711411200"
    start_time  REAL NOT NULL,           -- Unix timestamp
    end_time    REAL,                    -- NULL if in progress
    drone_count INTEGER NOT NULL,
    mission_id  TEXT,                    -- FK to missions table (nullable)
    notes       TEXT
);

-- Telemetry: high-frequency drone state snapshots
CREATE TABLE telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id   TEXT NOT NULL,
    drone_id    TEXT NOT NULL,
    timestamp   REAL NOT NULL,           -- Unix timestamp (ms precision)
    lat         REAL,
    lon         REAL,
    alt         REAL,                    -- meters, relative to home
    heading     REAL,                    -- degrees, 0-360
    battery_pct REAL,                    -- 0-100
    groundspeed REAL,                    -- m/s
    status      TEXT,                    -- DroneStatus enum value
    FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
);

-- Events: discrete occurrences during a flight
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id   TEXT NOT NULL,
    timestamp   REAL NOT NULL,
    drone_id    TEXT,                    -- NULL for swarm-level events
    event_type  TEXT NOT NULL,           -- "waypoint_reached", "drone_lost", etc.
    level       TEXT NOT NULL DEFAULT 'info',  -- info/warning/critical/emergency
    detail      TEXT,                    -- Human-readable message
    metadata    TEXT,                    -- JSON blob for structured data
    FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
);

-- Missions: mission plans (reusable, not tied to a specific flight)
CREATE TABLE missions (
    mission_id             TEXT PRIMARY KEY,   -- "m_1711411200"
    name                   TEXT NOT NULL,
    waypoints_json         TEXT NOT NULL,       -- JSON array of {lat, lon, alt}
    formation              TEXT,                -- "line", "v_formation", "orbit", etc.
    drone_assignments_json TEXT,                -- JSON: {drone_id: [waypoint_indices]}
    created_at             REAL NOT NULL
);

-- Indexes for query performance
CREATE INDEX idx_telemetry_flight_time ON telemetry(flight_id, timestamp);
CREATE INDEX idx_telemetry_drone_time  ON telemetry(flight_id, drone_id, timestamp);
CREATE INDEX idx_events_flight_time    ON events(flight_id, timestamp);
CREATE INDEX idx_events_level          ON events(level);
```

**Storage estimates (3 drones, 1-hour flight):**

| Table | Row Size | Rows/Hour | Size/Hour |
|-------|----------|-----------|-----------|
| telemetry | ~120 bytes | 108,000 (10Hz x 3 drones) | ~13 MB |
| events | ~200 bytes | ~100 | ~20 KB |
| flights | ~100 bytes | 1 | negligible |

SQLite handles this workload well. At 50+ drones or multi-hour missions, consider WAL mode and periodic archival.

### 5.4 Geofence Files

```json
// geofences/default.json
{
  "name": "Test Field",
  "polygon": [
    {"lat": 34.0520, "lon": -118.2440},
    {"lat": 34.0520, "lon": -118.2400},
    {"lat": 34.0540, "lon": -118.2400},
    {"lat": 34.0540, "lon": -118.2440}
  ],
  "max_altitude": 120.0,
  "min_altitude": 0.0,
  "created_at": 1711411200
}
```

### 5.5 Configuration

```yaml
# config/swarm_config.yaml

swarm:
  heartbeat_timeout_s: 5.0
  battery_warning_pct: 30
  battery_critical_pct: 20
  battery_emergency_pct: 10
  max_altitude_m: 120
  min_separation_m: 5
  default_takeoff_alt_m: 10

formation:
  update_rate_hz: 5
  dead_zone_m: 1.0
  max_correction_mps: 2.0
  pid_p: 0.5
  pid_i: 0.01
  pid_d: 0.1

telemetry:
  poll_rate_hz: 10
  snapshot_rate_hz: 1
  trail_length: 200

api:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["http://localhost:3000"]

logging:
  db_path: "data/missions.db"
  telemetry_batch_size: 100
```

---

## 6. Formation Maintenance Algorithm

### 6.1 Overview

The formation controller runs a continuous PID control loop that keeps each drone at its designated position within the formation. It does not navigate drones to waypoints (that is the mission executor's job). Instead, it maintains relative positions while the swarm moves as a unit.

### 6.2 PID Controller

Each drone has an independent PID controller operating on 2D position error (north/east components).

```
                ┌─────────────────────────────────┐
                │      Formation Geometry          │
                │   (line, V, orbit, custom)       │
                └──────────────┬──────────────────┘
                               │
                       Target Position (lat, lon, alt)
                               │
                               ▼
              ┌────────────────────────────────────┐
              │          Error Calculation          │
              │                                    │
              │  error_north = target_lat - actual  │
              │  error_east  = target_lon - actual  │
              │  error_mag   = sqrt(N^2 + E^2)      │
              └──────────────┬─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Dead Zone?    │
                    │  error < 1.0m   │──── YES ──── No correction
                    └────────┬────────┘
                             │ NO
                             ▼
              ┌──────────────────────────────────┐
              │         PID Controller            │
              │                                   │
              │  P = Kp * error                   │
              │  I = Ki * integral(error * dt)    │
              │  D = Kd * d(error)/dt             │
              │  output = P + I + D               │
              └──────────────┬───────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Clamp Speed   │
                    │  max 2.0 m/s    │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────────┐
              │   MAVLink Velocity Command        │
              │   SET_POSITION_TARGET_LOCAL_NED   │
              │   (vx, vy components)             │
              └──────────────────────────────────┘
```

### 6.3 Tuning Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Kp (proportional) | 0.5 | Primary correction force. Higher = faster response, more oscillation |
| Ki (integral) | 0.01 | Eliminates steady-state error. Keep low to avoid windup |
| Kd (derivative) | 0.1 | Dampens oscillation. Increase if drone oscillates around target |
| Update rate | 5 Hz | Balance between responsiveness and radio bandwidth |
| Dead zone | 1.0 m | Prevents micro-corrections that cause oscillation |
| Max correction speed | 2.0 m/s | Safety limit; prevents aggressive maneuvers |
| Integral windup limit | 5.0 m*s | Clamp integral term to prevent runaway accumulation |

**These are starting values.** Field tuning is required:
1. Start with P-only control (Ki=0, Kd=0)
2. Increase Kp until drone consistently approaches target without overshooting more than 2m
3. Add Kd to dampen any oscillation
4. Add small Ki only if there is persistent steady-state offset (usually caused by wind)

### 6.4 Formation Types

All formations are computed by `mission_planner.py` (existing module). The formation controller takes the computed positions and maintains them.

| Formation | Drones | Use Case | Existing Implementation |
|-----------|--------|----------|------------------------|
| Line | N | Search patterns, parallel sweep | `line_formation()` |
| V-Formation | N | Forward movement, recon | `v_formation()` |
| Orbit | N | Point surveillance | `orbit_point()` |
| Area Sweep | N | Lawnmower coverage | `area_sweep()` |
| Custom | N | User-defined positions | Planned |

### 6.5 Formation Transitions

When switching formations (e.g., from line to V):
1. Compute new target positions for each drone
2. Calculate optimal assignment (which drone goes to which new position) using the task allocator to minimize total distance
3. Gradually transition: set new targets and let PID controllers guide drones to new positions
4. Formation is "stable" when all drones are within dead zone of their new targets

---

## 7. Dynamic Replanning Algorithm

### 7.1 Drone Lost

```
Event: Heartbeat timeout on drone X
       │
       ▼
Step 1: Identify orphaned waypoints
       │  remaining_wps = drone_X.mission (unvisited waypoints)
       │  lost_role = drone_X.role
       │  lost_capabilities = drone_X.capabilities
       │
       ▼
Step 2: Check for critical capability loss
       │  IF lost_role == RECON AND has_camera:
       │    Search active drones for one with camera
       │    IF found:
       │      Reassign RECON role to replacement
       │      Alert: "RECON reassigned: X -> Y"
       │    ELSE:
       │      Alert: "RECON capability lost -- mission degraded"
       │  IF lost_role == STRIKE AND has_payload:
       │    Alert: "STRIKE capability lost -- mission degraded"
       │
       ▼
Step 3: Build cost matrix
       │  For each active drone D and orphaned waypoint W:
       │    cost[D][W] = haversine(D.position, W.position)
       │
       │  If N_active < 5 and N_waypoints < 20:
       │    Use Hungarian algorithm (optimal)
       │  Else:
       │    Use greedy nearest-neighbor (fast, good-enough)
       │
       ▼
Step 4: Assign orphaned waypoints
       │  For each waypoint (greedy):
       │    Find nearest active drone
       │    Append waypoint to that drone's mission
       │  For Hungarian:
       │    Use scipy.optimize.linear_sum_assignment
       │    Assign based on optimal matching
       │
       ▼
Step 5: Recompute formation
       │  Remove lost drone from formation targets
       │  Recompute positions for N-1 drones
       │  Formation controller auto-adjusts
       │
       ▼
Step 6: Log and notify
       │  Log "replan" event to mission_logger
       │  Broadcast "event" WebSocket message
       │  If critical capability lost: broadcast "alert"
```

### 7.2 Drone Added Mid-Mission

```
Event: New drone Y connected and airborne during active mission
       │
       ▼
Step 1: Evaluate current workload
       │  For each active drone, count remaining waypoints
       │  most_loaded = drone with most remaining waypoints
       │
       ▼
Step 2: Transfer surplus waypoints
       │  IF most_loaded has > 1 remaining waypoint:
       │    split = len(most_loaded.mission) // 2
       │    new_drone.mission = most_loaded.mission[split:]
       │    most_loaded.mission = most_loaded.mission[:split]
       │
       ▼
Step 3: Assign role
       │  Based on new drone's capabilities:
       │    If has_camera and no RECON in swarm: assign RECON
       │    If has_payload and no STRIKE in swarm: assign STRIKE
       │    Else: assign RELAY
       │
       ▼
Step 4: Recompute formation
       │  Add new drone to formation targets
       │  Recompute positions for N+1 drones
       │  Formation controller guides new drone into position
       │
       ▼
Step 5: Log and notify
       │  Log "drone_added" event
       │  Broadcast updated swarm_status
```

### 7.3 Replanning Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max replan time | 500 ms | Must complete within one failsafe check cycle |
| Min active drones for mission | 1 | Mission aborts if all drones are lost |
| Replan cooldown | 5 s | Prevent cascading replans if multiple drones are lost simultaneously |
| Max waypoints per drone | 50 | Beyond this, mission should be split into segments |

---

## 8. Security Architecture

### 8.1 Layer Diagram

```
Layer 4 (Application)   │ REST API auth (Bearer/JWT) + WebSocket token
                         │ Input validation on all API endpoints
─────────────────────────┼──────────────────────────────────────────────
Layer 3 (Transport)      │ HTTPS/WSS (TLS 1.3) between frontend and backend
                         │ (localhost in single-machine mode; TLS for remote)
─────────────────────────┼──────────────────────────────────────────────
Layer 2 (Protocol)       │ MAVLink v2 message signing
                         │ Shared key per fleet, prevents command injection
─────────────────────────┼──────────────────────────────────────────────
Layer 1 (Physical/Link)  │ SiK radio: FHSS (frequency hopping spread spectrum)
                         │ NetID provides basic network separation
                         │ Future: AES-256 on ESP32 mesh
```

### 8.2 MAVLink v2 Signing

MAVLink v2 supports message signing to prevent command injection attacks. Each message includes a SHA-256 HMAC using a shared secret key.

**Configuration:**
- A 32-byte signing key is generated per fleet and stored in `config/signing_key.bin`
- The key is loaded by `swarm.py` and set on each MAVLink connection:
  ```python
  conn.setup_signing(key, sign_outgoing=True, allow_unsigned_callback=None)
  ```
- All unsigned incoming messages are rejected (no `allow_unsigned_callback`)
- The same key must be flashed to each drone's flight controller

**Key management:**
- Key generated once during fleet setup: `os.urandom(32)`
- Distributed to drones via USB (not over radio)
- Rotated manually if a drone is decommissioned or compromised

### 8.3 Frontend-Backend Authentication

**Single-operator mode (default):**
- A static bearer token is generated at backend startup and printed to console
- Operator copies the token into the frontend settings page
- Token is stored in browser `localStorage` and sent as `Authorization: Bearer <token>` header
- Simple and sufficient for a single-laptop deployment

**Multi-operator mode (future):**
- JWT-based authentication with username/password
- Tokens expire after 8 hours (configurable)
- Role-based access: `operator` (full control) vs `observer` (read-only, no commands)
- WebSocket connections require a valid token in the initial handshake query string

### 8.4 WebSocket Authentication

```
Client → ws://host:8000/ws?token=<bearer_token>
Server → Validates token before accepting upgrade
       → Rejects with 403 if invalid
       → Adds to client list if valid
```

### 8.5 Input Validation

All REST API endpoints validate:
- Drone IDs exist in the fleet registry
- Coordinates are within valid ranges (lat: -90 to 90, lon: -180 to 180)
- Altitudes are within configured limits
- Roles match drone capabilities
- Geofence polygons have at least 3 vertices and form a valid polygon

### 8.6 Phase 1 Security Requirements

The following security measures must be enabled from Phase 1, not deferred:

**MAVLink v2 signing (Phase 1, not Phase 5):**
- MAVLink v2 message signing must be enabled from the first flight. Without signing, any device with a $15 SiK radio on the same frequency can inject commands into the fleet -- including disarm, motor override, or waypoint changes. This is not a theoretical risk; MAVLink injection tools are publicly available.
- The signing key is generated per-fleet during initial setup and flashed to each drone's flight controller via USB during firmware configuration (`firmware_flasher.py` already handles parameter setting -- add the signing key to this process).
- The ground station loads the same key at startup. All unsigned incoming messages are rejected.

**TLS for ground station to browser (Phase 1):**
- The WebSocket and REST API connections between the Python backend and the browser frontend must use TLS (HTTPS/WSS) from Phase 1. This is trivial to enable -- generate a self-signed certificate during first setup, or use mkcert for local development.
- Without TLS, any device on the same WiFi network can sniff operator commands and telemetry, or inject commands via the REST API. On a shared field network, this is a realistic attack surface.
- Implementation: Configure uvicorn with `--ssl-keyfile` and `--ssl-certfile`. The frontend connects to `wss://` and `https://` instead of the unencrypted variants. Total effort: ~30 minutes of configuration.

### 8.7 Future Security Enhancements

| Enhancement | Priority | Description |
|-------------|----------|-------------|
| AES-256 mesh encryption | High | Encrypt all ESP32 mesh traffic end-to-end |
| Hardware security module | Medium | Store signing keys in tamper-resistant hardware (e.g., ATECC608) |
| Audit logging | Medium | Log all operator commands with timestamps for accountability |
| Rate limiting | Low | Prevent API abuse in multi-operator mode |
| Geofence signing | Low | Cryptographically sign geofence definitions to prevent tampering |

---

## 9. Failure Modes & Recovery

### 9.1 Failure Mode Table

| # | Failure | Detection Method | Automatic Response | Recovery Procedure | Severity |
|---|---------|-----------------|-------------------|-------------------|----------|
| F1 | **Drone comms loss** (single drone) | Heartbeat timeout (>5s) | Mark drone LOST; replan mission waypoints to remaining drones; recompute formation for N-1 | Wait for heartbeat to resume. If not recovered in 60s, drone's onboard failsafe (RTL) activates. Operator can manually re-register if drone returns. | CRITICAL |
| F2 | **Drone comms loss** (all drones) | All drones show LOST status simultaneously | Cancel all mission tasks; broadcast EMERGENCY alert; log event | Likely ground-side issue (USB hub, radio, laptop). Check USB connections, restart backend. Drones will RTL on their own failsafes. | EMERGENCY |
| F3 | **Ground station crash** (backend process dies) | Frontend WebSocket disconnect; no heartbeat from backend | Frontend shows "DISCONNECTED" banner; plays alert tone | Drones continue last command or RTL (ArduPilot GCS failsafe). Restart backend process; drones will reconnect on next heartbeat. | CRITICAL |
| F4 | **GPS loss** (single drone) | GPS fix_type drops below 3D fix (`GPS_RAW_INT.fix_type < 3`) | Alert operator; if in flight, command LOITER (hold position using last known GPS) | Wait for GPS reacquisition. If no fix in 30s, RTL (uses compass + baro for inertial nav). | WARNING |
| F5 | **Compass failure** | `SYS_STATUS` sensor health flags; erratic heading readings (>30deg/sec change with no turn commanded) | Alert operator; switch to GPS-only heading (requires forward movement) | Land the affected drone. Recalibrate compass on ground. Not safe to continue mission with compass failure. | CRITICAL |
| F6 | **Motor failure** | Detected by ArduPilot (EKF vibration, motor output saturation); communicated via `STATUSTEXT` message | ArduPilot attempts controlled descent; backend marks drone LOST; replans mission | Drone will crash-land. Remove from fleet. Investigate hardware. No software recovery possible. | EMERGENCY |
| F7 | **Battery critical** (<20%) | `SYS_STATUS.battery_remaining` below threshold | Automatic RTL command sent to drone | Drone returns to launch. Mission continues with remaining drones. Replan triggered. | CRITICAL |
| F8 | **Battery emergency** (<10%) | Same as above, lower threshold | Immediate LAND command (land in place, do not attempt RTL) | Recover drone from landing location. | EMERGENCY |
| F9 | **Geofence breach** | `geofence_manager.contains()` returns False for drone position | Automatic RTL command; log breach event; alert operator | Investigate why drone left geofence (wind, GPS error, bad waypoint). Adjust geofence or mission plan. | CRITICAL |
| F10 | **Radio interference** (degraded link) | Intermittent heartbeats; increased MAVLink packet loss (`RADIO_STATUS.remrssi` drops) | Alert operator with signal quality metric; reduce telemetry rate to conserve bandwidth | Move ground station or increase radio power. Consider switching to backup frequency. If persistent, RTL affected drones. | WARNING |
| F11 | **Software crash** (unhandled exception in a task) | Task health monitoring: event loop exception handler catches unhandled errors | Attempt to restart crashed task; if restart fails, initiate graceful shutdown (RTL all) | Check logs for exception traceback. Fix bug, restart backend. | CRITICAL |
| F12 | **USB disconnect** (single radio) | pyserial `SerialException` on read/write; MAVLink connection object reports error | Mark affected drone as DISCONNECTED; attempt reconnection every 5s for 30s | Reconnect USB cable. If powered USB hub, check hub power. Backend auto-reconnects when device reappears. | CRITICAL |
| F13 | **USB hub power loss** | All serial connections fail simultaneously | All drones marked DISCONNECTED; broadcast EMERGENCY alert | Drones RTL via onboard failsafe. Restore USB hub power. Restart backend. | EMERGENCY |
| F14 | **Frontend crash** (browser tab crash) | Backend unaware (frontend is stateless from backend perspective) | None needed; backend continues operating | Reload browser tab. WebSocket auto-reconnects. Zustand state rebuilds from next `swarm_status` snapshot. | LOW |
| F15 | **Collision risk** (drones too close) | `failsafe_manager._check_separation()` detects distance < 5m | Alert operator; no automatic evasive action (risk of making it worse) | Operator manually commands one drone to move. Future: automatic deconfliction vectors. | EMERGENCY |

### 9.2 Escalation Chain

```
Level 0: Normal operation
    │
    │  Anomaly detected
    ▼
Level 1: WARNING
    │  - Log event
    │  - WebSocket event (yellow indicator in UI)
    │  - No automatic action
    │  - Operator informed, may take action
    │
    │  Condition worsens or is safety-critical
    ▼
Level 2: CRITICAL
    │  - Log event
    │  - WebSocket alert (red indicator + audio in UI)
    │  - Automatic safety action (RTL, replan)
    │  - Operator must acknowledge
    │
    │  Immediate danger to aircraft or people
    ▼
Level 3: EMERGENCY
    │  - Log event
    │  - WebSocket alert (flashing red + continuous audio)
    │  - Immediate motor/flight action (land, kill)
    │  - Operator must acknowledge + confirm recovery plan
```

### 9.3 ArduPilot Onboard Failsafes (Defense in Depth)

The ground station failsafes are the first line of defense. If the ground station itself fails, ArduPilot's built-in failsafes provide a second layer:

| ArduPilot Failsafe | Parameter | Behavior |
|--------------------|-----------|----------|
| GCS Failsafe | `FS_GCS_ENABLE=1` | RTL if no GCS heartbeat for 5s |
| Battery Failsafe | `FS_BATT_ENABLE=1` | RTL at voltage threshold |
| GPS Failsafe | `FS_EKF_ACTION=1` | Land if EKF variance too high |
| Geofence | `FENCE_ENABLE=1` | RTL if breaching ArduPilot fence |
| Crash Detection | `FS_CRASH_CHECK=1` | Disarm if crash detected |

These parameters should be configured on every drone before flight. They act independently of the ground station software.

---

## 10. Scalability Path

### 10.1 Scale Tiers

```
Tier 1: 3 drones          Tier 2: 5-8 drones        Tier 3: 10-20 drones
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────────┐
│  Star topology   │      │  Star topology   │      │  Mesh networking     │
│  USB hub (basic) │      │  Powered USB hub │      │  ESP32 mesh bridge   │
│  Single laptop   │      │  Single laptop   │      │  Dedicated server    │
│  3x SiK radios   │      │  USB hub fan-out │      │  Multiple radios     │
│  All-in-one      │      │  Maybe UDP relay │      │  Multiple asyncio    │
└──────────────────┘      └──────────────────┘      └──────────────────────┘

Tier 4: 20-50 drones      Tier 5: 50+ drones
┌──────────────────────┐  ┌──────────────────────────────┐
│  Multi-GCS            │  │  Cloud-assisted              │
│  Shared state (Redis) │  │  Edge compute on drones      │
│  Hierarchical control │  │  AI-based planning           │
│  Sub-swarm leaders    │  │  Cellular/satellite backhaul │
│  Redundant comms      │  │  Digital twin simulation     │
└──────────────────────┘  └──────────────────────────────┘
```

### 10.2 Tier Details

#### Tier 1: 3 Drones (Current Design)

**Hardware:**
- 1 laptop (any modern laptop with 3+ USB ports)
- 1 basic USB hub (unpowered is fine for 3 SiK radios)
- 3 SiK 433/915 MHz radio pairs
- 3 ArduPilot drones

**Software:**
- Single Python process
- Star topology: each drone has a dedicated radio on a dedicated serial port
- Telemetry at 10Hz per drone = 30 messages/sec (trivial load)
- Frontend and backend on same laptop

**Limitations:**
- USB serial latency: ~10ms per read, negligible for 3 drones
- SiK radio bandwidth: 64 kbps per link, sufficient for MAVLink
- Radio range: ~1 km LOS with stock antennas

#### Tier 2: 5-8 Drones

**Changes needed:**
- **Powered USB hub:** 7-port powered hub (Anker or similar). SiK radios draw ~100mA each; unpowered hubs cannot reliably supply 5+ radios
- **Serial port management:** Use `udev` rules (Linux) or COM port aliases to ensure consistent port-to-drone mapping across reboots
- **UDP multicast option:** Instead of N serial connections, configure SiK radios in mesh mode or use a MAVProxy instance that bridges serial to UDP. Backend connects to UDP endpoints instead of serial ports. Reduces USB dependency
- **Telemetry batching:** At 80 messages/sec, consider reducing per-drone rate to 5Hz and using swarm snapshot at 2Hz
- **Formation controller load:** 8 PID loops at 5Hz = 40 control iterations/sec. Still manageable on a single event loop, but monitor CPU usage

**Cost estimate:** ~$150 additional (powered hub, extra radios)

#### Tier 3: 10-20 Drones

**Changes needed:**
- **ESP32 mesh networking:** SiK star topology does not scale beyond ~8 radios (USB port exhaustion, bandwidth contention). Deploy ESP32 modules on each drone forming an ESP-NOW mesh. Single ground ESP32 connects to the backend via USB. `mesh_bridge.py` translates between mesh and the existing MAVLink abstraction
- **Dedicated server:** Move the backend to a mini-PC (Intel NUC or similar) with reliable power. Laptop becomes a thin client running only the frontend
- **Process architecture:** Consider splitting telemetry aggregation into a separate process communicating via ZeroMQ or shared memory. This allows the telemetry process to use a dedicated CPU core
- **Database load:** 10 drones at 10Hz = 100 rows/sec into SQLite. Enable WAL mode. Consider reducing logging rate to 2Hz for non-critical telemetry
- **Frontend performance:** 20 drone markers with trails on Leaflet. Switch to Canvas renderer. Reduce trail length to 100 points. Throttle React re-renders to 5Hz

**Cost estimate:** ~$500 additional (ESP32 modules, NUC, antenna upgrades)

#### Tier 4: 20-50 Drones

**Changes needed:**
- **Hierarchical control:** Divide the swarm into sub-swarms of 5-10 drones. Each sub-swarm has a leader drone that relays commands and aggregates telemetry. Reduces ground-to-drone communication from N to N/5
- **Multiple ground stations:** Two or more operators with separate UI instances. Shared backend state via Redis or a shared SQLite (with proper locking). One operator is "primary" (can issue commands), others are "observers" unless primary delegates
- **Sub-swarm orchestrators:** Each sub-swarm can operate semi-autonomously. The main orchestrator sends high-level commands ("sweep area X"), sub-swarm leaders handle formation and individual waypoints
- **Redundant comms:** Primary mesh network + backup SiK radio link for critical commands (RTL, emergency stop). If mesh goes down, SiK provides degraded-but-functional control
- **Database:** Migrate from SQLite to PostgreSQL. 50 drones at 10Hz = 500 rows/sec. SQLite cannot handle this reliably. PostgreSQL with TimescaleDB extension for time-series optimization

**Cost estimate:** ~$2,000-5,000 additional (multiple ground stations, server hardware, network infrastructure)

#### Tier 5: 50+ Drones

**Changes needed:**
- **Cloud-assisted coordination:** Mission planning, optimal task allocation, and replanning run on cloud infrastructure (AWS/GCP). The ground station handles real-time control; the cloud handles planning (latency-tolerant)
- **Edge compute on drones:** Drones with Jetson Nano or Raspberry Pi CM4 run local path planning, obstacle avoidance, and inter-drone deconfliction. Reduces dependency on ground station for safety-critical decisions
- **Cellular/satellite backhaul:** For operations beyond radio range, drones use 4G/LTE or Iridium satellite modems. The ground station connects via internet
- **AI-based planning:** Reinforcement learning models trained in simulation for optimal task allocation, dynamic replanning, and formation adaptation. Deployed as ONNX models running on edge compute
- **Digital twin:** Full simulation environment (Gazebo + ArduPilot SITL) running in parallel with the live swarm. Used for predictive failure detection ("if we lose drone X in 2 minutes based on battery trend, pre-position drone Y")
- **Distributed state:** etcd or CockroachDB for strongly-consistent distributed state across multiple ground stations and cloud nodes

**Cost estimate:** $10,000+ (significant infrastructure investment)

### 10.3 Bottleneck Analysis by Scale

| Bottleneck | Hits at | Mitigation |
|-----------|---------|------------|
| USB port count | 5-8 drones | Powered hub, then mesh networking |
| SiK radio bandwidth (64kbps shared) | 8-10 drones | Mesh with higher bandwidth (ESP-NOW: 1Mbps) |
| Serial read latency (10ms/port) | 10+ drones | UDP multicast, or mesh with single USB connection |
| Python GIL (single-core telemetry) | 15-20 drones | Multiprocessing, or Rust/C extension for telemetry |
| SQLite write throughput | 20+ drones | PostgreSQL + TimescaleDB |
| Leaflet DOM rendering | 20+ markers with trails | Canvas renderer, WebGL (deck.gl), or virtual markers |
| Single operator cognitive load | 10+ drones | Hierarchical control, autonomous sub-swarms, AI alerts |
| Single point of failure (one laptop) | Any scale | Redundant ground stations, onboard failsafes |

---

## Technology Decision Rationale

### Why Next.js?

Next.js was chosen as the frontend framework after evaluating several alternatives. The decision acknowledges trade-offs for the current local-only deployment while optimizing for the product roadmap.

**Reasons for choosing Next.js:**
- **React ecosystem**: Largest component ecosystem, easiest to hire for. Libraries like react-leaflet, recharts, and zustand are mature and well-maintained.
- **Vercel deployment path**: Phase 2+ introduces cloud features (shared mission planning, fleet analytics dashboards, multi-operator collaboration). Next.js + Vercel provides a zero-config deployment path for these features.
- **SSR for initial load**: Server-side rendering ensures the dashboard loads fast on first visit, which matters when an operator opens the ground station UI on a tablet and needs immediate situational awareness.
- **Strong TypeScript support**: First-class TypeScript integration with App Router provides type safety across the telemetry data pipeline from WebSocket message to rendered component.

**Acknowledged trade-off:** Next.js is heavier than a native desktop framework (Tauri, Electron) for a local-only single-machine deployment. The dev server adds complexity during development, and the Node.js runtime is an extra dependency alongside Python.

**Mitigation for field use without internet:** Next.js can be built as a fully static export (`next export` / `output: 'export'`) and served directly from the Python FastAPI backend as static files. This eliminates the Node.js runtime requirement in the field -- the operator just runs the Python backend, which serves both the API and the pre-built frontend on a single port.

**Alternative considered:** Tauri was evaluated for a native desktop app with smaller binary size and direct OS integration. Tauri remains a candidate for a dedicated tablet app in Phase 4, where offline-first native performance and hardware integration (e.g., direct USB serial access) would justify the separate build target.

---

## Appendix A: Technology Stack Summary

| Layer | Technology | Version | License |
|-------|-----------|---------|---------|
| Drones | ArduPilot | 4.4+ | GPLv3 |
| MAVLink Library | pymavlink | 2.4+ | LGPLv3 |
| Backend Runtime | Python | 3.11+ | PSF |
| REST/WebSocket Server | FastAPI + uvicorn | 0.100+ | MIT |
| Task Allocation | scipy (Hungarian algorithm) | 1.11+ | BSD |
| Database | SQLite (stdlib) | 3.35+ | Public Domain |
| Frontend Framework | Next.js (App Router) | 14+ | MIT |
| UI Library | React | 18+ | MIT |
| State Management | Zustand | 4+ | MIT |
| Map | Leaflet + react-leaflet | 1.9+ / 4+ | BSD |
| Styling | Tailwind CSS | 3+ | MIT |
| Charts | Recharts or lightweight canvas | -- | MIT |

## Appendix B: Port Assignments

| Service | Port | Protocol |
|---------|------|----------|
| FastAPI REST + WebSocket | 8000 | HTTP/WS |
| Next.js dev server | 3000 | HTTP |
| SiK radio serial | /dev/ttyUSB0-N | Serial (57600 baud) |
| SITL simulation drone 1 | 14550 (UDP) | MAVLink |
| SITL simulation drone 2 | 14560 (UDP) | MAVLink |
| SITL simulation drone 3 | 14570 (UDP) | MAVLink |

## Appendix C: Development vs. Production

| Aspect | Development | Production |
|--------|------------|------------|
| Drones | ArduPilot SITL (simulated) | Physical drones |
| MAVLink transport | UDP localhost | USB serial (SiK) |
| Frontend | `next dev` (hot reload) | `next build && next start` |
| Backend | `uvicorn api:app --reload` | `uvicorn api:app --workers 1` |
| Database | SQLite file | SQLite file (or PostgreSQL at scale) |
| Auth | Disabled or static token | Bearer token / JWT |
| CORS | `localhost:3000` allowed | Locked to known origins |
| TLS | None (localhost) | Required for remote access |

---

## 11. Payload Compatibility System

The Payload Compatibility System validates and calculates performance metrics for drone loadout configurations. It ensures that every drone's frame, motors, battery, payload, and connection type are compatible before flight, and feeds loadout-derived parameters into mission planning, preflight checks, and in-flight weight compensation.

### 11.1 Module Breakdown

#### `loadout_checker.py` -- Loadout Validation and Performance Calculator

This module is the computational core of the Loadout Builder UI. It takes a loadout configuration (frame + motors + battery + payload + connection) and produces:

1. **Compatibility verdict:** COMPATIBLE, WARNINGS, or INCOMPATIBLE with a list of specific issues.
2. **Calculated performance metrics:** flight time, max speed, agility score, stability score, range, and wind resistance.
3. **Weight summary:** AUW, thrust-to-weight ratio, weight margin.

```python
# loadout_checker.py (structural sketch)

@dataclass
class LoadoutConfig:
    frame_id: str
    motor_id: str
    battery_id: str
    payload_id: str | None
    connection_id: str

@dataclass
class PerformanceMetrics:
    flight_time_min: float      # minutes
    max_speed_ms: float         # m/s
    agility_score: int          # 0-100
    stability_score: int        # 0-100
    range_km: float             # km
    wind_resist_kmh: float      # km/h max wind for stable hover

@dataclass
class LoadoutResult:
    status: Literal["COMPATIBLE", "WARNINGS", "INCOMPATIBLE"]
    metrics: PerformanceMetrics
    auw_grams: float
    max_auw_grams: float
    thrust_to_weight: float
    warnings: list[str]
    errors: list[str]

class LoadoutChecker:
    def __init__(self, profiles: PayloadProfiles):
        self.profiles = profiles

    def evaluate(self, config: LoadoutConfig) -> LoadoutResult:
        """Full loadout evaluation: compatibility + performance metrics."""
        ...

    def _calculate_auw(self, config: LoadoutConfig) -> float:
        """Sum of frame + motors + battery + payload + wiring/fasteners estimate."""
        ...

    def _calculate_flight_time(self, config: LoadoutConfig, auw: float) -> float:
        """Battery Wh / estimated power draw (motors + payload + avionics)."""
        ...

    def _calculate_thrust_to_weight(self, config: LoadoutConfig, auw: float) -> float:
        """Total motor thrust at 100% / (AUW * gravity)."""
        ...

    def _check_mount_compatibility(self, config: LoadoutConfig) -> list[str]:
        """Verify payload mount point exists on selected frame."""
        ...
```

#### `payload_profiles.py` -- Preset Definitions

A data module containing all known frame, motor, battery, payload, and connection profiles. Each profile is a dataclass with the physical specs needed by `LoadoutChecker`.

```python
# payload_profiles.py (structural sketch)

@dataclass
class FrameProfile:
    id: str
    name: str
    weight_grams: float
    max_auw_grams: float
    motor_count: int
    mount_points: list[str]       # e.g., ["top", "bottom_center", "front", "side"]
    geometry: str                  # "quad", "hex", "x8", "mini"
    drag_coefficient: float

@dataclass
class MotorProfile:
    id: str
    name: str
    kv: int
    max_thrust_grams: float       # per motor at 100% throttle
    weight_grams: float           # per motor (including prop)

@dataclass
class BatteryProfile:
    id: str
    name: str
    cell_count: int               # e.g., 4, 6, 12
    capacity_mah: int
    watt_hours: float
    weight_grams: float

@dataclass
class PayloadProfile:
    id: str
    name: str
    weight_grams: float
    mount_point: str              # required mount point
    power_draw_watts: float       # continuous power draw
    is_droppable: bool            # can be released mid-flight

@dataclass
class ConnectionProfile:
    id: str
    name: str
    range_km: float
    latency_ms: float
    weight_grams: float

class PayloadProfiles:
    """Registry of all known part profiles. Loaded from JSON/YAML on startup."""
    frames: dict[str, FrameProfile]
    motors: dict[str, MotorProfile]
    batteries: dict[str, BatteryProfile]
    payloads: dict[str, PayloadProfile]
    connections: dict[str, ConnectionProfile]

    # Preset loadouts (quick-load from the UI)
    PRESETS: dict[str, LoadoutConfig] = {
        "class_a_standard": LoadoutConfig("hex_550", "2814_700kv", "6s_5000", "lidar", "sik_915"),
        "class_b_recon":    LoadoutConfig("quad_450", "2312_920kv", "4s_3300", "fpv_cam", "sik_433"),
        "class_c_compute":  LoadoutConfig("hex_550", "2814_700kv", "6s_5000", "compute_box", "esp32_mesh"),
        "class_d_strike":   LoadoutConfig("x8_heavy", "4010_370kv", "12s_16000", "drop_mech", "4g_lte"),
    }
```

### 11.2 Integration Points

#### Fleet Registry -- Stores Current Loadout per Drone

The `Drone` dataclass in `swarm.py` gains a `loadout` field:

```python
@dataclass
class Drone:
    ...
    loadout: LoadoutConfig | None = None   # set via Loadout Builder UI
    loadout_result: LoadoutResult | None = None  # cached evaluation
```

When the operator saves a loadout from the UI, the API writes it to the Fleet Registry (JSON/SQLite). On startup, `SwarmOrchestrator.connect_all()` loads each drone's last-saved loadout and runs `LoadoutChecker.evaluate()` to populate `loadout_result`.

#### Preflight Check -- Validates Loadout Compatibility

The preflight check sequence (Screen 4 in the UI) adds a loadout validation step:

```
Preflight Checklist (extended)
──────────────────────────────
...
[6] Loadout compatibility      → LoadoutChecker.evaluate(drone.loadout)
    - PASS if status == COMPATIBLE
    - WARN if status == WARNINGS (operator can override)
    - FAIL if status == INCOMPATIBLE (blocks arming)
    - FAIL if drone.loadout is None (no loadout configured)
```

#### Mission Planner -- Adjusts Parameters Based on Loadout Weight

The Mission Planner reads `drone.loadout_result.metrics` to adjust mission parameters:

- **Speed:** cruise speed capped at 80% of `max_speed_ms` from the loadout evaluation.
- **Altitude:** heavier loadouts may require lower altitude ceilings in high-temperature / high-altitude environments (reduced air density).
- **Timing:** waypoint ETAs recalculated using the loadout's actual cruise speed rather than a default.
- **Endurance:** mission total flight time must not exceed 80% of the loadout's `flight_time_min` (20% reserve margin).

#### Firmware Flasher -- Sets Expected Weight Parameters for ArduPilot EKF

Before flight, the Firmware Flasher (or parameter upload step) writes loadout-derived parameters to ArduPilot so the EKF has accurate weight expectations:

```
MAVLink Parameter Writes (pre-arm)
───────────────────────────────────
MOT_THST_EXPO    → derived from motor profile thrust curve
INS_WEIGHT       → loadout_result.auw_grams / 1000  (kg)
```

This ensures ArduPilot's EKF state estimation and altitude hold are calibrated for the actual all-up weight, rather than relying on default parameters that may be wildly wrong for a heavy payload configuration.

#### Post-Release Compensation -- In-Flight Weight Change Notification

When a droppable payload (e.g., a drop mechanism) releases its cargo mid-flight, the orchestrator must notify ArduPilot of the sudden weight change so the EKF and altitude controller can compensate:

```
Payload Release Sequence
────────────────────────
1. Operator triggers "Release Payload" command from UI (or automated by mission plan)
2. Orchestrator sends MAVLink command to actuate the release servo/mechanism
3. Orchestrator calculates new AUW: current AUW - payload weight
4. Orchestrator sends updated weight parameter to ArduPilot:
     MAV_CMD_DO_SET_PARAMETER: INS_WEIGHT = new_auw_kg
5. Orchestrator updates drone.loadout_result with recalculated metrics
6. Mission Planner recalculates remaining waypoint ETAs with new performance envelope
7. Telemetry feed logs: "PAYLOAD RELEASED: {payload_name}, new AUW: {new_auw}g"
```

This prevents the common post-release problem where the drone suddenly climbs or oscillates because the flight controller still expects the pre-release weight.

### 11.3 Module Dependency Graph

```
                    ┌───────────────────────┐
                    │   payload_profiles.py  │
                    │   (part definitions)   │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌───────────────────────┐
                    │   loadout_checker.py   │
                    │   (evaluate loadout)   │
                    └──────────┬────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                   │
            ▼                  ▼                   ▼
   ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
   │ Fleet Registry   │ │ Preflight    │ │ Mission Planner  │
   │ (drone.loadout)  │ │ Check        │ │ (speed/altitude/ │
   └─────────────────┘ │ (go/no-go)   │ │  timing adjust)  │
                        └──────────────┘ └──────────────────┘
            ┌──────────────────┼──────────────────┐
            │                                     │
            ▼                                     ▼
   ┌─────────────────┐                 ┌───────────────────────┐
   │ Firmware Flasher │                 │ Post-Release          │
   │ (EKF weight      │                 │ Compensation          │
   │  params)         │                 │ (in-flight weight     │
   └─────────────────┘                 │  change → ArduPilot)  │
                                        └───────────────────────┘
```

---

## Related Documents

- [[API_DESIGN]] -- REST and WebSocket API specification
- [[UI_DESIGN]] -- Ground station UI that consumes this architecture
- [[COMMS_PROTOCOL]] -- MAVLink communication layer details
- [[HARDWARE_SPEC]] -- Hardware capability classes referenced by the orchestrator
- [[PRODUCT_SPEC]] -- Requirements driving the architecture
- [[PRESSURE_TEST]] -- Review that prompted the asyncio rewrite
- [[DECISION_LOG]] -- Architecture decision rationale
