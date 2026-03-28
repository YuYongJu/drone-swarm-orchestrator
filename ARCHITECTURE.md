# Architecture

This document explains how the drone-swarm SDK is organized and how its components interact.

## Module Map

```
drone_swarm/
  swarm.py            Core orchestrator — manages N drones, dispatches commands
  drone.py            Data model — Drone, DroneStatus, Waypoint, state machine
  telemetry.py        Async telemetry loop — reads MAVLink, runs safety hooks
  collision.py        Collision avoidance — ORCA algorithm + repulsive fallback
  geofence.py         Polygon geofence — ray-casting containment + buffer zones
  path_planner.py     A* pathfinding — obstacle avoidance, trajectory smoothing
  missions.py         Formation patterns — V, line, orbit, area sweep
  formation_control.py  Closed-loop formation hold — PID corrections
  allocation.py       Task assignment — Hungarian algorithm (requires scipy)
  safety.py           Preflight checks + emergency procedures
  health.py           Drone health scoring (battery, GPS, vibration, comms)
  anomaly.py          Statistical anomaly detection across the swarm
  battery.py          Battery discharge prediction
  wind.py             Wind speed/direction estimation from drift
  simulation.py       SITL launcher — spins up ArduPilot instances for testing
  config.py           SwarmConfig dataclass with YAML loading
  geo.py              Shared GPS math — haversine, coordinate offsets
  viz.py              Real-time map visualization server
  benchmarks.py       Performance benchmark framework
  cli.py              CLI entry point (dso command)
```

## Data Flow

```
User Code
    |
    v
SwarmOrchestrator  (swarm.py)
    |
    |-- register_drone() --> Drone dataclass  (drone.py)
    |-- connect_all()    --> pymavlink MAVLink connections
    |-- takeoff/goto/land/rtl --> MAVLink command_long_send
    |-- formation()      --> missions.py generates waypoints
    |-- assign_mission() --> stores waypoints on Drone.mission
    |-- execute_missions() --> spawns async _run_mission tasks
    |
    v
Telemetry Loop  (telemetry.py, runs at ~10 Hz)
    |
    |-- read_telemetry()    Read GPS, battery, heartbeat from each drone
    |-- Heartbeat monitor   Mark LOST after 15s silence, trigger replan
    |-- Battery auto-RTL    RTL when battery < 20%
    |-- Geofence check      (geofence.py) Breach -> RTL/land/warn
    |-- Collision avoidance  (collision.py) ORCA velocities -> override gotos
    |-- Formation hold       (formation_control.py) PID corrections
    |-- Anomaly detection    (anomaly.py) Flag statistical outliers
    |-- Health scoring       (health.py) Composite 0-100 score
```

## State Machine

Each drone follows this lifecycle. Invalid transitions are blocked by `_transition()`.

```
DISCONNECTED --> CONNECTED --> ARMED --> AIRBORNE --+--> RETURNING --> LANDED
                    ^                               |
                    |                               +--> LANDING ----> LANDED
                    |                               |
                    +-- LANDED <--------------------+
                    |                               |
                    +-- LOST <----------------------+
                    |     |
                    +-----+  (recovery)
```

- **RETURNING**: drone is flying back to its launch point (RTL mode)
- **LANDING**: drone is descending in place (LAND mode)
- **LOST**: heartbeat timeout — the orchestrator redistributes its mission

## Async Model

The SDK is fully async (Python `asyncio`). Key concurrent tasks:

1. **Telemetry loop** — single `asyncio.Task` reads all drones in round-robin
2. **Mission tasks** — one `asyncio.Task` per drone executing its waypoint sequence
3. **Per-drone locks** — `asyncio.Lock` per drone prevents concurrent state mutations
4. **Pause/restart** — telemetry loop is paused during arm/takeoff (MAVLink reads race)

## Safety Priority

When multiple systems want to control a drone, safety wins:

```
Emergency kill  >  Emergency land  >  Collision avoidance  >  Geofence RTL  >  Mission gotos
```

Collision avoidance sets a time-based override (`_collision_override_until`) on each drone.
Mission execution checks this before sending gotos and yields until the override expires.

## Optional Dependencies

| Feature | Package | Install extra |
|---------|---------|---------------|
| Optimal task allocation | scipy, numpy | `pip install drone-swarm[allocation]` |
| YAML config loading | pyyaml | `pip install drone-swarm[yaml]` |
| Trajectory smoothing | scipy | `pip install drone-swarm[allocation]` |
| SITL simulation | pyyaml | `pip install drone-swarm[sim]` |

The SDK is always importable without optional dependencies. Functions that need
them raise `ImportError` with a clear install instruction at call time.
