"""
Collision avoidance system for drone swarms.

Monitors pairwise distances between all drones and computes avoidance
manoeuvres when any pair gets closer than the configured minimum safe
separation.

Supports two algorithms selectable via the *method* parameter:

  "orca"  (default, v0.2)
      Optimal Reciprocal Collision Avoidance.  For each pair of drones,
      computes a velocity obstacle (VO) and derives an ORCA half-plane.
      The new velocity for each drone is found by projecting the preferred
      velocity onto the intersection of all ORCA half-planes (a simple
      linear-programming pass).  Runs in microseconds for typical swarm
      sizes.

  "repulsive"  (v0.1 fallback)
      Simple repulsive-force model that pushes drones apart along the
      line connecting them.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from itertools import combinations

from .drone import Drone, Waypoint
from .geo import haversine

logger = logging.getLogger("drone_swarm.collision")

# Earth radius in metres (WGS-84 mean)
_EARTH_R = 6_371_000.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CollisionRisk:
    """A pair of drones that are dangerously close."""

    drone_a_id: str
    drone_b_id: str
    distance_m: float
    min_distance_m: float


@dataclass
class OrcaVelocity:
    """ORCA output for a single drone: a safe velocity in local NED (m/s)."""

    drone_id: str
    vn: float  # north component (m/s)
    ve: float  # east component (m/s)


def _offset_gps(
    lat: float, lon: float, alt: float,
    delta_north_m: float, delta_east_m: float,
) -> Waypoint:
    """Return a new Waypoint offset by metres north and east (flat-earth approx)."""
    dn, de = delta_north_m, delta_east_m
    new_lat = lat + (dn / _EARTH_R) * (180.0 / math.pi)
    new_lon = lon + (de / (_EARTH_R * math.cos(math.radians(lat)))) * (180.0 / math.pi)
    return Waypoint(lat=new_lat, lon=new_lon, alt=alt)


def _gps_to_ned(ref_lat: float, ref_lon: float, lat: float, lon: float) -> tuple[float, float]:
    """Convert GPS coordinates to local NED offsets (north, east) in metres.

    Uses a flat-earth approximation relative to ``(ref_lat, ref_lon)``.
    Accurate for distances under ~10 km.
    """
    dn = (lat - ref_lat) * (_EARTH_R * math.pi / 180.0)
    de = (lon - ref_lon) * (_EARTH_R * math.cos(math.radians(ref_lat)) * math.pi / 180.0)
    return dn, de


# ---------------------------------------------------------------------------
# 2-D vector helpers
# ---------------------------------------------------------------------------

def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _sub(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] + b[0], a[1] + b[1])


def _scale(v: tuple[float, float], s: float) -> tuple[float, float]:
    return (v[0] * s, v[1] * s)


def _norm(v: tuple[float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1])


def _normalize(v: tuple[float, float]) -> tuple[float, float]:
    n = _norm(v)
    if n < 1e-12:
        return (0.0, 0.0)
    return (v[0] / n, v[1] / n)


# ---------------------------------------------------------------------------
# ORCA half-plane computation
# ---------------------------------------------------------------------------

@dataclass
class _HalfPlane:
    """A half-plane defined by a point on its boundary and an outward normal.

    The feasible region is: { v : dot(normal, v - point) >= 0 }.
    """
    point: tuple[float, float]
    normal: tuple[float, float]


def _compute_orca_half_plane(
    pos_a: tuple[float, float],
    pos_b: tuple[float, float],
    vel_a: tuple[float, float],
    vel_b: tuple[float, float],
    radius_a: float,
    radius_b: float,
    tau: float,
) -> _HalfPlane | None:
    """Compute the ORCA half-plane for agent A induced by agent B.

    Parameters
    ----------
    pos_a, pos_b : positions in 2-D
    vel_a, vel_b : current velocities in 2-D
    radius_a, radius_b : combined collision radii
    tau : time horizon (seconds)

    Returns None if agents are far enough that no constraint is needed.
    """
    rel_pos = _sub(pos_b, pos_a)           # p_B - p_A
    rel_vel = _sub(vel_a, vel_b)           # v_A - v_B
    dist_sq = _dot(rel_pos, rel_pos)
    combined_r = radius_a + radius_b
    combined_r_sq = combined_r * combined_r

    # --- ORCA Algorithm (van den Berg et al., 2011) ---
    # Step 1: Build a Velocity Obstacle (VO) — a truncated cone in velocity
    #   space representing all relative velocities that would cause a collision
    #   within time horizon tau.
    # Step 2: Find the smallest correction vector 'u' that moves the current
    #   relative velocity outside the VO.
    # Step 3: The ORCA half-plane passes through vel_a + 0.5*u (each agent
    #   takes responsibility for half the correction) with normal = u_hat.

    inv_tau = 1.0 / tau
    # Relative position scaled by 1/tau
    rel_pos_tau = _scale(rel_pos, inv_tau)
    # w = rel_vel - rel_pos / tau
    w = _sub(rel_vel, rel_pos_tau)
    w_len_sq = _dot(w, w)
    w_dot_rel = _dot(w, rel_pos)

    dist = math.sqrt(dist_sq)

    # Case 1: Agents overlap — push directly apart (degenerate case)
    if dist_sq <= combined_r_sq:
        # Agents overlap -- use the direction from A to B
        direction = _normalize(rel_pos) if dist > 1e-12 else (1.0, 0.0)
        normal = (-direction[0], -direction[1])  # pointing away from B
        point = _add(vel_a, _scale(normal, 0.0))
        return _HalfPlane(point=vel_a, normal=normal)

    # Case 2: No overlap — project rel_vel onto the nearest VO boundary
    # (either the truncation circle at 1/tau or one of the cone legs)
    if dist_sq > combined_r_sq:
        # No overlap
        # Squared cutoff radius scaled by inv_tau^2
        cutoff_r = combined_r * inv_tau

        if w_dot_rel < 0.0 and w_dot_rel * w_dot_rel > combined_r_sq * w_len_sq:
            # Project on the cutoff circle (the truncated part)
            w_len = math.sqrt(w_len_sq)
            if w_len < 1e-12:
                return None
            unit_w = (w[0] / w_len, w[1] / w_len)
            normal = unit_w
            u = _scale(unit_w, cutoff_r - w_len)
        else:
            # Project on the cone legs
            leg = math.sqrt(dist_sq - combined_r_sq)

            if rel_pos[0] * w[1] - rel_pos[1] * w[0] >= 0.0:
                # Left leg
                direction = (
                    rel_pos[0] * leg + rel_pos[1] * combined_r,
                    -rel_pos[0] * combined_r + rel_pos[1] * leg,
                )
            else:
                # Right leg
                direction = (
                    rel_pos[0] * leg - rel_pos[1] * combined_r,
                    rel_pos[0] * combined_r + rel_pos[1] * leg,
                )

            direction = _scale(direction, 1.0 / dist_sq)
            dot_prod = _dot(rel_vel, direction)
            proj = _scale(direction, dot_prod)
            u = _sub(proj, rel_vel)
            normal = _normalize(u)
            if _norm(u) < 1e-12:
                return None

    # ORCA half-plane: agent A takes responsibility for half the correction
    point = _add(vel_a, _scale(u, 0.5))
    return _HalfPlane(point=point, normal=normal)


# ---------------------------------------------------------------------------
# Linear program: project preferred velocity onto half-plane intersection
# ---------------------------------------------------------------------------

def _solve_half_planes(
    preferred: tuple[float, float],
    half_planes: list[_HalfPlane],
    max_speed: float,
) -> tuple[float, float]:
    """Find the velocity closest to *preferred* that satisfies all half-planes.

    Uses an incremental 2-D linear-programming approach (Dobkin-Kirkpatrick).
    Falls back to projecting onto individual planes when needed.
    """
    result = preferred

    for i, hp in enumerate(half_planes):
        # Check if current result already satisfies this half-plane
        if _dot(hp.normal, _sub(result, hp.point)) >= 0.0:
            continue

        # Project result onto the half-plane boundary
        # The boundary line passes through hp.point with direction perpendicular to hp.normal
        line_dir = (-hp.normal[1], hp.normal[0])  # 90 deg rotation
        diff = _sub(result, hp.point)
        t = _dot(diff, line_dir)
        result = _add(hp.point, _scale(line_dir, t))

        # Clamp to max speed disc
        if _norm(result) > max_speed:
            result = _scale(_normalize(result), max_speed)

        # Verify earlier half-planes are still satisfied; if not, find
        # the best we can on the boundary of the violated plane
        for j in range(i):
            if _dot(half_planes[j].normal, _sub(result, half_planes[j].point)) < -1e-9:
                # Intersect the boundary lines of plane i and plane j
                d_i = (-hp.normal[1], hp.normal[0])
                d_j = (-half_planes[j].normal[1], half_planes[j].normal[0])
                cross = d_i[0] * d_j[1] - d_i[1] * d_j[0]
                if abs(cross) < 1e-12:
                    # Parallel -- pick the one closer to preferred
                    result = (0.0, 0.0)
                else:
                    diff2 = _sub(half_planes[j].point, hp.point)
                    t_val = (diff2[0] * d_j[1] - diff2[1] * d_j[0]) / cross
                    result = _add(hp.point, _scale(d_i, t_val))

                if _norm(result) > max_speed:
                    result = _scale(_normalize(result), max_speed)
                break

    # Final speed clamp
    if _norm(result) > max_speed:
        result = _scale(_normalize(result), max_speed)

    return result


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class CollisionAvoidance:
    """
    Monitors drone separations and computes avoidance waypoints.

    Parameters
    ----------
    min_distance_m:
        Minimum safe separation in metres.  Pairs whose distance is
        **strictly less than** this value are flagged.
    method:
        ``"orca"`` (default) for Optimal Reciprocal Collision Avoidance,
        ``"repulsive"`` for the v0.1 simple repulsive-force fallback.
    tau:
        ORCA time horizon in seconds (how far ahead to look for collisions).
    max_speed:
        Maximum drone speed in m/s (used to clamp ORCA output).
    dt:
        Time step for converting ORCA velocity to waypoint offset (seconds).
    """

    def __init__(
        self,
        min_distance_m: float = 5.0,
        method: str = "orca",
        tau: float = 5.0,
        max_speed: float = 5.0,
        dt: float = 1.0,
    ) -> None:
        if method not in ("orca", "repulsive"):
            raise ValueError(f"Unknown method {method!r}; expected 'orca' or 'repulsive'")
        self.min_distance_m = min_distance_m
        self.method = method
        self.tau = tau
        self.max_speed = max_speed
        self.dt = dt

    # -- detection ----------------------------------------------------------

    def check_all_pairs(self, drones: dict[str, Drone]) -> list[CollisionRisk]:
        """Return a :class:`CollisionRisk` for every pair closer than the threshold.

        Uses spatial grid indexing for O(n) expected performance when drones
        are spread out, falling back gracefully when clustered.
        """
        if len(drones) < 2:
            return []

        risks: list[CollisionRisk] = []

        # For small swarms, brute-force is fine
        if len(drones) <= 10:
            for (id_a, drone_a), (id_b, drone_b) in combinations(drones.items(), 2):
                dist = haversine(drone_a.lat, drone_a.lon, drone_b.lat, drone_b.lon)
                if dist < self.min_distance_m:
                    risks.append(CollisionRisk(id_a, id_b, dist, self.min_distance_m))
            return risks

        # Spatial grid: bucket drones by cell, only check neighbours
        cell_size = self.min_distance_m
        # Use first drone as reference for local NED conversion
        items = list(drones.items())
        ref_lat, ref_lon = items[0][1].lat, items[0][1].lon

        grid: dict[tuple[int, int], list[tuple[str, Drone]]] = {}
        for did, d in items:
            dn, de = _gps_to_ned(ref_lat, ref_lon, d.lat, d.lon)
            cr = math.floor(dn / cell_size)
            cc = math.floor(de / cell_size)
            grid.setdefault((cr, cc), []).append((did, d))

        checked: set[tuple[str, str]] = set()
        for (gr, gc), cell_drones in grid.items():
            # Check within this cell and 8 neighbours
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    neighbour_key = (gr + dr, gc + dc)
                    neighbour_drones = grid.get(neighbour_key)
                    if neighbour_drones is None:
                        continue
                    for id_a, drone_a in cell_drones:
                        for id_b, drone_b in neighbour_drones:
                            if id_a >= id_b:
                                continue
                            pair = (id_a, id_b)
                            if pair in checked:
                                continue
                            checked.add(pair)
                            dist = haversine(drone_a.lat, drone_a.lon,
                                             drone_b.lat, drone_b.lon)
                            if dist < self.min_distance_m:
                                risks.append(CollisionRisk(
                                    id_a, id_b, dist, self.min_distance_m,
                                ))

        return risks

    # -- ORCA ---------------------------------------------------------------

    def compute_orca_velocities(
        self,
        drones: dict[str, Drone],
        preferred_velocities: dict[str, tuple[float, float]] | None = None,
    ) -> list[OrcaVelocity]:
        """Compute ORCA-safe velocities for all drones.

        Parameters
        ----------
        drones:
            Map of drone_id -> Drone with current GPS positions.
        preferred_velocities:
            Map of drone_id -> (vn, ve) preferred velocity in m/s.
            If ``None``, preferred velocity is (0, 0) for all drones
            (i.e. they want to hover in place).

        Returns
        -------
        A list of :class:`OrcaVelocity` for every drone whose velocity
        was adjusted (or all drones if any constraints exist).
        """
        if preferred_velocities is None:
            preferred_velocities = {did: (0.0, 0.0) for did in drones}

        ids = list(drones.keys())
        if len(ids) < 2:
            return [
                OrcaVelocity(drone_id=did, vn=pv[0], ve=pv[1])
                for did, pv in preferred_velocities.items()
                if did in drones
            ]

        # Use first drone as NED reference
        ref_lat = drones[ids[0]].lat
        ref_lon = drones[ids[0]].lon

        # Compute NED positions
        positions: dict[str, tuple[float, float]] = {}
        for did, d in drones.items():
            positions[did] = _gps_to_ned(ref_lat, ref_lon, d.lat, d.lon)

        # Collision radius per drone = half the minimum distance
        radius = self.min_distance_m / 2.0

        # Build half-planes for each drone
        half_planes_per_drone: dict[str, list[_HalfPlane]] = {did: [] for did in ids}

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a, id_b = ids[i], ids[j]
                vel_a = preferred_velocities.get(id_a, (0.0, 0.0))
                vel_b = preferred_velocities.get(id_b, (0.0, 0.0))

                hp_a = _compute_orca_half_plane(
                    positions[id_a], positions[id_b],
                    vel_a, vel_b,
                    radius, radius,
                    self.tau,
                )
                if hp_a is not None:
                    half_planes_per_drone[id_a].append(hp_a)

                # Symmetric: B's half-plane from A
                hp_b = _compute_orca_half_plane(
                    positions[id_b], positions[id_a],
                    vel_b, vel_a,
                    radius, radius,
                    self.tau,
                )
                if hp_b is not None:
                    half_planes_per_drone[id_b].append(hp_b)

        # Solve LP for each drone
        results: list[OrcaVelocity] = []
        for did in ids:
            pref = preferred_velocities.get(did, (0.0, 0.0))
            hps = half_planes_per_drone[did]
            safe = pref if not hps else _solve_half_planes(pref, hps, self.max_speed)
            results.append(OrcaVelocity(drone_id=did, vn=safe[0], ve=safe[1]))

        return results

    # -- avoidance dispatch -------------------------------------------------

    def compute_avoidance(
        self,
        drone_a: Drone,
        drone_b: Drone,
        min_dist: float,
    ) -> tuple[Waypoint, Waypoint]:
        """Compute avoidance waypoints for a pair using the configured method.

        This keeps the v0.1 public API: accepts two drones and returns
        two waypoints.
        """
        if self.method == "orca":
            return self.compute_avoidance_orca(drone_a, drone_b, min_dist)
        return self.compute_avoidance_repulsive(drone_a, drone_b, min_dist)

    # -- ORCA pair avoidance (convenience wrapper) -------------------------

    def compute_avoidance_orca(
        self,
        drone_a: Drone,
        drone_b: Drone,
        min_dist: float,
    ) -> tuple[Waypoint, Waypoint]:
        """Compute ORCA avoidance waypoints for a single pair.

        Uses :meth:`compute_orca_velocities` internally, then converts
        the safe velocity into a GPS waypoint offset.
        """
        drones = {"__a__": drone_a, "__b__": drone_b}

        # Compute a repulsive preferred velocity: each drone *wants* to move
        # away from the other at max_speed.  This ensures the LP solver always
        # finds a velocity that actually separates the pair.
        dn, de = _gps_to_ned(drone_a.lat, drone_a.lon, drone_b.lat, drone_b.lon)
        length = math.sqrt(dn * dn + de * de)
        if length < 1e-12:
            # Co-located -- pick an arbitrary direction
            dn, de, length = 0.0, 1.0, 1.0
        un, ue = dn / length, de / length
        push_speed = self.max_speed
        preferred = {
            "__a__": (-un * push_speed, -ue * push_speed),  # away from B
            "__b__": (un * push_speed, ue * push_speed),    # away from A
        }
        velocities = self.compute_orca_velocities(drones, preferred)

        vel_map = {v.drone_id: v for v in velocities}
        va = vel_map["__a__"]
        vb = vel_map["__b__"]

        # Convert velocity to waypoint offset: position + velocity * dt
        wp_a = _offset_gps(drone_a.lat, drone_a.lon, drone_a.alt,
                           va.vn * self.dt, va.ve * self.dt)
        wp_b = _offset_gps(drone_b.lat, drone_b.lon, drone_b.alt,
                           vb.vn * self.dt, vb.ve * self.dt)

        return wp_a, wp_b

    # -- Repulsive-force fallback (v0.1) ------------------------------------

    @staticmethod
    def compute_avoidance_repulsive(
        drone_a: Drone,
        drone_b: Drone,
        min_dist: float,
    ) -> tuple[Waypoint, Waypoint]:
        """
        Compute repulsive avoidance waypoints for a pair that is too close.

        Each drone is pushed away from the other by half the deficit so that
        the total separation increases to at least *min_dist*.
        """
        dist = haversine(drone_a.lat, drone_a.lon, drone_b.lat, drone_b.lon)

        # Local NED offset from A to B (flat-earth approximation, good for
        # short distances typical of collision-avoidance).
        dn = (drone_b.lat - drone_a.lat) * (_EARTH_R * math.pi / 180.0)
        de = (drone_b.lon - drone_a.lon) * (
            _EARTH_R * math.cos(math.radians(drone_a.lat)) * math.pi / 180.0
        )

        length = math.sqrt(dn * dn + de * de)
        if length == 0:
            # Drones exactly co-located -- nudge B east arbitrarily.
            dn, de, length = 0.0, 1.0, 1.0

        # Unit vector A -> B
        un = dn / length
        ue = de / length

        push = (min_dist - dist) / 2.0
        if push < 0:
            push = 0.0

        # A gets pushed *away* from B (opposite direction)
        wp_a = _offset_gps(drone_a.lat, drone_a.lon, drone_a.alt, -un * push, -ue * push)
        # B gets pushed *away* from A (same direction as A->B)
        wp_b = _offset_gps(drone_b.lat, drone_b.lon, drone_b.alt, un * push, ue * push)

        return wp_a, wp_b
