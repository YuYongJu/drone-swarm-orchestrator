# Changelog

All notable changes to drone-swarm will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

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
