"""
Performance benchmark and iteration tracker for the drone-swarm SDK.

Measures and records performance metrics across algorithm iterations,
enabling comparison between different implementations (e.g., APF vs ORCA
collision avoidance, consensus vs waypoint formation control).

Usage::

    from drone_swarm.benchmarks import BenchmarkSuite, BenchmarkResult

    suite = BenchmarkSuite("collision_avoidance")
    suite.add_scenario("head_on_swap", setup_fn, run_fn, metrics_fn)
    results = await suite.run_all()
    suite.save("benchmarks/collision_v1.json")

    # Compare iterations
    from drone_swarm.benchmarks import compare_results
    compare_results("benchmarks/collision_v1.json", "benchmarks/collision_v2_orca.json")
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("drone_swarm.benchmarks")


@dataclass
class BenchmarkMetrics:
    """Metrics collected from a single benchmark run."""

    # Timing
    total_time_s: float = 0.0
    setup_time_s: float = 0.0
    execution_time_s: float = 0.0

    # Collision avoidance metrics
    min_separation_m: float = float("inf")
    collision_count: int = 0
    avoidance_interventions: int = 0
    avg_separation_m: float = 0.0

    # Formation metrics
    max_formation_error_m: float = 0.0
    avg_formation_error_m: float = 0.0
    formation_convergence_time_s: float = 0.0

    # Path planning metrics
    total_distance_m: float = 0.0
    path_smoothness: float = 0.0  # sum of heading changes (lower = smoother)
    energy_estimate_mah: float = 0.0

    # Task allocation metrics
    total_mission_time_s: float = 0.0
    idle_time_s: float = 0.0  # time drones spend not on task
    coverage_pct: float = 0.0

    # Communication metrics
    messages_sent: int = 0
    messages_lost: int = 0
    avg_latency_ms: float = 0.0

    # Custom metrics
    custom: dict[str, float] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of running a benchmark scenario multiple times."""

    scenario_name: str
    algorithm: str
    n_drones: int
    n_runs: int
    timestamp: str = ""

    # Aggregated metrics (mean across runs)
    mean_metrics: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    # Standard deviation
    std_metrics: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    # Best run
    best_metrics: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    # Worst run
    worst_metrics: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    # All individual runs
    all_runs: list[BenchmarkMetrics] = field(default_factory=list)


@dataclass
class BenchmarkScenario:
    """A single benchmark scenario definition."""

    name: str
    description: str
    n_drones: int = 3
    n_runs: int = 5
    setup_fn: Callable[..., Awaitable[Any]] | None = None
    run_fn: Callable[..., Awaitable[BenchmarkMetrics]] | None = None
    teardown_fn: Callable[..., Awaitable[None]] | None = None


