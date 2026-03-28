"""
Path planning module -- A* pathfinding, trajectory smoothing, multi-drone
deconfliction, and energy cost estimation.

Implements Phase 1 recommendations from the literature review:
- A* global planner on a GPS grid with configurable resolution
- Cubic spline trajectory smoothing (scipy.interpolate)
- Temporal deconfliction via altitude staggering for multi-drone paths
- Energy cost model accounting for distance, altitude, and wind

References:
- Hart, Nilsson & Raphael (1968) -- A* algorithm
- Mellinger & Kumar (2011) -- minimum-snap trajectory concepts
- Energy-Optimal Planning of Waypoint-Based UAV Missions (arXiv:2410.17585)
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .drone import Drone, Waypoint

if TYPE_CHECKING:
    from .geofence import Geofence
    from .wind import WindEstimate

logger = logging.getLogger("drone_swarm.path_planner")

# Earth radius in metres (WGS-84 mean)
_EARTH_R = 6_371_000.0

# ---------------------------------------------------------------------------
# Coordinate helpers
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


def _metres_per_deg_lat() -> float:
    """Approximate metres per degree of latitude."""
    return _EARTH_R * math.pi / 180.0


def _metres_per_deg_lon(lat: float) -> float:
    """Approximate metres per degree of longitude at a given latitude."""
    return _EARTH_R * math.cos(math.radians(lat)) * math.pi / 180.0


def _offset_gps(
    lat: float, lon: float, north_m: float, east_m: float,
) -> tuple[float, float]:
    """Offset a GPS coordinate by metres north/east."""
    new_lat = lat + north_m / _metres_per_deg_lat()
    new_lon = lon + east_m / _metres_per_deg_lon(lat)
    return new_lat, new_lon


# ---------------------------------------------------------------------------
# A* Path Planner
# ---------------------------------------------------------------------------


@dataclass
class PathPlanner:
    """A* grid-based path planner for GPS waypoints.

    Parameters
    ----------
    resolution_m:
        Grid cell size in metres.  Default 5 m.
    geofence:
        Optional :class:`~drone_swarm.geofence.Geofence` to constrain paths.
    """

    resolution_m: float = 5.0
    geofence: Geofence | None = None

    # 8-connected grid neighbours (north, east offsets in cells)
    _NEIGHBOURS: list[tuple[int, int]] = field(
        default_factory=lambda: [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ],
        init=False,
        repr=False,
    )

    def plan_path(
        self,
        start: Waypoint,
        goal: Waypoint,
        obstacles: list[tuple[float, float, float]] | None = None,
    ) -> list[Waypoint]:
        """Plan a path from *start* to *goal* using A* on a GPS grid.

        Parameters
        ----------
        start:
            Starting waypoint.
        goal:
            Goal waypoint.
        obstacles:
            List of ``(lat, lon, radius_m)`` no-fly zones.

        Returns
        -------
        list[Waypoint]
            Ordered list of intermediate waypoints including start and goal.
            If no obstacles block the direct path, the list is ``[start, goal]``.
        """
        obstacles = obstacles or []

        # Check if the direct path is clear
        if self._direct_path_clear(start, goal, obstacles):
            return [start, goal]

        # Build a local grid centred on the midpoint between start and goal
        mid_lat = (start.lat + goal.lat) / 2
        mid_lon = (start.lon + goal.lon) / 2

        # Determine grid extent: enough to cover start-goal + margin
        dist = _haversine(start.lat, start.lon, goal.lat, goal.lon)
        # Add generous margin for detours
        margin = max(dist * 0.5, self.resolution_m * 10)
        extent = dist / 2 + margin

        # Convert start/goal to grid coordinates
        m_per_lat = _metres_per_deg_lat()
        m_per_lon = _metres_per_deg_lon(mid_lat)

        def to_grid(lat: float, lon: float) -> tuple[int, int]:
            north_m = (lat - mid_lat) * m_per_lat
            east_m = (lon - mid_lon) * m_per_lon
            row = round(north_m / self.resolution_m)
            col = round(east_m / self.resolution_m)
            return row, col

        def to_gps(row: int, col: int, alt: float) -> Waypoint:
            north_m = row * self.resolution_m
            east_m = col * self.resolution_m
            lat = mid_lat + north_m / m_per_lat
            lon = mid_lon + east_m / m_per_lon
            return Waypoint(lat=lat, lon=lon, alt=alt)

        def is_blocked(row: int, col: int) -> bool:
            wp = to_gps(row, col, start.alt)
            # Check obstacles
            for olat, olon, orad in obstacles:
                if _haversine(wp.lat, wp.lon, olat, olon) < orad:
                    return True
            # Check geofence
            return (
                self.geofence is not None
                and not self.geofence.contains(wp.lat, wp.lon, wp.alt)
            )

        start_cell = to_grid(start.lat, start.lon)
        goal_cell = to_grid(goal.lat, goal.lon)

        # Grid bounds (in cells)
        half_cells = int(extent / self.resolution_m) + 1

        def in_bounds(r: int, c: int) -> bool:
            sr, sc = start_cell
            gr, gc = goal_cell
            min_r = min(sr, gr) - half_cells
            max_r = max(sr, gr) + half_cells
            min_c = min(sc, gc) - half_cells
            max_c = max(sc, gc) + half_cells
            return min_r <= r <= max_r and min_c <= c <= max_c

        def heuristic(cell: tuple[int, int]) -> float:
            dr = (cell[0] - goal_cell[0]) * self.resolution_m
            dc = (cell[1] - goal_cell[1]) * self.resolution_m
            return math.hypot(dr, dc)

        # A* search
        open_set: list[tuple[float, tuple[int, int]]] = []
        heapq.heappush(open_set, (0.0, start_cell))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
        g_score: dict[tuple[int, int], float] = {start_cell: 0.0}

        found = False
        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal_cell:
                found = True
                break

            cr, cc = current
            for dr, dc in self._NEIGHBOURS:
                nr, nc = cr + dr, cc + dc
                neighbour = (nr, nc)

                if not in_bounds(nr, nc):
                    continue
                if is_blocked(nr, nc):
                    continue

                step_cost = self.resolution_m * math.hypot(dr, dc)
                tentative_g = g_score[current] + step_cost

                if tentative_g < g_score.get(neighbour, float("inf")):
                    came_from[neighbour] = current
                    g_score[neighbour] = tentative_g
                    f = tentative_g + heuristic(neighbour)
                    heapq.heappush(open_set, (f, neighbour))

        if not found:
            # Fallback: direct path if A* can't find a route
            logger.warning(
                "A* could not find a path from %s to %s; returning direct path",
                start, goal,
            )
            return [start, goal]

        # Reconstruct path
        path_cells: list[tuple[int, int]] = []
        cell: tuple[int, int] | None = goal_cell
        while cell is not None:
            path_cells.append(cell)
            cell = came_from.get(cell)
        path_cells.reverse()

        # Interpolate altitude linearly from start to goal
        total_cells = len(path_cells)
        waypoints: list[Waypoint] = []
        for i, (r, c) in enumerate(path_cells):
            frac = i / max(total_cells - 1, 1)
            alt = start.alt + frac * (goal.alt - start.alt)
            waypoints.append(to_gps(r, c, alt))

        # Replace first/last with exact start/goal
        waypoints[0] = start
        waypoints[-1] = goal

        return waypoints

    def _direct_path_clear(
        self,
        start: Waypoint,
        goal: Waypoint,
        obstacles: list[tuple[float, float, float]],
    ) -> bool:
        """Check whether the direct line from start to goal is obstacle-free."""
        if not obstacles and self.geofence is None:
            return True

        # Sample points along the line
        dist = _haversine(start.lat, start.lon, goal.lat, goal.lon)
        n_samples = max(int(dist / self.resolution_m), 10)

        for i in range(n_samples + 1):
            frac = i / n_samples
            lat = start.lat + frac * (goal.lat - start.lat)
            lon = start.lon + frac * (goal.lon - start.lon)
            alt = start.alt + frac * (goal.alt - start.alt)

            for olat, olon, orad in obstacles:
                if _haversine(lat, lon, olat, olon) < orad:
                    return False

            if self.geofence is not None and not self.geofence.contains(lat, lon, alt):
                return False

        return True


# ---------------------------------------------------------------------------
# Trajectory smoothing
# ---------------------------------------------------------------------------


def smooth_trajectory(
    waypoints: list[Waypoint],
    num_points: int = 20,
) -> list[Waypoint]:
    """Smooth a waypoint path using cubic spline interpolation.

    Takes a list of waypoints with sharp turns and produces a smooth
    curved trajectory with *num_points* output waypoints.

    Parameters
    ----------
    waypoints:
        Input waypoints (at least 2).
    num_points:
        Number of points in the output trajectory.  Default 20.

    Returns
    -------
    list[Waypoint]
        Smoothed trajectory of *num_points* waypoints.  First and last
        match the input start and goal.
    """
    if len(waypoints) < 2:
        return list(waypoints)

    if len(waypoints) == 2:
        # Linear interpolation for two-point paths
        result: list[Waypoint] = []
        for i in range(num_points):
            frac = i / max(num_points - 1, 1)
            result.append(Waypoint(
                lat=waypoints[0].lat + frac * (waypoints[1].lat - waypoints[0].lat),
                lon=waypoints[0].lon + frac * (waypoints[1].lon - waypoints[0].lon),
                alt=waypoints[0].alt + frac * (waypoints[1].alt - waypoints[0].alt),
            ))
        return result

    try:
        from scipy.interpolate import CubicSpline
    except ImportError:
        # Fallback: linear interpolation without scipy
        logger.warning("scipy not available; using linear interpolation for smoothing")
        return _linear_interpolate(waypoints, num_points)

    import numpy as np

    lats = np.array([wp.lat for wp in waypoints])
    lons = np.array([wp.lon for wp in waypoints])
    alts = np.array([wp.alt for wp in waypoints])

    # Parameterize by cumulative chord-length
    diffs = np.sqrt(np.diff(lats) ** 2 + np.diff(lons) ** 2)
    t = np.zeros(len(waypoints))
    t[1:] = np.cumsum(diffs)

    # Build cubic splines
    cs_lat = CubicSpline(t, lats, bc_type="clamped")
    cs_lon = CubicSpline(t, lons, bc_type="clamped")
    cs_alt = CubicSpline(t, alts, bc_type="clamped")

    t_smooth = np.linspace(t[0], t[-1], num_points)

    result = []
    for ti in t_smooth:
        result.append(Waypoint(
            lat=float(cs_lat(ti)),
            lon=float(cs_lon(ti)),
            alt=float(cs_alt(ti)),
        ))

    return result


def _linear_interpolate(
    waypoints: list[Waypoint], num_points: int,
) -> list[Waypoint]:
    """Fallback linear interpolation when scipy is unavailable."""
    if len(waypoints) < 2:
        return list(waypoints)

    # Compute cumulative distances
    cum_dist = [0.0]
    for i in range(1, len(waypoints)):
        d = _haversine(
            waypoints[i - 1].lat, waypoints[i - 1].lon,
            waypoints[i].lat, waypoints[i].lon,
        )
        cum_dist.append(cum_dist[-1] + d)

    total = cum_dist[-1]
    if total == 0:
        return [waypoints[0]] * num_points

    result: list[Waypoint] = []
    for i in range(num_points):
        target_dist = (i / max(num_points - 1, 1)) * total
        # Find segment
        for j in range(1, len(cum_dist)):
            if cum_dist[j] >= target_dist:
                seg_len = cum_dist[j] - cum_dist[j - 1]
                frac = 0.0 if seg_len == 0 else (target_dist - cum_dist[j - 1]) / seg_len
                result.append(Waypoint(
                    lat=waypoints[j - 1].lat + frac * (waypoints[j].lat - waypoints[j - 1].lat),
                    lon=waypoints[j - 1].lon + frac * (waypoints[j].lon - waypoints[j - 1].lon),
                    alt=waypoints[j - 1].alt + frac * (waypoints[j].alt - waypoints[j - 1].alt),
                ))
                break
        else:
            result.append(waypoints[-1])

    return result


# ---------------------------------------------------------------------------
# Multi-drone path planning
# ---------------------------------------------------------------------------


def plan_multi_drone(
    drones: dict[str, Drone],
    goals: dict[str, Waypoint],
    obstacles: list[tuple[float, float, float]] | None = None,
    resolution_m: float = 5.0,
    alt_stagger_m: float = 3.0,
    geofence: Geofence | None = None,
) -> dict[str, list[Waypoint]]:
    """Plan paths for multiple drones with temporal deconfliction.

    Uses altitude staggering to ensure drone paths do not conflict.
    Each drone is assigned a unique altitude offset so that even if
    horizontal paths cross, drones are vertically separated.

    Parameters
    ----------
    drones:
        Mapping of drone_id to :class:`Drone` instances with current
        positions (``lat``, ``lon``, ``alt``).
    goals:
        Mapping of drone_id to goal :class:`Waypoint`.
    obstacles:
        Optional list of ``(lat, lon, radius_m)`` no-fly zones.
    resolution_m:
        Grid resolution for the A* planner.
    alt_stagger_m:
        Vertical separation between drone paths in metres.
    geofence:
        Optional geofence constraint.

    Returns
    -------
    dict[str, list[Waypoint]]
        Mapping of drone_id to planned waypoint path.
    """
    planner = PathPlanner(resolution_m=resolution_m, geofence=geofence)
    result: dict[str, list[Waypoint]] = {}

    drone_ids = sorted(goals.keys())

    for idx, drone_id in enumerate(drone_ids):
        drone = drones[drone_id]
        goal = goals[drone_id]

        # Altitude stagger: each drone gets a unique offset
        alt_offset = idx * alt_stagger_m

        start = Waypoint(
            lat=drone.lat,
            lon=drone.lon,
            alt=drone.alt + alt_offset,
        )
        staggered_goal = Waypoint(
            lat=goal.lat,
            lon=goal.lon,
            alt=goal.alt + alt_offset,
        )

        path = planner.plan_path(start, staggered_goal, obstacles)
        result[drone_id] = path

    return result


# ---------------------------------------------------------------------------
# Energy cost estimation
# ---------------------------------------------------------------------------


# Default energy model parameters (typical ~1.5 kg quadrotor)
_HOVER_POWER_W = 80.0       # watts required to hover
_SPEED_MS = 5.0              # cruise speed in m/s
_CLIMB_EXTRA_W = 30.0        # extra watts per m/s of climb
_VOLTAGE = 11.1              # nominal 3S LiPo voltage


def energy_cost(
    path: list[Waypoint],
    wind: WindEstimate | None = None,
    hover_power_w: float = _HOVER_POWER_W,
    cruise_speed_ms: float = _SPEED_MS,
    climb_extra_w: float = _CLIMB_EXTRA_W,
    voltage: float = _VOLTAGE,
) -> float:
    """Estimate energy cost of flying a path, in milliamp-hours (mAh).

    Parameters
    ----------
    path:
        List of waypoints defining the path.
    wind:
        Optional :class:`~drone_swarm.wind.WindEstimate`.  Headwind
        increases energy cost; tailwind decreases it.
    hover_power_w:
        Power draw in watts during hover / level flight.
    cruise_speed_ms:
        Cruise ground speed in m/s.
    climb_extra_w:
        Additional power per m/s of climb rate.
    voltage:
        Battery voltage (used to convert watts to amps).

    Returns
    -------
    float
        Estimated energy cost in mAh.
    """
    if len(path) < 2:
        return 0.0

    total_energy_wh = 0.0

    for i in range(1, len(path)):
        wp_prev = path[i - 1]
        wp_curr = path[i]

        # Horizontal distance
        horiz_dist = _haversine(wp_prev.lat, wp_prev.lon, wp_curr.lat, wp_curr.lon)

        # Vertical change
        dalt = wp_curr.alt - wp_prev.alt

        # 3D distance
        dist_3d = math.sqrt(horiz_dist ** 2 + dalt ** 2)

        # Effective ground speed (adjusted for wind)
        effective_speed = cruise_speed_ms
        if wind is not None and wind.speed_ms > 0:
            # Compute heading of this segment
            dlat = wp_curr.lat - wp_prev.lat
            dlon = wp_curr.lon - wp_prev.lon
            seg_heading_rad = math.atan2(dlon, dlat)
            # Wind direction is "from" in meteorological convention
            wind_rad = math.radians(wind.direction_deg)
            # Headwind component (positive = headwind)
            headwind = wind.speed_ms * math.cos(wind_rad - seg_heading_rad)
            effective_speed = max(cruise_speed_ms - headwind, 1.0)

        # Flight time for this segment
        flight_time_s = dist_3d / effective_speed if effective_speed > 0 else 0.0

        # Power: base hover + climb penalty
        power_w = hover_power_w
        if dalt > 0 and flight_time_s > 0:
            climb_rate = dalt / flight_time_s
            power_w += climb_extra_w * climb_rate

        # Energy in watt-hours
        energy_wh = power_w * (flight_time_s / 3600.0)
        total_energy_wh += energy_wh

    # Convert Wh to mAh:  mAh = Wh / V * 1000
    return (total_energy_wh / voltage) * 1000.0
