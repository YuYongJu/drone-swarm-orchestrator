"""Tests for drone_swarm.path_planner -- A* pathfinding, trajectory smoothing,
multi-drone deconfliction, and energy cost estimation.

All tests run without pymavlink or SITL.
"""

import math

import pytest

from drone_swarm.drone import Drone, DroneRole, Waypoint
from drone_swarm.geofence import Geofence
from drone_swarm.path_planner import (
    PathPlanner,
    _haversine,
    energy_cost,
    plan_multi_drone,
    smooth_trajectory,
)
from drone_swarm.wind import WindEstimate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Edwards AFB area coordinates for testing
BASE_LAT = 34.9592
BASE_LON = -117.8814


def _make_drone(drone_id: str, lat: float, lon: float, alt: float = 10.0) -> Drone:
    return Drone(
        drone_id=drone_id,
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
        lat=lat,
        lon=lon,
        alt=alt,
    )


# ---------------------------------------------------------------------------
# PathPlanner.plan_path
# ---------------------------------------------------------------------------


class TestPlanPath:
    """A* pathfinding tests."""

    def test_direct_path_no_obstacles(self):
        """With no obstacles the path should be a straight line: [start, goal]."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=10.0)

        path = planner.plan_path(start, goal)

        assert len(path) == 2
        assert path[0] is start
        assert path[1] is goal

    def test_detour_around_obstacle(self):
        """A single obstacle between start and goal forces a detour."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=10.0)

        # Place an obstacle right in the middle
        mid_lat = (start.lat + goal.lat) / 2
        obstacle = (mid_lat, BASE_LON, 30.0)  # 30m radius

        path = planner.plan_path(start, goal, obstacles=[obstacle])

        # Should have more than 2 waypoints (detour)
        assert len(path) > 2
        # First and last should match start/goal
        assert path[0] is start
        assert path[-1] is goal

        # No intermediate waypoint should be inside the obstacle
        for wp in path[1:-1]:
            dist = _haversine(wp.lat, wp.lon, obstacle[0], obstacle[1])
            assert dist >= obstacle[2] * 0.8, (
                f"Waypoint at ({wp.lat}, {wp.lon}) is {dist:.1f}m from obstacle "
                f"centre (min {obstacle[2]}m)"
            )

    def test_path_preserves_start_goal(self):
        """The returned path always starts at start and ends at goal exactly."""
        planner = PathPlanner(resolution_m=2.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=15.0)
        goal = Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=25.0)

        path = planner.plan_path(start, goal)

        assert path[0].lat == start.lat
        assert path[0].lon == start.lon
        assert path[-1].lat == goal.lat
        assert path[-1].lon == goal.lon

    def test_altitude_interpolated(self):
        """When detouring, altitude should transition from start.alt to goal.alt."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=30.0)
        obstacle = ((start.lat + goal.lat) / 2, BASE_LON, 30.0)

        path = planner.plan_path(start, goal, obstacles=[obstacle])

        assert len(path) >= 2
        # Altitude should generally increase from start to goal
        assert path[0].alt == pytest.approx(10.0, abs=0.5)
        assert path[-1].alt == pytest.approx(30.0, abs=0.5)

    def test_multiple_obstacles(self):
        """Path avoids multiple obstacles."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.003, lon=BASE_LON, alt=10.0)

        # Two obstacles staggered along the route
        obs1 = (BASE_LAT + 0.001, BASE_LON, 20.0)
        obs2 = (BASE_LAT + 0.002, BASE_LON, 20.0)

        path = planner.plan_path(start, goal, obstacles=[obs1, obs2])
        assert len(path) > 2


# ---------------------------------------------------------------------------
# Trajectory smoothing
# ---------------------------------------------------------------------------


