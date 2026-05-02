"""
Fluent Mission Builder -- compose, validate, serialize, and distribute missions.

Provides a builder-pattern API for constructing missions declaratively::

    from drone_swarm.mission_builder import Mission

    mission = (
        Mission.build("Pipeline Inspection Run 47")
        .add_waypoint(35.363, -117.669, alt=20)
        .add_waypoint(35.365, -117.665, alt=20)
        .set_formation("line", spacing=10)
        .set_geofence(
            polygon=[(35.36, -117.67), (35.37, -117.67),
                     (35.37, -117.66), (35.36, -117.66)],
            alt_max=50,
        )
        .set_speed(5.0)
        .on_complete("rtl")
        .validate()
    )

    mission.save_json("missions/pipeline_47.json")
    loaded = Mission.load_json("missions/pipeline_47.json")
    waypoint_sets = mission.generate_waypoints(num_drones=3)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .drone import Waypoint

# ---------------------------------------------------------------------------
# Valid values
# ---------------------------------------------------------------------------

_VALID_FORMATIONS = {"v", "line", "circle", "none"}
_VALID_ON_COMPLETE = {"rtl", "land", "loiter"}

# ---------------------------------------------------------------------------
# Internal data containers
# ---------------------------------------------------------------------------


@dataclass
class _WaypointEntry:
    """Internal waypoint representation with lat/lon/alt."""
    lat: float
    lon: float
    alt: float

    def to_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lon": self.lon, "alt": self.alt}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _WaypointEntry:
        return cls(lat=float(data["lat"]), lon=float(data["lon"]), alt=float(data["alt"]))


@dataclass
class _FormationConfig:
    """Formation configuration."""
    pattern: str = "none"
    spacing: float = 15.0
    heading: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "spacing": self.spacing, "heading": self.heading}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _FormationConfig:
        return cls(
            pattern=str(data.get("pattern", "none")),
            spacing=float(data.get("spacing", 15.0)),
            heading=float(data.get("heading", 0.0)),
        )


@dataclass
class _GeofenceConfig:
    """Geofence boundary configuration."""
    polygon: list[tuple[float, float]] = field(default_factory=list)
    alt_max: float = 120.0
    alt_min: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "polygon": [[lat, lon] for lat, lon in self.polygon],
            "alt_max": self.alt_max,
            "alt_min": self.alt_min,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _GeofenceConfig:
        polygon = [(float(p[0]), float(p[1])) for p in data.get("polygon", [])]
        return cls(
            polygon=polygon,
            alt_max=float(data.get("alt_max", 120.0)),
            alt_min=float(data.get("alt_min", 0.0)),
        )


# ---------------------------------------------------------------------------
# Mission class (the built, immutable-ish result)
# ---------------------------------------------------------------------------


class Mission:
    """
    A validated drone swarm mission.

    Use :meth:`build` to obtain a :class:`MissionBuilder`, then call
    :meth:`MissionBuilder.validate` to produce a ``Mission``.

    The ``Mission`` can be serialized to/from JSON and can generate
    per-drone waypoint assignments via :meth:`generate_waypoints`.
    """

    def __init__(
        self,
        name: str,
        waypoints: list[_WaypointEntry],
        formation: _FormationConfig | None = None,
        geofence: _GeofenceConfig | None = None,
        speed_ms: float | None = None,
        complete_action: str | None = None,
    ) -> None:
        self.name = name
        self.waypoints = list(waypoints)
        self.formation = formation or _FormationConfig()
        self.geofence = geofence
        self.speed_ms = speed_ms
        self.complete_action = complete_action

    # -- Factory / builder entry point -------------------------------------

    @classmethod
    def build(cls, name: str) -> MissionBuilder:
        """Return a :class:`MissionBuilder` for the named mission."""
        return MissionBuilder(name)

    # -- Serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mission to a plain dictionary."""
        data: dict[str, Any] = {
            "name": self.name,
            "waypoints": [wp.to_dict() for wp in self.waypoints],
            "formation": self.formation.to_dict(),
        }
        if self.geofence is not None:
            data["geofence"] = self.geofence.to_dict()
        if self.speed_ms is not None:
            data["speed_ms"] = self.speed_ms
        if self.complete_action is not None:
            data["complete_action"] = self.complete_action
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Mission:
        """Deserialize a mission from a plain dictionary."""
        waypoints = [_WaypointEntry.from_dict(wp) for wp in data.get("waypoints", [])]
        formation = _FormationConfig.from_dict(data["formation"]) if "formation" in data else None
        geofence = _GeofenceConfig.from_dict(data["geofence"]) if "geofence" in data else None
        return cls(
            name=data["name"],
            waypoints=waypoints,
            formation=formation,
            geofence=geofence,
            speed_ms=data.get("speed_ms"),
            complete_action=data.get("complete_action"),
        )

    def save_json(self, path: str) -> None:
        """Write the mission to a JSON file, creating parent directories if needed."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: str) -> Mission:
        """Load a mission from a JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    # -- Waypoint generation -----------------------------------------------

    def generate_waypoints(self, num_drones: int) -> list[list[Waypoint]]:
        """
        Distribute the mission's waypoints across *num_drones* drones.

        If a geofence polygon is defined and the formation is ``"none"``,
        the polygon is swept using a boustrophedon (lawnmower) pattern via
        :func:`~drone_swarm.missions.polygon_sweep`.

        For formation-based missions (``v``, ``line``, ``circle``), the first
        waypoint is used as the center point, and the corresponding formation
        helper generates per-drone positions along each mission waypoint.

        For simple waypoint missions with no formation, waypoints are
        distributed round-robin across drones.
        """
        if num_drones <= 0:
            return []

        pattern = self.formation.pattern if self.formation else "none"

        # Formation-based generation
        if pattern != "none" and self.waypoints:
            return self._generate_formation(num_drones, pattern)

        # Geofence polygon sweep (when geofence is defined and no specific formation)
        if self.geofence and self.geofence.polygon and len(self.geofence.polygon) >= 3:
            return self._generate_polygon_sweep(num_drones)

        # Default: round-robin distribution of waypoints
        return self._distribute_round_robin(num_drones)

    def _generate_formation(self, num_drones: int, pattern: str) -> list[list[Waypoint]]:
        """Generate formation-based waypoints along the mission path."""
        from .missions import line_formation, orbit_point, v_formation

        spacing = self.formation.spacing if self.formation else 15.0
        heading = self.formation.heading if self.formation else 0.0

        # Initialize per-drone waypoint lists
        missions: list[list[Waypoint]] = [[] for _ in range(num_drones)]

        for wp in self.waypoints:
            if pattern == "v":
                positions = v_formation(
                    wp.lat, wp.lon, wp.alt, num_drones=num_drones,
                    spacing_m=spacing, heading_deg=heading,
                )
            elif pattern == "line":
                positions = line_formation(
                    wp.lat, wp.lon, wp.alt, num_drones=num_drones,
                    spacing_m=spacing, heading_deg=heading,
                )
            elif pattern == "circle":
                positions = orbit_point(
                    wp.lat, wp.lon, wp.alt, num_drones=num_drones,
                    points_per_orbit=1,
                )
            else:
                # Unknown formation -- single waypoint for each drone
                positions = [[Waypoint(wp.lat, wp.lon, wp.alt)]] * num_drones

            for i in range(num_drones):
                if i < len(positions):
                    missions[i].extend(positions[i])

        return missions

    def _generate_polygon_sweep(self, num_drones: int) -> list[list[Waypoint]]:
        """Sweep the geofence polygon with a lawnmower pattern."""
        from .missions import polygon_sweep

        alt = self.waypoints[0].alt if self.waypoints else 20.0
        return polygon_sweep(
            self.geofence.polygon,  # type: ignore[union-attr]
            altitude=alt,
            num_drones=num_drones,
        )

    def _distribute_round_robin(self, num_drones: int) -> list[list[Waypoint]]:
        """Distribute waypoints round-robin across drones."""
        missions: list[list[Waypoint]] = [[] for _ in range(num_drones)]
        for i, wp in enumerate(self.waypoints):
            drone_idx = i % num_drones
            missions[drone_idx].append(Waypoint(wp.lat, wp.lon, wp.alt))
        return missions

    def __repr__(self) -> str:
        return (
            f"Mission(name={self.name!r}, waypoints={len(self.waypoints)}, "
            f"formation={self.formation.pattern!r})"
        )


