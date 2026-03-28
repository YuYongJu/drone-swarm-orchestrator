"""
Pre-built benchmark scenarios for comparing algorithm iterations.

Usage::

    from benchmarks.scenarios import collision_benchmarks, formation_benchmarks
    from drone_swarm.benchmarks import BenchmarkSuite

    suite = collision_benchmarks(algorithm="orca_v1")
    results = await suite.run_all()
    suite.save("benchmarks/results/collision_orca_v1.json")
"""

from __future__ import annotations

import math

from drone_swarm.benchmarks import BenchmarkMetrics, BenchmarkSuite
from drone_swarm.collision import CollisionAvoidance, haversine
from drone_swarm.drone import Drone, DroneRole, DroneStatus, Waypoint


def _make_drone(drone_id: str, lat: float, lon: float, alt: float = 20.0) -> Drone:
    """Create a test drone at a specific position."""
    d = Drone(drone_id=drone_id, connection_string="test://mock")
    d.lat = lat
    d.lon = lon
    d.alt = alt
    d.status = DroneStatus.AIRBORNE
    return d


# -- Collision Avoidance Benchmarks -------------------------------------------

def collision_benchmarks(algorithm: str = "default", min_dist: float = 5.0) -> BenchmarkSuite:
    """Create a benchmark suite for collision avoidance algorithms."""
    suite = BenchmarkSuite("collision_avoidance", algorithm=algorithm)

    async def setup_head_on():
        """Two drones flying directly at each other."""
        ca = CollisionAvoidance(min_distance_m=min_dist)
        d1 = _make_drone("d1", 35.3630, -117.6690)
        d2 = _make_drone("d2", 35.3630, -117.6691)  # ~9m apart
        return {"ca": ca, "drones": {"d1": d1, "d2": d2}}

    async def run_head_on(ctx):
        ca = ctx["ca"]
        drones = ctx["drones"]
        risks = ca.check_all_pairs(drones)
        metrics = BenchmarkMetrics()
        if risks:
            metrics.collision_count = 0
            metrics.avoidance_interventions = len(risks)
            metrics.min_separation_m = risks[0].distance_m
            wp_a, wp_b = ca.compute_avoidance(
                drones["d1"], drones["d2"], ca.min_distance_m,
            )
            # Verify avoidance pushes them apart
            new_dist = haversine(wp_a.lat, wp_a.lon, wp_b.lat, wp_b.lon)
            metrics.avg_separation_m = new_dist
            metrics.custom["separation_increase_m"] = new_dist - risks[0].distance_m
        else:
            d1, d2 = drones["d1"], drones["d2"]
            metrics.min_separation_m = haversine(d1.lat, d1.lon, d2.lat, d2.lon)
        return metrics

    suite.add_scenario(
        "head_on_2_drones", setup_head_on, run_head_on,
        description="Two drones 9m apart, below min distance",
        n_drones=2, n_runs=10,
    )

    async def setup_five_tight():
        """Five drones in a tight cluster."""
        ca = CollisionAvoidance(min_distance_m=min_dist)
        base_lat, base_lon = 35.3630, -117.6690
        drones = {}
        for i in range(5):
            angle = 2 * math.pi * i / 5
            offset_lat = 0.00002 * math.cos(angle)  # ~2m radius
            offset_lon = 0.00002 * math.sin(angle)
            drones[f"d{i}"] = _make_drone(
                f"d{i}", base_lat + offset_lat, base_lon + offset_lon,
            )
        return {"ca": ca, "drones": drones}

    async def run_five_tight(ctx):
        ca = ctx["ca"]
        drones = ctx["drones"]
        risks = ca.check_all_pairs(drones)
        metrics = BenchmarkMetrics()
        metrics.avoidance_interventions = len(risks)
        if risks:
            metrics.min_separation_m = min(r.distance_m for r in risks)
            metrics.avg_separation_m = sum(r.distance_m for r in risks) / len(risks)
        return metrics

    suite.add_scenario(
        "five_drones_tight_cluster", setup_five_tight, run_five_tight,
        description="Five drones in ~2m radius cluster",
        n_drones=5, n_runs=10,
    )

    async def setup_ten_random():
        """Ten drones at various positions."""
        import random
        random.seed(42)
        ca = CollisionAvoidance(min_distance_m=min_dist)
        drones = {}
        for i in range(10):
            drones[f"d{i}"] = _make_drone(
                f"d{i}",
                35.3630 + random.uniform(-0.0005, 0.0005),
                -117.6690 + random.uniform(-0.0005, 0.0005),
            )
        return {"ca": ca, "drones": drones}

    async def run_ten_random(ctx):
        ca = ctx["ca"]
        drones = ctx["drones"]
        import time
        t0 = time.perf_counter()
        risks = ca.check_all_pairs(drones)
        solve_time = time.perf_counter() - t0
        metrics = BenchmarkMetrics()
        metrics.execution_time_s = solve_time
        metrics.avoidance_interventions = len(risks)
        if risks:
            metrics.min_separation_m = min(r.distance_m for r in risks)
        metrics.custom["solve_time_ms"] = solve_time * 1000
        return metrics

    suite.add_scenario(
        "ten_drones_random", setup_ten_random, run_ten_random,
        description="Ten drones at random positions, measure solve time",
        n_drones=10, n_runs=20,
    )

    return suite


# -- Formation Benchmarks -----------------------------------------------------

def formation_benchmarks(algorithm: str = "default") -> BenchmarkSuite:
    """Create a benchmark suite for formation control algorithms."""
    suite = BenchmarkSuite("formation_control", algorithm=algorithm)

    async def setup_v_formation():
        from drone_swarm.missions import v_formation
        plans = v_formation(35.3630, -117.6690, 20.0, 5, 15.0, 0.0)
        drones = {}
        for i, waypoints in enumerate(plans):
            d = _make_drone(f"d{i}", 35.3630, -117.6690 + i * 0.0001)
            drones[f"d{i}"] = d
        return {"plans": plans, "drones": drones}

    async def run_v_formation(ctx):
        plans = ctx["plans"]
        drones = ctx["drones"]
        metrics = BenchmarkMetrics()
        errors = []
        for i, (drone_id, drone) in enumerate(drones.items()):
            if plans[i]:
                target = plans[i][0]
                error = haversine(drone.lat, drone.lon, target.lat, target.lon)
                errors.append(error)
        if errors:
            metrics.max_formation_error_m = max(errors)
            metrics.avg_formation_error_m = sum(errors) / len(errors)
        return metrics

    suite.add_scenario(
        "v_formation_5_drones", setup_v_formation, run_v_formation,
        description="V-formation with 5 drones, measure position error",
        n_drones=5, n_runs=5,
    )

    return suite