class TestSmoothTrajectory:
    """Cubic spline trajectory smoothing tests."""

    def test_smooth_has_more_points(self):
        """Smoothed trajectory should have the requested number of points."""
        waypoints = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=10.0),
        ]

        smoothed = smooth_trajectory(waypoints, num_points=30)
        assert len(smoothed) == 30

    def test_smooth_preserves_endpoints(self):
        """Smoothed trajectory starts and ends at the original endpoints."""
        waypoints = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.0005, alt=15.0),
            Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON + 0.001, alt=20.0),
        ]

        smoothed = smooth_trajectory(waypoints, num_points=20)
        assert smoothed[0].lat == pytest.approx(waypoints[0].lat, abs=1e-7)
        assert smoothed[0].lon == pytest.approx(waypoints[0].lon, abs=1e-7)
        assert smoothed[-1].lat == pytest.approx(waypoints[-1].lat, abs=1e-7)
        assert smoothed[-1].lon == pytest.approx(waypoints[-1].lon, abs=1e-7)

    def test_smooth_heading_gradual(self):
        """Heading changes in the smoothed trajectory should be gradual."""
        # A sharp 90-degree turn
        waypoints = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON + 0.002, alt=10.0),
        ]

        smoothed = smooth_trajectory(waypoints, num_points=50)

        # Compute heading changes between consecutive segments
        max_heading_change = 0.0
        for i in range(1, len(smoothed) - 1):
            dlat1 = smoothed[i].lat - smoothed[i - 1].lat
            dlon1 = smoothed[i].lon - smoothed[i - 1].lon
            dlat2 = smoothed[i + 1].lat - smoothed[i].lat
            dlon2 = smoothed[i + 1].lon - smoothed[i].lon

            if (dlat1 == 0 and dlon1 == 0) or (dlat2 == 0 and dlon2 == 0):
                continue

            h1 = math.atan2(dlon1, dlat1)
            h2 = math.atan2(dlon2, dlat2)

            delta = abs(h2 - h1)
            if delta > math.pi:
                delta = 2 * math.pi - delta
            max_heading_change = max(max_heading_change, delta)

        # With 50 points on a smooth spline, the max heading change
        # should be much less than 90 degrees (the raw turn angle)
        assert max_heading_change < math.radians(45), (
            f"Max heading change {math.degrees(max_heading_change):.1f} deg "
            f"is not gradual enough"
        )

    def test_smooth_two_points(self):
        """Smoothing a 2-point path should produce a linearly interpolated result."""
        waypoints = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=20.0),
        ]

        smoothed = smooth_trajectory(waypoints, num_points=11)
        assert len(smoothed) == 11
        # Mid-point (index 5 of 11 = fraction 0.5) should be roughly halfway
        mid = smoothed[5]
        expected_mid_lat = (waypoints[0].lat + waypoints[1].lat) / 2
        assert mid.lat == pytest.approx(expected_mid_lat, abs=1e-5)


# ---------------------------------------------------------------------------
# Multi-drone path planning
# ---------------------------------------------------------------------------


class TestMultiDronePlanning:
    """Multi-drone deconfliction tests."""

    def test_altitude_staggering(self):
        """Paths for different drones should be at different altitudes."""
        drones = {
            "alpha": _make_drone("alpha", BASE_LAT, BASE_LON, alt=10.0),
            "bravo": _make_drone("bravo", BASE_LAT, BASE_LON + 0.001, alt=10.0),
        }
        goals = {
            "alpha": Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON, alt=10.0),
            "bravo": Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=10.0),
        }

        paths = plan_multi_drone(drones, goals, alt_stagger_m=5.0)

        # Each drone should have a different altitude
        {wp.alt for wp in paths["alpha"]}
        {wp.alt for wp in paths["bravo"]}

        # The altitude sets should not overlap (stagger of 5m)
        alpha_avg = sum(wp.alt for wp in paths["alpha"]) / len(paths["alpha"])
        bravo_avg = sum(wp.alt for wp in paths["bravo"]) / len(paths["bravo"])
        assert abs(alpha_avg - bravo_avg) >= 4.0, (
            f"Alpha avg alt {alpha_avg:.1f} and Bravo avg alt {bravo_avg:.1f} "
            f"are not staggered enough"
        )

    def test_multi_drone_paths_dont_cross_at_same_altitude(self):
        """Multi-drone paths should have different altitudes at crossing points."""
        drones = {
            "alpha": _make_drone("alpha", BASE_LAT, BASE_LON, alt=10.0),
            "bravo": _make_drone("bravo", BASE_LAT + 0.002, BASE_LON, alt=10.0),
        }
        # Goals cross: alpha goes northeast, bravo goes northwest
        goals = {
            "alpha": Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON + 0.002, alt=10.0),
            "bravo": Waypoint(lat=BASE_LAT, lon=BASE_LON + 0.002, alt=10.0),
        }

        paths = plan_multi_drone(drones, goals, alt_stagger_m=5.0)

        # All waypoints in alpha's path should have different alt from bravo's
        for wp_a in paths["alpha"]:
            for wp_b in paths["bravo"]:
                if _haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon) < 10.0:
                    # Close horizontally -- altitudes must differ
                    assert abs(wp_a.alt - wp_b.alt) >= 3.0, (
                        f"Alpha and Bravo paths are too close in 3D: "
                        f"alpha alt={wp_a.alt}, bravo alt={wp_b.alt}"
                    )

    def test_three_drones_all_different_altitudes(self):
        """Three drones should each get a distinct altitude band."""
        drones = {
            "a": _make_drone("a", BASE_LAT, BASE_LON, alt=10.0),
            "b": _make_drone("b", BASE_LAT, BASE_LON + 0.001, alt=10.0),
            "c": _make_drone("c", BASE_LAT, BASE_LON + 0.002, alt=10.0),
        }
        goals = {
            "a": Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON, alt=10.0),
            "b": Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=10.0),
            "c": Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.002, alt=10.0),
        }

        paths = plan_multi_drone(drones, goals, alt_stagger_m=5.0)

        avg_alts = {}
        for did, path in paths.items():
            avg_alts[did] = sum(wp.alt for wp in path) / len(path)

        # All pairs should differ by at least the stagger amount
        ids = sorted(avg_alts.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                diff = abs(avg_alts[ids[i]] - avg_alts[ids[j]])
                assert diff >= 4.0, (
                    f"{ids[i]} (alt={avg_alts[ids[i]]:.1f}) and "
                    f"{ids[j]} (alt={avg_alts[ids[j]]:.1f}) overlap"
                )


# ---------------------------------------------------------------------------
# Energy cost estimation
# ---------------------------------------------------------------------------


class TestEnergyCost:
    """Energy cost model tests."""

    def test_zero_for_single_waypoint(self):
        """A path with one waypoint has zero cost."""
        path = [Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)]
        assert energy_cost(path) == 0.0

    def test_increases_with_distance(self):
        """Longer paths cost more energy."""
        short_path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON, alt=10.0),
        ]
        long_path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.005, lon=BASE_LON, alt=10.0),
        ]

        short_cost = energy_cost(short_path)
        long_cost = energy_cost(long_path)

        assert long_cost > short_cost
        assert short_cost > 0

    def test_climb_costs_more(self):
        """Climbing uses more energy than level flight over the same horizontal distance."""
        level_path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=10.0),
        ]
        climb_path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=50.0),
        ]

        level_cost = energy_cost(level_path)
        climb_cost = energy_cost(climb_path)

        assert climb_cost > level_cost

    def test_headwind_increases_cost(self):
        """A headwind should increase energy cost vs. no wind."""
        path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.003, lon=BASE_LON, alt=10.0),
        ]

        no_wind_cost = energy_cost(path)
        # Wind from the north (0 deg) blowing against northward travel
        headwind = WindEstimate(speed_ms=5.0, direction_deg=0.0, confidence=0.8)
        headwind_cost = energy_cost(path, wind=headwind)

        assert headwind_cost > no_wind_cost

    def test_tailwind_decreases_cost(self):
        """A tailwind should decrease energy cost vs. no wind."""
        path = [
            Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0),
            Waypoint(lat=BASE_LAT + 0.003, lon=BASE_LON, alt=10.0),
        ]

        no_wind_cost = energy_cost(path)
        # Wind from the south (180 deg) pushing northward travel
        tailwind = WindEstimate(speed_ms=3.0, direction_deg=180.0, confidence=0.8)
        tailwind_cost = energy_cost(path, wind=tailwind)

        assert tailwind_cost < no_wind_cost


