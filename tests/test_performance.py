"""Performance regression tests for drone-swarm SDK.

Each test measures the execution time of a critical algorithm and asserts
it completes within a budget. These budgets are generous (10-50x headroom)
so they catch regressions without flaking on slow CI runners.

Run with: pytest tests/test_performance.py
"""

import time

from drone_swarm.collision import CollisionAvoidance
from drone_swarm.drone import Drone, DroneRole, Waypoint
from drone_swarm.geofence import Geofence
from drone_swarm.path_planner import PathPlanner, smooth_trajectory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _spread_drones(n: int, spacing_deg: float = 0.001) -> dict[str, Drone]:
    """Create n drones spread in a grid pattern."""
    import math
    side = math.ceil(math.sqrt(n))
    drones = {}
    for i in range(n):
        row, col = divmod(i, side)
        drones[f"d-{i}"] = _make_drone(
            f"d-{i}",
            BASE_LAT + row * spacing_deg,
            BASE_LON + col * spacing_deg,
        )
    return drones


# ---------------------------------------------------------------------------
# Collision avoidance performance
# ---------------------------------------------------------------------------

class TestCollisionPerformance:
    def test_check_all_pairs_10_drones(self):
        """10-drone pairwise check must complete in <10ms."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = _spread_drones(10, spacing_deg=0.00003)  # ~3m apart

        start = time.perf_counter()
        for _ in range(100):
            ca.check_all_pairs(drones)
        elapsed = (time.perf_counter() - start) / 100

        assert elapsed < 0.010, f"10-drone check took {elapsed*1000:.1f}ms (budget: 10ms)"

    def test_check_all_pairs_50_drones(self):
        """50-drone pairwise check must complete in <50ms (spatial index)."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = _spread_drones(50, spacing_deg=0.0001)

        start = time.perf_counter()
        for _ in range(20):
            ca.check_all_pairs(drones)
        elapsed = (time.perf_counter() - start) / 20

        assert elapsed < 0.050, f"50-drone check took {elapsed*1000:.1f}ms (budget: 50ms)"

    def test_orca_velocities_10_drones(self):
        """ORCA velocity computation for 10 drones must complete in <20ms."""
        ca = CollisionAvoidance(min_distance_m=5.0)
        drones = _spread_drones(10, spacing_deg=0.00003)

        start = time.perf_counter()
        for _ in range(50):
            ca.compute_orca_velocities(drones)
        elapsed = (time.perf_counter() - start) / 50

        assert elapsed < 0.020, f"ORCA 10-drone took {elapsed*1000:.1f}ms (budget: 20ms)"


# ---------------------------------------------------------------------------
# A* path planner performance
# ---------------------------------------------------------------------------

class TestPathPlannerPerformance:
    def test_astar_with_obstacle(self):
        """A* around a single obstacle must complete in <200ms."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.002, lon=BASE_LON, alt=10.0)
        obstacle = ((start.lat + goal.lat) / 2, BASE_LON, 30.0)

        t0 = time.perf_counter()
        for _ in range(10):
            planner.plan_path(start, goal, obstacles=[obstacle])
        elapsed = (time.perf_counter() - t0) / 10

        assert elapsed < 0.200, f"A* took {elapsed*1000:.1f}ms (budget: 200ms)"

    def test_astar_multiple_obstacles(self):
        """A* around 5 obstacles must complete in <500ms."""
        planner = PathPlanner(resolution_m=5.0)
        start = Waypoint(lat=BASE_LAT, lon=BASE_LON, alt=10.0)
        goal = Waypoint(lat=BASE_LAT + 0.005, lon=BASE_LON, alt=10.0)
        obstacles = [
            (BASE_LAT + 0.001, BASE_LON, 20.0),
            (BASE_LAT + 0.002, BASE_LON + 0.0005, 15.0),
            (BASE_LAT + 0.003, BASE_LON - 0.0005, 15.0),
            (BASE_LAT + 0.004, BASE_LON, 20.0),
            (BASE_LAT + 0.0025, BASE_LON, 10.0),
        ]

        t0 = time.perf_counter()
        for _ in range(5):
            planner.plan_path(start, goal, obstacles=obstacles)
        elapsed = (time.perf_counter() - t0) / 5

        assert elapsed < 0.500, f"A* 5-obstacle took {elapsed*1000:.1f}ms (budget: 500ms)"

    def test_smooth_trajectory_50_points(self):
        """Smoothing a 10-waypoint path to 50 points must complete in <50ms (after warmup)."""
        waypoints = [
            Waypoint(lat=BASE_LAT + i * 0.0005, lon=BASE_LON + (i % 3) * 0.0003, alt=10.0)
            for i in range(10)
        ]

        # Warm up scipy import
        smooth_trajectory(waypoints, num_points=10)

        t0 = time.perf_counter()
        for _ in range(20):
            smooth_trajectory(waypoints, num_points=50)
        elapsed = (time.perf_counter() - t0) / 20

        assert elapsed < 0.050, f"Smoothing took {elapsed*1000:.1f}ms (budget: 50ms)"


# ---------------------------------------------------------------------------
# Geofence performance
# ---------------------------------------------------------------------------

class TestGeofencePerformance:
    def test_containment_check_20_vertex_polygon(self):
        """Point-in-polygon for a 20-vertex fence must complete in <0.1ms."""
        import math
        # Create a 20-vertex circular polygon
        polygon = [
            (BASE_LAT + 0.01 * math.cos(2 * math.pi * i / 20),
             BASE_LON + 0.01 * math.sin(2 * math.pi * i / 20))
            for i in range(20)
        ]
        gf = Geofence(polygon)

        t0 = time.perf_counter()
        for _ in range(10000):
            gf.contains(BASE_LAT, BASE_LON, 10.0)
        elapsed = (time.perf_counter() - t0) / 10000

        assert elapsed < 0.0001, f"Containment took {elapsed*1e6:.1f}us (budget: 100us)"

    def test_drone_check_with_buffer(self):
        """Full drone check (containment + buffer zone) must complete in <0.5ms."""
        import math
        polygon = [
            (BASE_LAT + 0.01 * math.cos(2 * math.pi * i / 20),
             BASE_LON + 0.01 * math.sin(2 * math.pi * i / 20))
            for i in range(20)
        ]
        gf = Geofence(polygon)
        drone = _make_drone("alpha", BASE_LAT, BASE_LON)

        t0 = time.perf_counter()
        for _ in range(5000):
            gf.check_drone(drone)
        elapsed = (time.perf_counter() - t0) / 5000

        assert elapsed < 0.0005, f"Drone check took {elapsed*1e6:.1f}us (budget: 500us)"
