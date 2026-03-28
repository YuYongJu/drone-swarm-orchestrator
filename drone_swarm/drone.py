"""
Drone data model -- dataclasses for individual drones, roles, status, and capabilities.

Extracted from src/swarm.py to give each concept its own module.
"""

from dataclasses import dataclass, field
from enum import Enum


class DroneRole(Enum):
    """Operational role assigned to a drone in the swarm."""
    RECON = "recon"
    RELAY = "relay"
    STRIKE = "strike"
    DECOY = "decoy"


class DroneStatus(Enum):
    """State-machine states for a drone's lifecycle."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ARMED = "armed"
    AIRBORNE = "airborne"
    RETURNING = "returning"
    LANDED = "landed"
    LOST = "lost"


# Valid state transitions: source -> set of allowed destinations.
VALID_TRANSITIONS: dict[DroneStatus, set[DroneStatus]] = {
    DroneStatus.DISCONNECTED: {DroneStatus.CONNECTED},
    DroneStatus.CONNECTED:    {DroneStatus.ARMED, DroneStatus.DISCONNECTED},
    DroneStatus.ARMED: {
        DroneStatus.AIRBORNE, DroneStatus.CONNECTED, DroneStatus.DISCONNECTED,
    },
    DroneStatus.AIRBORNE:     {DroneStatus.RETURNING, DroneStatus.LOST},
    DroneStatus.RETURNING:    {DroneStatus.LANDED, DroneStatus.LOST},
    DroneStatus.LANDED:       {DroneStatus.CONNECTED, DroneStatus.DISCONNECTED},
    DroneStatus.LOST:         {DroneStatus.CONNECTED, DroneStatus.DISCONNECTED},
}


@dataclass
class Waypoint:
    """A GPS waypoint with latitude, longitude, and altitude (meters relative to home)."""
    lat: float
    lon: float
    alt: float

    def __post_init__(self):
        if not -90 <= self.lat <= 90:
            raise ValueError(f"lat must be in [-90, 90], got {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"lon must be in [-180, 180], got {self.lon}")



@dataclass
class DroneCapabilities:
    """Hardware capabilities for a drone, determining which roles it can fill."""
    hw_class: str = "A"           # A=Basic, B=Sensor, C=Compute, D=Payload
    has_camera: bool = False
    has_compute: bool = False
    has_payload: bool = False
    max_speed_ms: float = 5.0     # m/s
    max_altitude_m: float = 100.0
    endurance_min: float = 12.0   # estimated flight time


@dataclass
class Drone:
    """
    Represents a single drone in the swarm.

    Holds connection state, telemetry, mission waypoints, and hardware capabilities.
    """
    drone_id: str
    connection_string: str  # e.g. "udp:127.0.0.1:14550" or "/dev/ttyUSB0"
    role: DroneRole = DroneRole.RECON
    status: DroneStatus = DroneStatus.DISCONNECTED
    capabilities: DroneCapabilities = field(default_factory=DroneCapabilities)
    connection: object | None = field(default=None, repr=False)
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    heading: float = 0.0
    battery_pct: float = 100.0
    last_heartbeat: float = 0.0
    takeoff_time: float = 0.0
    _armed_from_heartbeat: bool = False
    mission: list[Waypoint] = field(default_factory=list)
    # Health scoring fields
    health_score: float = 100.0
    gps_satellite_count: int = 0
    vibration_level: float = -1.0  # max of x/y/z; -1 = no data
    message_loss_rate: float = -1.0  # 0.0-1.0 fraction; -1 = no data
    # Attitude fields (radians, from ATTITUDE MAVLink message)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    # Battery detail fields (from SYS_STATUS / BATTERY_STATUS)
    current_a: float = 0.0   # instantaneous current draw in amps
    voltage: float = 0.0     # battery voltage in volts
