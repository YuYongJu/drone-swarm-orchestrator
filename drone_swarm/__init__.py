"""
drone-swarm -- Python SDK for multi-drone swarm orchestration.

Quick start::

    from drone_swarm import Swarm, Drone

    swarm = Swarm()
    swarm.add("alpha", "udp:127.0.0.1:14550")
    swarm.add("bravo", "udp:127.0.0.1:14560")
    await swarm.connect()
    await swarm.takeoff(altitude=10)
    await swarm.formation("v", spacing=15)
    await swarm.sweep(bounds=[(lat1, lon1), (lat2, lon2)])
    await swarm.rtl()

Public API exports
------------------
- **Swarm** / **SwarmOrchestrator** -- main orchestrator class
- **Drone** -- drone data model
- **DroneRole** -- enum of operational roles (RECON, RELAY, STRIKE, DECOY)
- **DroneStatus** -- enum of lifecycle states
- **DroneCapabilities** -- hardware capability descriptor
- **Waypoint** -- GPS waypoint (lat, lon, alt)
- **SwarmConfig** -- configuration object (YAML/dict/defaults)
- **SimulationHarness** -- SITL multi-drone launcher
- **CheckResult** -- preflight check result
- Missions: **v_formation**, **line_formation**, **area_sweep**, **orbit_point**
- Safety: **run_preflight_checks**, **preflight_ok**
"""


from ._version import __version__

# Allocation (functions require scipy at call time, not import time)
from .allocation import optimal_assign, replan_optimal

# Anomaly detection
from .anomaly import Anomaly, AnomalyDetector

# Geofence
# Battery prediction
from .battery import BatteryConfig, BatteryPredictor

# Behavior plugin system
from .behavior import Behavior, BehaviorEvent, BehaviorRegistry

# Collision avoidance
from .collision import CollisionAvoidance, CollisionRisk, OrcaVelocity

# Configuration
from .config import SwarmConfig

# Core types
from .drone import (
    Drone,
    DroneCapabilities,
    DroneRole,
    DroneStatus,
    Waypoint,
)

# Flight logging
from .flight_log import FlightLog, FlightLogger, TelemetrySnapshot, load_flight_log

# Formation control
from .formation_control import (
    FormationController,
    FormationGains,
    compute_formation_error,
)
from .geofence import Geofence, GeofenceStatus

# Health scoring
from .health import compute_health_score

# Missions
from .missions import area_sweep, line_formation, orbit_point, polygon_sweep, v_formation

# Path planning
from .path_planner import PathPlanner, energy_cost, plan_multi_drone, smooth_trajectory

# Safety / preflight
from .safety import CheckResult, preflight_ok, run_preflight_checks

# Simulation
from .simulation import SimulationHarness, SITLNotFoundError, SITLStartupError

# Orchestrator (+ Swarm alias)
from .swarm import Swarm, SwarmOrchestrator

# Telemetry server
from .telemetry_server import TelemetryServer

# Visualization
from .viz import start_map_server

# Wind estimation
from .wind import WindEstimate, WindEstimator

__all__ = [
    # Anomaly detection
    "Anomaly",
    "AnomalyDetector",
    # Battery prediction
    "BatteryConfig",
    "BatteryPredictor",
    # Behavior plugin system
    "Behavior",
    "BehaviorEvent",
    "BehaviorRegistry",
    # Safety
    "CheckResult",
    # Collision avoidance
    "CollisionAvoidance",
    "CollisionRisk",
    # Core types
    "Drone",
    "DroneCapabilities",
    "DroneRole",
    "DroneStatus",
    # Flight logging
    "FlightLog",
    "FlightLogger",
    # Formation control
    "FormationController",
    "FormationGains",
    # Geofence
    "Geofence",
    "GeofenceStatus",
    "OrcaVelocity",
    # Path planning
    "PathPlanner",
    # Simulation errors
    "SITLNotFoundError",
    "SITLStartupError",
    # Simulation
    "SimulationHarness",
    # Orchestrator
    "Swarm",
    # Config
    "SwarmConfig",
    "SwarmOrchestrator",
    # Telemetry server
    "TelemetryServer",
    # Flight log
    "TelemetrySnapshot",
    "Waypoint",
    # Wind estimation
    "WindEstimate",
    "WindEstimator",
    # Version
    "__version__",
    # Missions
    "area_sweep",
    # Formation control (function)
    "compute_formation_error",
    # Health
    "compute_health_score",
    # Path planning (functions)
    "energy_cost",
    "line_formation",
    "load_flight_log",
    # Allocation
    "optimal_assign",
    "orbit_point",
    "plan_multi_drone",
    "polygon_sweep",
    "preflight_ok",
    "replan_optimal",
    "run_preflight_checks",
    "smooth_trajectory",
    "start_map_server",
    "v_formation",
]