class BenchmarkSuite:
    """
    A collection of benchmark scenarios for comparing algorithm performance.

    Example::

        suite = BenchmarkSuite("collision_avoidance")

        async def setup():
            swarm = Swarm()
            # ... set up drones
            return swarm

        async def run_head_on(swarm):
            # ... fly drones toward each other
            return BenchmarkMetrics(min_separation_m=3.2, collision_count=0)

        suite.add_scenario("head_on_swap", setup, run_head_on, n_drones=2)
        results = await suite.run_all()
        suite.save("benchmarks/results.json")
    """

    def __init__(self, name: str, algorithm: str = "default"):
        self.name = name
        self.algorithm = algorithm
        self.scenarios: list[BenchmarkScenario] = []
        self.results: list[BenchmarkResult] = []

    def add_scenario(
        self,
        name: str,
        setup_fn: Callable[..., Awaitable[Any]],
        run_fn: Callable[..., Awaitable[BenchmarkMetrics]],
        teardown_fn: Callable[..., Awaitable[None]] | None = None,
        description: str = "",
        n_drones: int = 3,
        n_runs: int = 5,
    ) -> None:
        """Register a benchmark scenario."""
        self.scenarios.append(BenchmarkScenario(
            name=name,
            description=description,
            n_drones=n_drones,
            n_runs=n_runs,
            setup_fn=setup_fn,
            run_fn=run_fn,
            teardown_fn=teardown_fn,
        ))

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all scenarios and collect results."""
        self.results = []
        for scenario in self.scenarios:
            logger.info("Running benchmark: %s (%d runs)", scenario.name, scenario.n_runs)
            result = await self._run_scenario(scenario)
            self.results.append(result)
            logger.info(
                "  %s: avg_time=%.3fs, min_sep=%.1fm, collisions=%d",
                scenario.name,
                result.mean_metrics.total_time_s,
                result.mean_metrics.min_separation_m,
                result.mean_metrics.collision_count,
            )
        return self.results

    async def _run_scenario(self, scenario: BenchmarkScenario) -> BenchmarkResult:
        """Run a single scenario N times and aggregate."""
        all_metrics: list[BenchmarkMetrics] = []

        for run_idx in range(scenario.n_runs):
            logger.debug("  Run %d/%d", run_idx + 1, scenario.n_runs)

            # Setup
            t0 = time.perf_counter()
            context = None
            if scenario.setup_fn:
                context = await scenario.setup_fn()
            setup_time = time.perf_counter() - t0

            # Execute
            t1 = time.perf_counter()
            metrics = BenchmarkMetrics()
            if scenario.run_fn:
                if context is not None:
                    metrics = await scenario.run_fn(context)
                else:
                    metrics = await scenario.run_fn()
            exec_time = time.perf_counter() - t1

            metrics.setup_time_s = setup_time
            metrics.execution_time_s = exec_time
            metrics.total_time_s = setup_time + exec_time

            # Teardown
            if scenario.teardown_fn:
                await scenario.teardown_fn(context) if context else await scenario.teardown_fn()

            all_metrics.append(metrics)

        return BenchmarkResult(
            scenario_name=scenario.name,
            algorithm=self.algorithm,
            n_drones=scenario.n_drones,
            n_runs=scenario.n_runs,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            mean_metrics=_aggregate_metrics(all_metrics, statistics.mean),
            std_metrics=_aggregate_metrics(all_metrics, _safe_stdev),
            best_metrics=_best_metrics(all_metrics),
            worst_metrics=_worst_metrics(all_metrics),
            all_runs=all_metrics,
        )

    def save(self, path: str | Path) -> None:
        """Save results to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "suite": self.name,
            "algorithm": self.algorithm,
            "results": [asdict(r) for r in self.results],
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Benchmark results saved to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> list[BenchmarkResult]:
        """Load results from JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        results = []
        for r in data["results"]:
            result = BenchmarkResult(
                scenario_name=r["scenario_name"],
                algorithm=r["algorithm"],
                n_drones=r["n_drones"],
                n_runs=r["n_runs"],
                timestamp=r.get("timestamp", ""),
            )
            result.mean_metrics = _dict_to_metrics(r.get("mean_metrics", {}))
            results.append(result)
        return results


def compare_results(
    path_a: str | Path,
    path_b: str | Path,
    metric_keys: list[str] | None = None,
) -> str:
    """
    Compare two benchmark result files and print a human-readable table.

    Args:
        path_a: Path to baseline results.
        path_b: Path to new results.
        metric_keys: Specific metrics to compare. If None, compares all non-zero metrics.

    Returns:
        Formatted comparison string.
    """
    results_a = BenchmarkSuite.load(path_a)
    results_b = BenchmarkSuite.load(path_b)

    lines = ["=" * 70]
    lines.append("BENCHMARK COMPARISON")
    lines.append(f"  A: {path_a}")
    lines.append(f"  B: {path_b}")
    lines.append("=" * 70)

    for ra in results_a:
        rb_match = next((r for r in results_b if r.scenario_name == ra.scenario_name), None)
        if rb_match is None:
            continue

        lines.append(f"\nScenario: {ra.scenario_name}")
        lines.append(f"  Algorithm A: {ra.algorithm} | Algorithm B: {rb_match.algorithm}")
        lines.append(f"  {'Metric':<30} {'A':>12} {'B':>12} {'Change':>12}")
        lines.append(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*12}")

        ma = asdict(ra.mean_metrics)
        mb = asdict(rb_match.mean_metrics)

        keys = metric_keys or [
            k for k in ma
            if k != "custom" and (ma[k] != 0 or mb[k] != 0)
        ]

        for key in keys:
            va = ma.get(key, 0)
            vb = mb.get(key, 0)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                if va != 0:
                    pct = ((vb - va) / abs(va)) * 100
                    change = f"{pct:+.1f}%"
                else:
                    change = "N/A"
                lines.append(f"  {key:<30} {va:>12.3f} {vb:>12.3f} {change:>12}")

    lines.append("\n" + "=" * 70)
    output = "\n".join(lines)
    print(output)
    return output


# -- Helpers ------------------------------------------------------------------

def _safe_stdev(values: list[float]) -> float:
    """Standard deviation that handles len < 2."""
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def _aggregate_metrics(
    runs: list[BenchmarkMetrics], agg_fn: Callable[[list[float]], float],
) -> BenchmarkMetrics:
    """Aggregate a list of metrics using the given function (mean, stdev, etc.)."""
    if not runs:
        return BenchmarkMetrics()

    result = BenchmarkMetrics()
    fields_to_agg = [
        "total_time_s", "setup_time_s", "execution_time_s",
        "min_separation_m", "collision_count", "avoidance_interventions",
        "avg_separation_m", "max_formation_error_m", "avg_formation_error_m",
        "formation_convergence_time_s", "total_distance_m", "path_smoothness",
        "energy_estimate_mah", "total_mission_time_s", "idle_time_s",
        "coverage_pct", "messages_sent", "messages_lost", "avg_latency_ms",
    ]
    for f in fields_to_agg:
        values = [getattr(r, f) for r in runs if getattr(r, f) != float("inf")]
        if values:
            setattr(result, f, agg_fn(values))

    return result


def _best_metrics(runs: list[BenchmarkMetrics]) -> BenchmarkMetrics:
    """Return the run with the lowest total_time_s."""
    if not runs:
        return BenchmarkMetrics()
    return min(runs, key=lambda m: m.total_time_s)


def _worst_metrics(runs: list[BenchmarkMetrics]) -> BenchmarkMetrics:
    """Return the run with the highest total_time_s."""
    if not runs:
        return BenchmarkMetrics()
    return max(runs, key=lambda m: m.total_time_s)


def _dict_to_metrics(d: dict) -> BenchmarkMetrics:
    """Convert a dict back to BenchmarkMetrics."""
    m = BenchmarkMetrics()
    for k, v in d.items():
        if k == "custom":
            m.custom = v or {}
        elif hasattr(m, k) and isinstance(v, (int, float)):
            setattr(m, k, v)
    return m
