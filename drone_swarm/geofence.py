"""
Geofence enforcement -- NASA PolyCARP-inspired point-in-polygon containment.

Provides a ``Geofence`` class that uses ray-casting for containment tests and
computes distance-to-boundary for buffer-zone warnings. Designed to integrate
with the telemetry loop so every airborne drone is checked each cycle.
"""

from __future__ import annotations

import logging
import math
from enum import Enum

from .drone import Drone

logger = logging.getLogger("drone_swarm.geofence")

# Earth radius in metres (WGS-84 mean)
_EARTH_R = 6_371_000.0


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class GeofenceStatus(Enum):
    """Result of checking a drone against the geofence."""
    INSIDE = "inside"
    WARNING = "warning"
    BREACH = "breach"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two GPS points."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return _EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_to_segment_distance(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """
    Minimum distance from point (px, py) to segment (ax, ay)-(bx, by).

    Works in a local Cartesian frame (metres). Returns distance in the same
    units as the inputs.
    """
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        # Degenerate segment (a == b)
        return math.hypot(px - ax, py - ay)

    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _to_local_metres(
    lat: float, lon: float, ref_lat: float, ref_lon: float,
) -> tuple[float, float]:
    """Convert (lat, lon) to local (north_m, east_m) relative to a reference."""
    north = (lat - ref_lat) * (_EARTH_R * math.pi / 180.0)
    east = (lon - ref_lon) * (
        _EARTH_R * math.cos(math.radians(ref_lat)) * math.pi / 180.0
    )
    return north, east


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class Geofence:
    """
    Polygon geofence with altitude limits and buffer-zone warnings.

    Uses the ray-casting algorithm for point-in-polygon containment and
    computes distance-to-boundary for the warning buffer zone.

    Parameters
    ----------
    polygon:
        List of ``(lat, lon)`` vertices defining the fence boundary.
        The polygon is automatically closed (last vertex connects to first).
    alt_max_m:
        Maximum allowed altitude in metres AGL.
    alt_min_m:
        Minimum allowed altitude in metres AGL.
    buffer_fraction:
        Fraction of the distance from centroid to boundary that defines
        the warning zone. Default 0.20 means warn when within 20% of
        the boundary.
    """

    def __init__(
        self,
        polygon: list[tuple[float, float]],
        alt_max_m: float = 120.0,
        alt_min_m: float = 0.0,
        buffer_fraction: float = 0.20,
    ) -> None:
        if len(polygon) < 3:
            raise ValueError("Geofence polygon must have at least 3 vertices")
        self.polygon = list(polygon)
        self.alt_max_m = alt_max_m
        self.alt_min_m = alt_min_m
        self.buffer_fraction = buffer_fraction

        # Pre-compute reference point (centroid) for local-frame conversions
        self._ref_lat = sum(p[0] for p in polygon) / len(polygon)
        self._ref_lon = sum(p[1] for p in polygon) / len(polygon)

        # Pre-compute polygon vertices in local metres
        self._local_verts: list[tuple[float, float]] = [
            _to_local_metres(p[0], p[1], self._ref_lat, self._ref_lon)
            for p in self.polygon
        ]

    # -- Containment --------------------------------------------------------

    def contains(self, lat: float, lon: float, alt: float) -> bool:
        """
        Return ``True`` if the point is inside the geofence volume.

        Checks both the 2-D polygon (ray-casting) and altitude bounds.
        """
        if alt < self.alt_min_m or alt > self.alt_max_m:
            return False
        return self._point_in_polygon(lat, lon)

    def _point_in_polygon(self, lat: float, lon: float) -> bool:
        """Ray-casting point-in-polygon test."""
        n = len(self.polygon)
        inside = False
        x, y = lat, lon
        j = n - 1
        for i in range(n):
            xi, yi = self.polygon[i]
            xj, yj = self.polygon[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i
        return inside

    # -- Distance to boundary -----------------------------------------------

    def distance_to_boundary(self, lat: float, lon: float) -> float:
        """
        Distance in metres from the point to the nearest fence edge.

        Uses a local Cartesian approximation (accurate for small geofences).
        """
        px, py = _to_local_metres(lat, lon, self._ref_lat, self._ref_lon)
        min_dist = float("inf")
        n = len(self._local_verts)
        for i in range(n):
            ax, ay = self._local_verts[i]
            bx, by = self._local_verts[(i + 1) % n]
            d = _point_to_segment_distance(px, py, ax, ay, bx, by)
            if d < min_dist:
                min_dist = d
        return min_dist

    # -- Drone check --------------------------------------------------------

    def check_drone(self, drone: Drone) -> GeofenceStatus:
        """
        Check a drone's position against this geofence.

        Returns
        -------
        GeofenceStatus.INSIDE
            Drone is safely inside the fence and not in the buffer zone.
        GeofenceStatus.WARNING
            Drone is inside but within the buffer zone (20% of boundary).
        GeofenceStatus.BREACH
            Drone is outside the polygon or violating altitude limits.
        """
        # Altitude check
        if drone.alt < self.alt_min_m or drone.alt > self.alt_max_m:
            return GeofenceStatus.BREACH

        # Polygon containment
        if not self._point_in_polygon(drone.lat, drone.lon):
            return GeofenceStatus.BREACH

        # Buffer zone check: warn if close to boundary
        dist = self.distance_to_boundary(drone.lat, drone.lon)

        # Compute a representative "radius" as the max distance from centroid
        # to any vertex, then use buffer_fraction of that as warning threshold.
        max_radius = 0.0
        cx, cy = _to_local_metres(
            self._ref_lat, self._ref_lon, self._ref_lat, self._ref_lon,
        )  # (0, 0)
        for vx, vy in self._local_verts:
            r = math.hypot(vx - cx, vy - cy)
            if r > max_radius:
                max_radius = r

        warning_threshold = max_radius * self.buffer_fraction
        if dist < warning_threshold:
            return GeofenceStatus.WARNING

        return GeofenceStatus.INSIDE
