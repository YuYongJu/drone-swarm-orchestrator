# Changelog

All notable changes to drone-swarm will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-03-28

### Fixed

- **State machine:** Added `LANDING` state so `land()` no longer misuses `RETURNING` (P2-1)
- **Geofence:** Ray-casting now operates in local metres, fixing distortion at high latitudes (P2-2)
- **Path planner:** A* now uses a closed set, preventing re-expansion of visited nodes (P2-5)
- **Path planner:** Obstacle check pre-computes blocked grid cells for O(1) per expansion (P2-10)
- **Collision avoidance:** Added time-based override so avoidance gotos take priority over mission gotos (P2-7)
- **Collision avoidance:** Spatial grid index for O(n) expected performance on 50+ drone swarms (P2-9)
- **Safety:** `run_preflight_checks()` raises clear `ImportError` when pymavlink is missing (P3-5)
- **Geo utilities:** `meters_per_deg_lon()` clamped near poles to avoid near-zero return (P3-9)
- **Formation control:** PID D-term normalized by dt, I-term multiplied by dt (P3-10)
- **Package init:** Removed misleading `contextlib.suppress` around allocation import (P3-2)

### Changed

- Telemetry heartbeat timeout now also monitors drones in `LANDING` state
- Emergency land sets drones to `LANDING` (not `RETURNING`)
- Shutdown procedure includes `LANDING` drones for RTL

## [0.1.0] - 2026-03-27

### Added

- Core `Swarm` class with async drone coordination
- `Drone`, `DroneRole`, `DroneStatus`, `DroneCapabilities`, `Waypoint` data models
- Flight commands: takeoff, land, RTL, goto, arm/disarm
- Formation patterns: V-formation, line, area sweep, orbit
- Telemetry reader with heartbeat monitoring
- Battery auto-RTL with grace period
- Dynamic replanning on drone loss
- Two-tier emergency stop (land + motor kill with confirmation)
- `SwarmConfig` with YAML support
- `SimulationHarness` for SITL multi-drone testing
- Preflight safety checks
- 4 example scripts (basic, formation, sweep, simulate)
- MkDocs Material documentation site
- PyPI packaging via pyproject.toml