# ---------------------------------------------------------------------------
# MissionBuilder -- fluent builder that produces a Mission
# ---------------------------------------------------------------------------


class MissionBuilder:
    """
    Chainable builder for constructing a :class:`Mission`.

    Obtain an instance via ``Mission.build("name")``.
    Call :meth:`validate` when done to get the final ``Mission``.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._waypoints: list[_WaypointEntry] = []
        self._formation: _FormationConfig = _FormationConfig()
        self._geofence: _GeofenceConfig | None = None
        self._speed_ms: float | None = None
        self._complete_action: str | None = None

    # -- Chainable setters -------------------------------------------------

    def add_waypoint(self, lat: float, lon: float, alt: float = 20.0) -> MissionBuilder:
        """Append a waypoint. Returns self for chaining."""
        if not -90 <= lat <= 90:
            raise ValueError(f"lat must be in [-90, 90], got {lat}")
        if not -180 <= lon <= 180:
            raise ValueError(f"lon must be in [-180, 180], got {lon}")
        if alt < 0:
            raise ValueError(f"alt must be >= 0, got {alt}")
        self._waypoints.append(_WaypointEntry(lat=lat, lon=lon, alt=alt))
        return self

    def set_formation(
        self,
        pattern: str,
        spacing: float = 15.0,
        heading: float = 0.0,
    ) -> MissionBuilder:
        """Set the formation pattern. Returns self for chaining."""
        pattern = pattern.lower()
        if pattern not in _VALID_FORMATIONS:
            raise ValueError(
                f"Invalid formation pattern {pattern!r}. "
                f"Must be one of {sorted(_VALID_FORMATIONS)}"
            )
        self._formation = _FormationConfig(pattern=pattern, spacing=spacing, heading=heading)
        return self

    def set_geofence(
        self,
        polygon: list[tuple[float, float]],
        alt_max: float = 120.0,
        alt_min: float = 0.0,
    ) -> MissionBuilder:
        """Set the geofence boundary. Returns self for chaining."""
        if len(polygon) < 3:
            raise ValueError("Geofence polygon must have at least 3 vertices")
        if alt_max <= alt_min:
            raise ValueError(f"alt_max ({alt_max}) must be greater than alt_min ({alt_min})")
        for lat, lon in polygon:
            if not -90 <= lat <= 90:
                raise ValueError(f"Geofence vertex lat must be in [-90, 90], got {lat}")
            if not -180 <= lon <= 180:
                raise ValueError(f"Geofence vertex lon must be in [-180, 180], got {lon}")
        self._geofence = _GeofenceConfig(polygon=list(polygon), alt_max=alt_max, alt_min=alt_min)
        return self

    def set_speed(self, speed_ms: float) -> MissionBuilder:
        """Set target speed in m/s. Returns self for chaining."""
        if speed_ms <= 0:
            raise ValueError(f"speed_ms must be positive, got {speed_ms}")
        self._speed_ms = speed_ms
        return self

    def on_complete(self, action: str) -> MissionBuilder:
        """Set the completion action: 'rtl', 'land', or 'loiter'. Returns self for chaining."""
        action = action.lower()
        if action not in _VALID_ON_COMPLETE:
            raise ValueError(
                f"Invalid on_complete action {action!r}. "
                f"Must be one of {sorted(_VALID_ON_COMPLETE)}"
            )
        self._complete_action = action
        return self

    # -- Validation and build ----------------------------------------------

    def validate(self) -> Mission:
        """
        Validate the builder state and return a :class:`Mission`.

        Raises :class:`ValueError` if the mission configuration is invalid.
        """
        if not self._name or not self._name.strip():
            raise ValueError("Mission name must not be empty")

        if not self._waypoints:
            raise ValueError("Mission must have at least one waypoint")

        # Validate geofence contains waypoints (if geofence is set)
        if self._geofence and self._geofence.polygon:
            for wp in self._waypoints:
                if wp.alt > self._geofence.alt_max:
                    raise ValueError(
                        f"Waypoint altitude {wp.alt}m exceeds geofence "
                        f"alt_max of {self._geofence.alt_max}m"
                    )
                if wp.alt < self._geofence.alt_min:
                    raise ValueError(
                        f"Waypoint altitude {wp.alt}m is below geofence "
                        f"alt_min of {self._geofence.alt_min}m"
                    )

        return Mission(
            name=self._name,
            waypoints=list(self._waypoints),
            formation=self._formation,
            geofence=self._geofence,
            speed_ms=self._speed_ms,
            complete_action=self._complete_action,
        )
