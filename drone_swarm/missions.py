"""
Mission planner -- generates waypoint sequences for common swarm patterns.

Feed the output into ``SwarmOrchestrator.assign_mission()`` or use the
high-level ``Swarm`` helpers (``swarm.formation()``, ``swarm.sweep()``).

Moved from src/mission_planner.py with the import path updated to use the
SDK's own :class:`~drone_swarm.drone.Waypoint`.
"""

import math

from .drone import Waypoint

# ---------------------------------------------------------------------------
# Helpers for GPS coordinate math
# ---------------------------------------------------------------------------

_METERS_PER_DEG_LAT = 111_320.0


def _meters_per_deg_lon(lat: float) -> float:
    """Meters per degree of longitude at the given latitude."""
    return _METERS_PER_DEG_LAT * math.cos(math.radians(lat))


def _offset_gps(
    lat: float, lon: float, north_m: float, east_m: float,
) -> tuple[float, float]:
    """Return ``(new_lat, new_lon)`` after offsetting by meters."""
    new_lat = lat + north_m / _METERS_PER_DEG_LAT
    new_lon = lon + east_m / _meters_per_deg_lon(lat)
    return new_lat, new_lon


# ---------------------------------------------------------------------------
# Polygon geometry helpers (all in a local meters frame)
# ---------------------------------------------------------------------------

def _polygon_to_local(
    polygon: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], float, float]:
    """
    Convert GPS polygon to local (east_m, north_m) frame centred on the centroid.

    Returns ``(local_points, centroid_lat, centroid_lon)``.
    """
    clat = sum(p[0] for p in polygon) / len(polygon)
    clon = sum(p[1] for p in polygon) / len(polygon)
    mlon = _meters_per_deg_lon(clat)
    local = [
        ((p[1] - clon) * mlon, (p[0] - clat) * _METERS_PER_DEG_LAT)
        for p in polygon
    ]
    return local, clat, clon


def _local_to_gps(
    x: float, y: float, clat: float, clon: float,
) -> tuple[float, float]:
    """Convert local (east, north) meters back to (lat, lon)."""
    lat = clat + y / _METERS_PER_DEG_LAT
    lon = clon + x / _meters_per_deg_lon(clat)
    return lat, lon


def _polygon_edge_x_at_y(
    p1: tuple[float, float], p2: tuple[float, float], y: float,
) -> float | None:
    """Return x coordinate where the edge crosses the given y, or None."""
    (x1, y1), (x2, y2) = p1, p2
    if (y1 <= y < y2) or (y2 <= y < y1):
        t = (y - y1) / (y2 - y1)
        return x1 + t * (x2 - x1)
    return None


def _sweep_line_intersections(
    polygon: list[tuple[float, float]], y: float,
) -> list[float]:
    """Return sorted x-intersections of *polygon* at sweep-line *y*."""
    xs: list[float] = []
    n = len(polygon)
    for i in range(n):
        x = _polygon_edge_x_at_y(polygon[i], polygon[(i + 1) % n], y)
        if x is not None:
            xs.append(x)
    xs.sort()
    return xs


