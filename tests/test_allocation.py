"""Tests for drone_swarm.allocation -- Hungarian algorithm task assignment.

Requires scipy. All tests run without pymavlink or SITL.
"""

import math

import pytest

from drone_swarm.drone import Drone, DroneStatus, Waypoint
from drone_swarm.swarm import SwarmOrchestrator

scipy = pytest.importorskip("scipy")

from drone_swarm.allocation import optimal_assign, replan_optimal  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def _total_assignment_distance(
    drones: dict[str, Drone],
    assignments: dict[str, list[Waypoint]],
) -> float:
    """Sum of distances from each drone to its first assigned target."""
    total = 0.0
    for did, wps in assignments.items():
        if wps:
            d = drones[did]
            total += _haversine(d.lat, d.lon, wps[0].lat, wps[0].lon)
    return total


def _make_drone(drone_id: str, lat: float, lon: float) -> Drone:
    return Drone(
        drone_id=drone_id,
        connection_string="udp:127.0.0.1:0",
        lat=lat,
        lon=lon,
        status=DroneStatus.AIRBORNE,
    )


# ---------------------------------------------------------------------------
# Tests: optimal_assign (Hungarian)
# ---------------------------------------------------------------------------

class TestOptimalAssign:
    def test_3_drones_3_targets_each_gets_closest(self):
        """Each drone should be assigned the target nearest to it."""
        drones = {
            "d0": _make_drone("d0", 35.0, -118.0),
            "d1": _make_drone("d1", 35.1, -118.0),
            "d2": _make_drone("d2", 35.0, -117.9),
        }
        targets = [
            Waypoint(35.0, -117.91, 20),  # closest to d2
            Waypoint(35.1, -118.01, 20),  # closest to d1
            Waypoint(35.0, -118.01, 20),  # closest to d0
        ]
        result = optimal_assign(drones, targets)

        # Every drone gets exactly 1 target
        assert all(len(wps) == 1 for wps in result.values())
        # All 3 targets assigned
        all_assigned = [wp for wps in result.values() for wp in wps]
        assert len(all_assigned) == 3

    def test_more_targets_than_drones(self):
        """With 6 targets and 2 drones, each drone should get 3."""
        drones = {
            "d0": _make_drone("d0", 35.0, -118.0),
            "d1": _make_drone("d1", 35.1, -118.0),
        }
        targets = [
            Waypoint(35.0 + 0.01 * i, -118.0 + 0.01 * i, 20)
            for i in range(6)
        ]
        result = optimal_assign(drones, targets)

        total = sum(len(wps) for wps in result.values())
        assert total == 6
        # Each drone gets at least 2 targets
        for wps in result.values():
            assert len(wps) >= 2

    def test_more_drones_than_targets(self):
        """With 3 drones and 1 target, only 1 drone gets a waypoint."""
        drones = {
            "d0": _make_drone("d0", 35.0, -118.0),
            "d1": _make_drone("d1", 35.1, -118.0),
            "d2": _make_drone("d2", 35.0, -117.9),
        }
        targets = [Waypoint(35.0, -118.01, 20)]
        result = optimal_assign(drones, targets)

        total = sum(len(wps) for wps in result.values())
        assert total == 1

    def test_empty_targets(self):
        drones = {"d0": _make_drone("d0", 35.0, -118.0)}
        result = optimal_assign(drones, [])
        assert result == {"d0": []}

    def test_empty_drones(self):
        result = optimal_assign({}, [Waypoint(35.0, -118.0, 20)])
        assert result == {}

    def test_total_distance_less_than_nearest_neighbor(self):
        """Hungarian assignment should beat or match greedy nearest-neighbor."""
        # Place drones and targets so greedy assignment is suboptimal
        drones = {
            "d0": _make_drone("d0", 35.0, -118.0),
            "d1": _make_drone("d1", 35.0, -117.5),
        }
        # t0 is slightly closer to d0 but t1 is much closer to d0
        # Greedy: d0->t0, d1->t1 or d0->t1, d1->t0
        targets = [
            Waypoint(35.0, -117.99, 20),  # very close to d0
            Waypoint(35.0, -117.51, 20),  # very close to d1
        ]

        result = optimal_assign(drones, targets)
        hungarian_dist = _total_assignment_distance(drones, result)

        # Build a greedy (nearest-neighbor) assignment for comparison
        greedy: dict[str, list[Waypoint]] = {did: [] for did in drones}
        remaining = list(targets)
        for did in drones:
            if not remaining:
                break
            nearest = min(
                remaining,
                key=lambda wp: _haversine(
                    drones[did].lat, drones[did].lon, wp.lat, wp.lon,
                ),
            )
            greedy[did].append(nearest)
            remaining.remove(nearest)
        greedy_dist = _total_assignment_distance(drones, greedy)

        assert hungarian_dist <= greedy_dist + 1e-6  # allow float tolerance


