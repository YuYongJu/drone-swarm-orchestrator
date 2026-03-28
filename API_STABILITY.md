# API Stability Contract

**Version:** 0.2.0
**Last Updated:** 2026-03-28

This document defines the stability guarantees for the `drone-swarm` SDK
public API. It helps you decide which parts of the SDK are safe to depend
on in production code versus which parts may change in future releases.

---

## Stability Tiers

### Stable

These APIs are covered by [semantic versioning](https://semver.org/).
Breaking changes will only happen in a new **major** version (e.g., 1.0 -> 2.0)
and will be preceded by at least one minor release with deprecation warnings.

### Provisional

These APIs are functional and tested, but their signatures or behavior
may change in a future **minor** release (e.g., 0.3.0). We will document
changes in the changelog and provide migration guidance.

### Internal

These are implementation details. Do not depend on them. They may change
or be removed in any release, including patches.

---

## API Reference by Tier

### Stable

These are the core building blocks most users need. They will not break
without a major version bump.

| Symbol | Module | Description |
|--------|--------|-------------|
| `Swarm` | `swarm` | Main orchestrator (alias for `SwarmOrchestrator`) |
| `SwarmOrchestrator` | `swarm` | Full orchestrator class |
| `Drone` | `drone` | Drone data model |
| `DroneRole` | `drone` | Role enum (RECON, RELAY, STRIKE, DECOY) |
| `DroneStatus` | `drone` | Lifecycle state enum |
| `DroneCapabilities` | `drone` | Hardware capability descriptor |
| `Waypoint` | `drone` | GPS waypoint (lat, lon, alt) |
| `SwarmConfig` | `config` | Configuration object (YAML/dict/defaults) |
| `CheckResult` | `safety` | Preflight check result |
| `run_preflight_checks` | `safety` | Run full preflight suite against a drone |
| `preflight_ok` | `safety` | Check if all preflight results passed |
| `Behavior` | `behavior` | Base class for behavior plugins |
| `BehaviorEvent` | `behavior` | Event dispatched to behaviors |
| `Geofence` | `geofence` | Polygon geofence with altitude limits |
| `GeofenceStatus` | `geofence` | Geofence check result enum |
| `CollisionAvoidance` | `collision` | Collision detection and avoidance |
| `CollisionRisk` | `collision` | Detected collision risk between two drones |
| `SimulationHarness` | `simulation` | SITL multi-drone launcher |
| `SITLNotFoundError` | `simulation` | Raised when SITL binary not found |
| `SITLStartupError` | `simulation` | Raised when SITL fails to start |
| `__version__` | `_version` | Package version string |

#### Stable SwarmOrchestrator Methods

| Method | Description |
|--------|-------------|
| `register_drone()` / `add()` | Register a drone |
| `connect_all()` / `connect()` | Connect to all drones |
| `takeoff()` | Take off one or all drones |
| `goto()` | Send a drone to a waypoint |
| `return_to_launch()` / `rtl()` | Return to launch |
| `land()` | Land a drone |
| `formation()` | Move drones into a formation |
| `sweep()` | Execute area sweep |
| `assign_mission()` | Assign waypoints to a drone |
| `execute_missions()` | Launch all assigned missions |
| `shutdown()` | Graceful shutdown |
| `emergency_land()` | Emergency controlled descent |
| `emergency_kill()` | Emergency motor kill (last resort) |
| `set_geofence()` / `clear_geofence()` | Geofence management |
| `enable_collision_avoidance()` / `disable_collision_avoidance()` | Collision avoidance |
| `add_behavior()` / `remove_behavior()` / `get_behavior()` | Behavior plugins |
| `status_report()` | Human-readable status |
| `simulate()` | Factory: create simulated swarm |

#### Stable Mission Functions

| Function | Description |
|----------|-------------|
| `v_formation()` | V-formation waypoints |
| `line_formation()` | Line formation waypoints |
| `area_sweep()` | Rectangular area sweep |
| `orbit_point()` | Circular orbit waypoints |

---

### Provisional

These APIs work and are tested, but their interfaces may evolve as we
gather real-world usage feedback. Pin your `drone-swarm` version if you
depend on these.

| Symbol | Module | Description | Notes |
|--------|--------|-------------|-------|
| `polygon_sweep` | `missions` | Arbitrary polygon sweep | Signature may gain options |
| `FormationController` | `formation_control` | Closed-loop formation hold | PID gains API may change |
| `FormationGains` | `formation_control` | PID gain parameters | Fields may be added |
| `compute_formation_error` | `formation_control` | Formation error measurement | Return type may change |
| `AnomalyDetector` | `anomaly` | Telemetry anomaly detection | Threshold API may change |
| `Anomaly` | `anomaly` | Detected anomaly record | Fields may be added |
| `BatteryPredictor` | `battery` | SOC estimation | Peukert model may evolve |
| `BatteryConfig` | `battery` | Battery parameters | Fields may be added |
| `WindEstimator` | `wind` | Tilt-based wind estimation | Calibration API may change |
| `WindEstimate` | `wind` | Wind vector result | Fields may be added |
| `PathPlanner` | `path_planner` | A* path planning | Grid API may change |
| `plan_multi_drone` | `path_planner` | Multi-drone deconflicted paths | Parameters may change |
| `smooth_trajectory` | `path_planner` | Cubic spline smoothing | |
| `energy_cost` | `path_planner` | Energy cost estimation | Model parameters may change |
| `FlightLogger` | `flight_log` | Telemetry recording behavior | Export format may evolve |
| `FlightLog` | `flight_log` | Loaded flight log data | |
| `TelemetrySnapshot` | `flight_log` | Single telemetry record | Fields may be added |
| `load_flight_log` | `flight_log` | Load exported JSON log | |
| `TelemetryServer` | `telemetry_server` | WebSocket telemetry broadcast | Wire format may evolve |
| `compute_health_score` | `health` | Composite health score | Weights may be tuned |
| `OrcaVelocity` | `collision` | ORCA velocity output | |
| `start_map_server` | `viz` | Web map visualization | |

#### Provisional SwarmOrchestrator Methods

| Method | Description | Notes |
|--------|-------------|-------|
| `enable_formation_hold()` / `disable_formation_hold()` | Formation correction | Gains API may change |
| `enable_path_planning()` / `disable_path_planning()` | A* routing | |
| `enable_anomaly_detection()` / `disable_anomaly_detection()` | Anomaly detection | |
| `rotate()` | Formation rotation animation | |
| `auto_assign_roles()` | Capability-based role assignment | |
| `replan_on_loss()` | Redistribute lost drone's mission | |
| `validate_role()` | Check role-capability fit | |
| `register_from_fleet()` | Auto-register from JSON files | |

---

### Internal

Do not depend on these. They are implementation details that may change
without notice.

| Symbol | Module | Notes |
|--------|--------|-------|
| `BehaviorRegistry` | `behavior` | Use `swarm.add_behavior()` instead |
| `optimal_assign` | `allocation` | Used internally by `replan_on_loss` |
| `replan_optimal` | `allocation` | Used internally by `replan_on_loss` |
| All `_`-prefixed attributes and methods | Various | Private by convention |
| `VALID_TRANSITIONS` | `drone` | State machine internals |

---

## Versioning Policy

Starting with v0.2.0, the `drone-swarm` SDK follows these rules:

- **Patch releases** (0.2.x): Bug fixes only. No API changes.
- **Minor releases** (0.x.0): May change Provisional APIs. Stable APIs
  are not changed. Changelog documents all changes with migration notes.
- **Major releases** (x.0.0): May change any API. Preceded by deprecation
  warnings in the prior minor release.

## Deprecation Process

1. The deprecated API is marked with a `DeprecationWarning` and documented
   in the changelog.
2. The replacement API is available in the same release.
3. The deprecated API is removed in the next **major** release (or after
   at least 2 minor releases for Provisional APIs).

---

## How to Read `__all__`

The `drone_swarm/__init__.py` file exports all Stable and Provisional
symbols in `__all__`. Internal symbols (`BehaviorRegistry`,
`optimal_assign`, `replan_optimal`) are still importable but are not
part of the supported API surface and may be removed from `__all__` in
a future release.

---

*This document is updated with each release. Check the version at the top
to ensure you're reading the correct edition.*
