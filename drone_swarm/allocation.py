"""
Optimal task allocation using the Hungarian algorithm.

Provides optimal drone-to-target assignment minimizing total distance,
and optimal replanning when a drone is lost mid-mission.

Requires ``scipy`` (install with ``pip install drone-swarm[allocation]``).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from .drone import Drone, Waypoint

if TYPE_CHECKING:
    from .swarm import SwarmOrchestrator

logger = logging.getLogger("drone_swarm.allocation")


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two GPS coordinates."""
    earth_r = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return earth_r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def optimal_assign(
    drones: dict[str, Drone],
    targets: list[Waypoint],
) -> dict[str, list[Waypoint]]:
    """
    Optimally assign *targets* to *drones* minimizing total travel distance.

    Uses the Hungarian algorithm (``scipy.optimize.linear_sum_assignment``).

    When there are more targets than drones, each drone may receive multiple
    targets.  The algorithm iteratively assigns the next batch of targets
    until all are allocated.

    Returns a mapping ``{drone_id: [waypoints...]}``.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    drone_ids = list(drones.keys())
    n_drones = len(drone_ids)

    if n_drones == 0 or len(targets) == 0:
        return {did: [] for did in drone_ids}

    # Initialize result and mutable drone positions (updated after each round)
    result: dict[str, list[Waypoint]] = {did: [] for did in drone_ids}
    # Track the "current position" of each drone for multi-round assignment
    drone_positions: dict[str, tuple[float, float]] = {
        did: (drones[did].lat, drones[did].lon) for did in drone_ids
    }

    remaining = list(targets)

    while remaining:
        # Take up to n_drones targets per round
        batch = remaining[:n_drones]
        remaining = remaining[n_drones:]

        n_batch = len(batch)

        # Build cost matrix: rows = drones, cols = batch targets
        cost = np.zeros((n_drones, n_batch))
        for i, did in enumerate(drone_ids):
            dlat, dlon = drone_positions[did]
            for j, wp in enumerate(batch):
                cost[i, j] = _haversine(dlat, dlon, wp.lat, wp.lon)

        # Solve assignment (handles rectangular matrices)
        row_ind, col_ind = linear_sum_assignment(cost)

        for r, c in zip(row_ind, col_ind, strict=False):
            did = drone_ids[r]
            wp = batch[c]
            result[did].append(wp)
            # Update position to assigned target for next round
            drone_positions[did] = (wp.lat, wp.lon)

    return result


def replan_optimal(swarm: SwarmOrchestrator, lost_drone_id: str) -> None:
    """
    Redistribute the lost drone's remaining waypoints optimally.

    Collects all unfinished waypoints from the lost drone and uses the
    Hungarian algorithm to assign them across remaining active drones,
    minimizing total distance.
    """
    lost = swarm.drones[lost_drone_id]
    remaining_wps = list(lost.mission)
    if not remaining_wps:
        return

    active_ids = swarm.active_drones()
    if not active_ids:
        logger.error("No active drones to absorb mission -- all lost")
        return

    active_drones = {did: swarm.drones[did] for did in active_ids}
    assignments = optimal_assign(active_drones, remaining_wps)

    for did, wps in assignments.items():
        swarm.drones[did].mission.extend(wps)

    lost.mission = []
    logger.info(
        "Optimal replan: %d waypoints from '%s' redistributed to %d drones",
        len(remaining_wps),
        lost_drone_id,
        len(active_ids),
    )