def _optimal_heading_deg(polygon: list[tuple[float, float]]) -> float:
    """
    Choose sweep heading that minimizes the number of turns.

    We test headings from 0 to 179 degrees and pick the one where the
    polygon's extent perpendicular to the heading is maximized (longest
    sweep lines = fewest turns).  For simplicity we work in the local
    metre frame.
    """
    best_heading = 0.0
    best_extent = 0.0

    for deg in range(0, 180, 5):
        rad = math.radians(deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Project all points onto the axis *perpendicular* to the heading
        perp_vals = [x * (-sin_a) + y * cos_a for x, y in polygon]
        extent = max(perp_vals) - min(perp_vals)
        if extent > best_extent:
            best_extent = extent
            best_heading = deg

    return best_heading


def _rotate_polygon(
    polygon: list[tuple[float, float]], angle_rad: float,
) -> list[tuple[float, float]]:
    """Rotate polygon by *angle_rad* around the origin."""
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return [
        (x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in polygon
    ]


# ---------------------------------------------------------------------------
# Boustrophedon (lawnmower) sweep for arbitrary polygons
# ---------------------------------------------------------------------------

def polygon_sweep(
    polygon: list[tuple[float, float]],
    altitude: float,
    num_drones: int,
    overlap_pct: float = 0.0,
    line_spacing_m: float = 20.0,
) -> list[list[Waypoint]]:
    """
    Boustrophedon (lawnmower) decomposition for an arbitrary polygon.

    Args:
        polygon: List of ``(lat, lon)`` vertices defining the area.
        altitude: Flight altitude in meters.
        num_drones: Number of drones to split the work across.
        overlap_pct: Percentage overlap between adjacent sweep lines (0-100).
        line_spacing_m: Base distance in meters between sweep lines before
            overlap adjustment.

    Returns:
        A list of waypoint lists, one per drone.
    """
    if num_drones <= 0:
        return []

    # Convert to local metre frame
    local_poly, clat, clon = _polygon_to_local(polygon)

    # Find optimal heading and rotate polygon so sweep lines are horizontal
    heading = _optimal_heading_deg(local_poly)
    angle_rad = math.radians(heading)
    rotated = _rotate_polygon(local_poly, -angle_rad)

    # Determine y-extent (sweep direction after rotation is along y-axis)
    ys = [p[1] for p in rotated]
    y_min, y_max = min(ys), max(ys)

    # Compute effective spacing with overlap
    if overlap_pct >= 100:
        raise ValueError(
            f"overlap_pct must be < 100, got {overlap_pct}. "
            f"100% overlap would produce zero spacing between sweep lines."
        )
    effective_spacing = line_spacing_m * (1.0 - overlap_pct / 100.0)
    if effective_spacing <= 0:
        effective_spacing = line_spacing_m  # fallback for floating-point edge cases

    # Generate sweep y-coordinates
    sweep_ys: list[float] = []
    y = y_min + effective_spacing / 2.0
    while y < y_max:
        sweep_ys.append(y)
        y += effective_spacing

    if not sweep_ys:
        # Polygon too small -- put a single sweep through the middle
        sweep_ys = [(y_min + y_max) / 2.0]

    # Generate waypoints for each sweep line (boustrophedon pattern)
    all_waypoints: list[Waypoint] = []
    sweep_segments: list[list[Waypoint]] = []

    for idx, sy in enumerate(sweep_ys):
        xs = _sweep_line_intersections(rotated, sy)
        if len(xs) < 2:
            continue

        # Take pairs of intersections as segments
        segments: list[tuple[float, float]] = []
        for k in range(0, len(xs) - 1, 2):
            segments.append((xs[k], xs[k + 1]))

        # Generate waypoints for this sweep line
        line_wps: list[Waypoint] = []
        for x_start, x_end in segments:
            # Boustrophedon: alternate direction on even/odd rows
            pts = [(x_start, sy), (x_end, sy)] if idx % 2 == 0 else [(x_end, sy), (x_start, sy)]

            for px, py in pts:
                # Rotate back to original frame
                rx = px * math.cos(angle_rad) - py * math.sin(angle_rad)
                ry = px * math.sin(angle_rad) + py * math.cos(angle_rad)
                lat, lon = _local_to_gps(rx, ry, clat, clon)
                line_wps.append(Waypoint(lat, lon, altitude))

        if line_wps:
            sweep_segments.append(line_wps)
            all_waypoints.extend(line_wps)

    # Divide sweep lines equitably among drones
    missions: list[list[Waypoint]] = [[] for _ in range(num_drones)]
    if sweep_segments:
        # Distribute sweep lines round-robin
        for i, seg in enumerate(sweep_segments):
            drone_idx = i % num_drones
            missions[drone_idx].extend(seg)

    return missions


# ---------------------------------------------------------------------------
# Backwards-compatible area_sweep (rectangle -> polygon_sweep)
# ---------------------------------------------------------------------------

def area_sweep(
    sw_lat: float,
    sw_lon: float,
    ne_lat: float,
    ne_lon: float,
    altitude: float,
    num_drones: int,
) -> list[list[Waypoint]]:
    """
    Divide a rectangular area into strips using Boustrophedon decomposition.

    This is a backwards-compatible wrapper around :func:`polygon_sweep`.
    The rectangle defined by the SW and NE corners is converted to a polygon
    and swept with the lawnmower pattern.

    Each drone sweeps its assigned strips.  The function preserves the old
    contract: returns one waypoint list per drone.
    """
    # Build rectangle polygon (SW, SE, NE, NW)
    rectangle: list[tuple[float, float]] = [
        (sw_lat, sw_lon),
        (sw_lat, ne_lon),
        (ne_lat, ne_lon),
        (ne_lat, sw_lon),
    ]
    return polygon_sweep(rectangle, altitude, num_drones)


# ---------------------------------------------------------------------------
# Formation helpers (unchanged)
# ---------------------------------------------------------------------------

def line_formation(
    center_lat: float,
    center_lon: float,
    altitude: float,
    num_drones: int,
    spacing_m: float = 20.0,
    heading_deg: float = 0.0,
) -> list[list[Waypoint]]:
    """Arrange drones in a line perpendicular to *heading_deg*.

    Drones are evenly spaced along a line centered on ``(center_lat, center_lon)``,
    oriented 90 degrees to the heading. Useful for search lines or perimeter patrols.

    Args:
        center_lat: Center latitude of the line.
        center_lon: Center longitude of the line.
        altitude: Flight altitude in metres.
        num_drones: Number of drones to position.
        spacing_m: Distance in metres between adjacent drones.
        heading_deg: Direction the formation faces (0 = north).

    Returns:
        A list of waypoint lists, one per drone. Each contains a single
        waypoint at the drone's formation slot.
    """
    missions: list[list[Waypoint]] = []
    heading_rad = math.radians(heading_deg + 90)
    for i in range(num_drones):
        offset = (i - (num_drones - 1) / 2) * spacing_m
        dlat = offset * math.cos(heading_rad) / 111320
        dlon = offset * math.sin(heading_rad) / (111320 * math.cos(math.radians(center_lat)))
        missions.append([Waypoint(center_lat + dlat, center_lon + dlon, altitude)])
    return missions


def v_formation(
    center_lat: float,
    center_lon: float,
    altitude: float,
    num_drones: int,
    spacing_m: float = 15.0,
    heading_deg: float = 0.0,
    angle_deg: float = 45.0,
) -> list[list[Waypoint]]:
    """Arrange drones in a V-formation pointed in *heading_deg* direction.

    The first drone is the leader at the tip of the V. Remaining drones
    alternate between left and right arms, each ``spacing_m`` metres apart
    along the arm. The V angle is controlled by ``angle_deg``.

    Args:
        center_lat: Latitude of the V tip (leader position).
        center_lon: Longitude of the V tip (leader position).
        altitude: Flight altitude in metres.
        num_drones: Total number of drones (including leader).
        spacing_m: Distance along each arm between consecutive drones.
        heading_deg: Direction the V points (0 = north, 90 = east).
        angle_deg: Half-angle of the V shape (45 = classic V).

    Returns:
        A list of waypoint lists, one per drone. Index 0 is the leader.
    """
    missions: list[list[Waypoint]] = []
    heading_rad = math.radians(heading_deg)
    arm_rad = math.radians(angle_deg)

    # Leader
    missions.append([Waypoint(center_lat, center_lon, altitude)])

    for i in range(1, num_drones):
        side = 1 if i % 2 == 1 else -1
        rank = (i + 1) // 2
        dist = rank * spacing_m
        dx = -dist * math.cos(arm_rad)
        dy = side * dist * math.sin(arm_rad)
        rx = dx * math.cos(heading_rad) - dy * math.sin(heading_rad)
        ry = dx * math.sin(heading_rad) + dy * math.cos(heading_rad)
        dlat = rx / 111320
        dlon = ry / (111320 * math.cos(math.radians(center_lat)))
        missions.append([Waypoint(center_lat + dlat, center_lon + dlon, altitude)])

    return missions


def orbit_point(
    center_lat: float,
    center_lon: float,
    altitude: float,
    radius_m: float = 50.0,
    num_drones: int = 3,
    points_per_orbit: int = 12,
) -> list[list[Waypoint]]:
    """Generate circular orbit waypoints around a point of interest.

    Drones are evenly phased around the circle so they maintain equal angular
    separation throughout the orbit. Each drone gets ``points_per_orbit``
    waypoints tracing a full 360-degree loop.

    Args:
        center_lat: Latitude of the orbit center.
        center_lon: Longitude of the orbit center.
        altitude: Flight altitude in metres.
        radius_m: Orbit radius in metres.
        num_drones: Number of drones to orbit.
        points_per_orbit: Number of waypoints per full orbit (more = smoother).

    Returns:
        A list of waypoint lists, one per drone. Each contains
        ``points_per_orbit`` waypoints tracing the full circle.
    """
    missions: list[list[Waypoint]] = []
    phase_offset = 2 * math.pi / num_drones

    for i in range(num_drones):
        waypoints: list[Waypoint] = []
        for p in range(points_per_orbit):
            angle = phase_offset * i + (2 * math.pi * p / points_per_orbit)
            dlat = radius_m * math.cos(angle) / 111320
            dlon = radius_m * math.sin(angle) / (111320 * math.cos(math.radians(center_lat)))
            waypoints.append(Waypoint(center_lat + dlat, center_lon + dlon, altitude))
        missions.append(waypoints)
    return missions