# ---------------------------------------------------------------------------
# Geofence integration
# ---------------------------------------------------------------------------


class TestGeofenceIntegration:
    """Path planner respects geofence boundaries."""

    def test_path_stays_within_geofence(self):
        """When a geofence is set, the planned path stays inside it."""
        # Define a square geofence ~500m on a side
        half = 0.003  # ~330m
        polygon = [
            (BASE_LAT - half, BASE_LON - half),
            (BASE_LAT - half, BASE_LON + half),
            (BASE_LAT + half, BASE_LON + half),
            (BASE_LAT + half, BASE_LON - half),
        ]
        fence = Geofence(polygon=polygon, alt_max_m=100.0)
        planner = PathPlanner(resolution_m=5.0, geofence=fence)

        start = Waypoint(lat=BASE_LAT - 0.001, lon=BASE_LON - 0.001, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.001, lon=BASE_LON + 0.001, alt=10.0)

        path = planner.plan_path(start, goal)

        for wp in path:
            assert fence.contains(wp.lat, wp.lon, wp.alt), (
                f"Waypoint ({wp.lat}, {wp.lon}, {wp.alt}) is outside the geofence"
            )


# ---------------------------------------------------------------------------
# SwarmOrchestrator integration
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """Test enable/disable path planning on SwarmOrchestrator."""

    def test_enable_disable_path_planning(self):
        """enable_path_planning and disable_path_planning toggle the planner."""
        from drone_swarm.swarm import SwarmOrchestrator

        swarm = SwarmOrchestrator()

        assert swarm._path_planner is None

        swarm.enable_path_planning(
            obstacles=[(BASE_LAT, BASE_LON, 10.0)],
            resolution_m=3.0,
        )
        assert swarm._path_planner is not None
        assert swarm._path_planner.resolution_m == 3.0
        assert swarm._path_planning_obstacles == [(BASE_LAT, BASE_LON, 10.0)]

        swarm.disable_path_planning()
        assert swarm._path_planner is None
        assert swarm._path_planning_obstacles is None

    def test_enable_path_planning_uses_geofence(self):
        """When a geofence is set, enable_path_planning passes it to the planner."""
        from drone_swarm.swarm import SwarmOrchestrator

        swarm = SwarmOrchestrator()
        polygon = [
            (BASE_LAT - 0.01, BASE_LON - 0.01),
            (BASE_LAT - 0.01, BASE_LON + 0.01),
            (BASE_LAT + 0.01, BASE_LON + 0.01),
            (BASE_LAT + 0.01, BASE_LON - 0.01),
        ]
        swarm.set_geofence(polygon, alt_max_m=100.0)
        swarm.enable_path_planning()

        assert swarm._path_planner is not None
        assert swarm._path_planner.geofence is not None