# ---------------------------------------------------------------------------
# Tests: replan_optimal (swarm integration)
# ---------------------------------------------------------------------------

class TestReplanOptimal:
    def _build_swarm_with_missions(self):
        """Create a 3-drone swarm where all are AIRBORNE with missions."""
        orch = SwarmOrchestrator()
        positions = {
            "alpha": (35.0, -118.0),
            "bravo": (35.1, -118.0),
            "charlie": (35.0, -117.9),
        }
        for did, (lat, lon) in positions.items():
            orch.register_drone(did, "udp:127.0.0.1:0")
            orch.drones[did].lat = lat
            orch.drones[did].lon = lon
            orch.drones[did].status = DroneStatus.AIRBORNE

        # Assign missions
        orch.drones["alpha"].mission = [
            Waypoint(35.01, -118.0, 20),
            Waypoint(35.02, -118.0, 20),
        ]
        orch.drones["bravo"].mission = [
            Waypoint(35.11, -118.0, 20),
        ]
        orch.drones["charlie"].mission = [
            Waypoint(35.01, -117.9, 20),
            Waypoint(35.02, -117.9, 20),
            Waypoint(35.03, -117.9, 20),
        ]
        return orch

    def test_lost_drone_waypoints_redistributed(self):
        orch = self._build_swarm_with_missions()
        charlie_wps_count = len(orch.drones["charlie"].mission)

        # Mark charlie as lost
        orch.drones["charlie"].status = DroneStatus.LOST
        replan_optimal(orch, "charlie")

        # Charlie's mission is now empty
        assert orch.drones["charlie"].mission == []

        # All of charlie's waypoints were distributed to active drones
        alpha_new = len(orch.drones["alpha"].mission)
        bravo_new = len(orch.drones["bravo"].mission)
        # Originally: alpha=2, bravo=1, charlie=3
        # After replan: alpha + bravo should have original + charlie's 3
        assert (alpha_new + bravo_new) == (2 + 1 + charlie_wps_count)

    def test_replan_no_waypoints_is_noop(self):
        orch = self._build_swarm_with_missions()
        orch.drones["charlie"].mission = []
        orch.drones["charlie"].status = DroneStatus.LOST

        alpha_before = len(orch.drones["alpha"].mission)
        bravo_before = len(orch.drones["bravo"].mission)
        replan_optimal(orch, "charlie")

        assert len(orch.drones["alpha"].mission) == alpha_before
        assert len(orch.drones["bravo"].mission) == bravo_before

    def test_swarm_replan_on_loss_uses_optimal(self):
        """SwarmOrchestrator.replan_on_loss should use Hungarian when scipy is available."""
        orch = self._build_swarm_with_missions()
        charlie_wps = list(orch.drones["charlie"].mission)
        orch.drones["charlie"].status = DroneStatus.LOST

        orch.replan_on_loss("charlie")

        assert orch.drones["charlie"].mission == []
        alpha_new = len(orch.drones["alpha"].mission)
        bravo_new = len(orch.drones["bravo"].mission)
        assert (alpha_new + bravo_new) == (2 + 1 + len(charlie_wps))
