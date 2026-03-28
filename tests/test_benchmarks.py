"""Tests for the benchmark and performance tracking system."""

import json

import pytest

from drone_swarm.benchmarks import (
    BenchmarkMetrics,
    BenchmarkResult,
    BenchmarkSuite,
    compare_results,
)


class TestBenchmarkMetrics:
    def test_defaults(self):
        m = BenchmarkMetrics()
        assert m.total_time_s == 0.0
        assert m.collision_count == 0
        assert m.min_separation_m == float("inf")

    def test_custom_metrics(self):
        m = BenchmarkMetrics(custom={"my_metric": 42.0})
        assert m.custom["my_metric"] == 42.0


class TestBenchmarkSuite:
    @pytest.fixture()
    def suite(self):
        return BenchmarkSuite("test_suite", algorithm="test_algo")

    def test_init(self, suite):
        assert suite.name == "test_suite"
        assert suite.algorithm == "test_algo"
        assert suite.scenarios == []

    def test_add_scenario(self, suite):
        async def setup():
            return {"drones": 3}

        async def run(ctx):
            return BenchmarkMetrics(total_time_s=1.5, collision_count=0)

        suite.add_scenario("test_scenario", setup, run, n_drones=3, n_runs=2)
        assert len(suite.scenarios) == 1
        assert suite.scenarios[0].name == "test_scenario"
        assert suite.scenarios[0].n_drones == 3
        assert suite.scenarios[0].n_runs == 2

    @pytest.mark.asyncio
    async def test_run_all(self, suite):
        async def setup():
            return {}

        async def run(ctx):
            return BenchmarkMetrics(
                total_time_s=1.0,
                min_separation_m=5.5,
                collision_count=0,
            )

        suite.add_scenario("simple", setup, run, n_runs=3)
        results = await suite.run_all()

        assert len(results) == 1
        r = results[0]
        assert r.scenario_name == "simple"
        assert r.algorithm == "test_algo"
        assert r.n_runs == 3
        assert len(r.all_runs) == 3
        assert r.mean_metrics.collision_count == 0
        assert r.mean_metrics.min_separation_m == 5.5

    @pytest.mark.asyncio
    async def test_run_with_varying_metrics(self, suite):
        call_count = 0

        async def setup():
            return {}

        async def run(ctx):
            nonlocal call_count
            call_count += 1
            return BenchmarkMetrics(
                total_time_s=float(call_count),
                collision_count=call_count,
            )

        suite.add_scenario("varying", setup, run, n_runs=3)
        results = await suite.run_all()

        r = results[0]
        assert len(r.all_runs) == 3
        # Mean of 1, 2, 3 = 2.0
        assert r.mean_metrics.collision_count == 2.0
        # Best = shortest time (1.0)
        assert r.best_metrics.total_time_s < r.worst_metrics.total_time_s

    def test_save_and_load(self, suite, tmp_path):
        result = BenchmarkResult(
            scenario_name="test",
            algorithm="algo_v1",
            n_drones=3,
            n_runs=1,
            mean_metrics=BenchmarkMetrics(
                total_time_s=2.5,
                min_separation_m=4.0,
                collision_count=1,
            ),
        )
        suite.results = [result]

        path = tmp_path / "results.json"
        suite.save(path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["suite"] == "test_suite"
        assert len(data["results"]) == 1

        loaded = BenchmarkSuite.load(path)
        assert len(loaded) == 1
        assert loaded[0].scenario_name == "test"
        assert loaded[0].algorithm == "algo_v1"
        assert loaded[0].mean_metrics.total_time_s == 2.5


class TestCompareResults:
    def test_compare(self, tmp_path):
        # Create two result files
        suite_a = BenchmarkSuite("collision", algorithm="apf_v1")
        suite_a.results = [BenchmarkResult(
            scenario_name="head_on",
            algorithm="apf_v1",
            n_drones=2,
            n_runs=5,
            mean_metrics=BenchmarkMetrics(
                total_time_s=10.0,
                min_separation_m=3.0,
                collision_count=2,
            ),
        )]

        suite_b = BenchmarkSuite("collision", algorithm="orca_v1")
        suite_b.results = [BenchmarkResult(
            scenario_name="head_on",
            algorithm="orca_v1",
            n_drones=2,
            n_runs=5,
            mean_metrics=BenchmarkMetrics(
                total_time_s=8.0,
                min_separation_m=5.0,
                collision_count=0,
            ),
        )]

        path_a = tmp_path / "apf.json"
        path_b = tmp_path / "orca.json"
        suite_a.save(path_a)
        suite_b.save(path_b)

        output = compare_results(path_a, path_b)
        assert "head_on" in output
        assert "apf_v1" in output
        assert "orca_v1" in output
        assert "-20.0%" in output  # total_time improved
