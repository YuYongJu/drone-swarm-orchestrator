# Core Concepts

## Swarm

A `Swarm` is the top-level object that manages a fleet of drones. It handles connections, coordinates commands, monitors telemetry, and enforces safety rules.

```python
from drone_swarm import Swarm

swarm = Swarm()
```

One `Swarm` instance manages N drones. All commands can target a single drone (`drone_id="alpha"`) or all drones at once (`drone_id=None`, the default).

## Drone

A `Drone` represents a single vehicle in the swarm. Each drone has:

- **drone_id** — a human-readable name (e.g., "alpha", "bravo")
- **connection_string** — how to reach it (e.g., `tcp:127.0.0.1:5760` or `/dev/ttyUSB0`)
- **role** — what it does in the swarm (RECON, RELAY, STRIKE, DECOY)
- **status** — its current lifecycle state
- **capabilities** — what hardware it has (camera, compute, payload)

## Drone Status (State Machine)

Every drone moves through a lifecycle:

```
DISCONNECTED → CONNECTED → ARMED → AIRBORNE → RETURNING → LANDED
                                       ↓
                                     LOST (heartbeat timeout)
```

Transitions are enforced — you can't go from DISCONNECTED to AIRBORNE directly. The SDK validates every state change.

## Roles

Roles describe what a drone does in the mission. The orchestrator assigns missions based on role:

| Role | Purpose | Hardware Needed |
|------|---------|----------------|
| **RECON** | Surveillance, mapping, search | Camera (optional) |
| **RELAY** | Communications relay, signal repeater | None (any drone) |
| **STRIKE** | Terminal guidance to target | None (any drone) |
| **DECOY** | Distraction, electronic signature | None (any drone) |

Roles are software assignments — any drone can play any role. The orchestrator auto-assigns based on hardware capabilities.

## Missions

A mission is a sequence of waypoints or a pattern that one or more drones execute:

- **Formation** — drones maintain relative positions (V, line, grid, circle)
- **Sweep** — parallel coverage of an area (lawnmower pattern)
- **Patrol** — repeated circuit of waypoints
- **Follow** — one drone follows another at a fixed offset
- **Orbit** — circular path around a point

Missions run as background tasks. You can monitor progress, pause, resume, or cancel them.

## Telemetry

The SDK continuously reads MAVLink telemetry from each drone:

- Position (lat, lon, altitude)
- Heading and speed
- Battery voltage and percentage
- GPS fix quality
- Flight mode

Telemetry updates at 4-10 Hz depending on radio bandwidth.

## Safety

drone-swarm enforces safety at multiple levels:

1. **Preflight checks** — GPS lock, battery level, compass health, EKF status
2. **Geofencing** — virtual boundary that triggers RTL if breached
3. **Heartbeat monitoring** — detects lost drones within 15 seconds
4. **Low battery auto-RTL** — sends drones home before they fall out of the sky
5. **Emergency stop** — two-tier: controlled landing or motor kill (with confirmation)
6. **Collision avoidance** — minimum separation distance enforcement (planned for v0.5)

## MAVLink

drone-swarm communicates with drones using [MAVLink](https://mavlink.io/en/), the standard protocol for ArduPilot and PX4. You don't need to know MAVLink to use the SDK — it handles all protocol details internally.

If you do need low-level access, the raw `pymavlink` connection is available via `drone.connection`.

## Configuration

All swarm parameters can be configured via YAML or Python dict:

```yaml
# swarm.yaml
heartbeat_timeout_s: 15
battery_rtl_threshold: 20
default_altitude_m: 10
```

```python
from drone_swarm import Swarm, SwarmConfig

config = SwarmConfig.from_yaml("swarm.yaml")
swarm = Swarm(config=config)
```

See [Configuration Reference](../api/config.md) for all options.
