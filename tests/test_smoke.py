"""
Smoke tests -- fast, offline sanity checks for the drone-swarm SDK.

These do NOT require pymavlink, SITL, or any external service. They verify
that the public API is importable, core objects can be instantiated, formation
patterns are callable, CLI commands parse without errors, and the version
string is valid semver.

Run with::

    pytest tests/test_smoke.py
"""

from __future__ import annotations

import re

import pytest


# ---------------------------------------------------------------------------
# 1. Public API imports
# ---------------------------------------------------------------------------

class TestPublicAPIImports:
    """Every symbol listed in ``drone_swarm.__all__`` should be importable."""

    def test_all_exports_importable(self):
        import drone_swarm

        missing = []
        for name in drone_swarm.__all__:
            if not hasattr(drone_swarm, name):
                missing.append(name)
        assert missing == [], f"Missing public API symbols: {missing}"

    def test_core_types_importable(self):
        from drone_swarm import (  # noqa: F401
            Drone,
            DroneCapabilities,
            DroneRole,
            DroneStatus,
            Swarm,
            SwarmConfig,
            SwarmOrchestrator,
            Waypoint,
        )

    def test_mission_functions_importable(self):
        from drone_swarm import (  # noqa: F401
            area_sweep,
            line_formation,
            orbit_point,
            polygon_sweep,
            v_formation,
        )

    def test_safety_importable(self):
        from drone_swarm import (  # noqa: F401
            CheckResult,
            preflight_ok,
            run_preflight_checks,
        )

    def test_collision_importable(self):
        from drone_swarm import (  # noqa: F401
            CollisionAvoidance,
            CollisionRisk,
            OrcaVelocity,
        )

    def test_formation_control_importable(self):
        from drone_swarm import (  # noqa: F401
            FormationController,
            FormationGains,
            compute_formation_error,
        )

    def test_health_importable(self):
        from drone_swarm import compute_health_score  # noqa: F401

    def test_anomaly_importable(self):
        from drone_swarm import Anomaly, AnomalyDetector  # noqa: F401

    def test_geofence_importable(self):
        from drone_swarm import Geofence, GeofenceStatus  # noqa: F401

    def test_battery_importable(self):
        from drone_swarm import BatteryConfig, BatteryPredictor  # noqa: F401

    def test_path_planner_importable(self):
        from drone_swarm import (  # noqa: F401
            PathPlanner,
            energy_cost,
            plan_multi_drone,
            smooth_trajectory,
        )

    def test_simulation_importable(self):
        from drone_swarm import (  # noqa: F401
            SimulationHarness,
            SITLNotFoundError,
            SITLStartupError,
        )

    def test_wind_importable(self):
        from drone_swarm import WindEstimate, WindEstimator  # noqa: F401


# ---------------------------------------------------------------------------
# 2. Swarm instantiation
# ---------------------------------------------------------------------------

class TestSwarmInstantiation:
    """Verify that Swarm() can be created without any external dependencies."""

    def test_swarm_creates_with_defaults(self):
        from drone_swarm import Swarm

        swarm = Swarm()
        assert swarm.drones == {}
        assert swarm._running is False

    def test_swarm_alias_is_orchestrator(self):
        from drone_swarm import Swarm, SwarmOrchestrator

        assert Swarm is SwarmOrchestrator

    def test_swarm_with_custom_config(self):
        from drone_swarm import Swarm, SwarmConfig

        cfg = SwarmConfig(default_altitude_m=25.0)
        swarm = Swarm(config=cfg)
        assert swarm._config.default_altitude_m == 25.0

    def test_register_drone_without_connection(self):
        from drone_swarm import Swarm

        swarm = Swarm()
        swarm.add("test-drone", "udp:127.0.0.1:14550")
        assert "test-drone" in swarm.drones


# ---------------------------------------------------------------------------
# 3. Formation patterns callable
# ---------------------------------------------------------------------------

class TestFormationPatternsCallable:
    """All formation/mission generators should run offline with valid args."""

    def test_v_formation(self):
        from drone_swarm import v_formation

        plans = v_formation(35.0, -117.0, 10.0, 3, 15.0, 0.0)
        assert len(plans) == 3
        for wp_list in plans:
            assert len(wp_list) >= 1

    def test_line_formation(self):
        from drone_swarm import line_formation

        plans = line_formation(35.0, -117.0, 10.0, 3, 15.0, 0.0)
        assert len(plans) == 3

    def test_orbit_point(self):
        from drone_swarm import orbit_point

        plans = orbit_point(35.0, -117.0, 10.0, 20.0, 3)
        assert len(plans) == 3

    def test_area_sweep(self):
        from drone_swarm import area_sweep

        plans = area_sweep(35.0, -117.0, 35.001, -116.999, 10.0, 2)
        assert len(plans) == 2

    def test_polygon_sweep(self):
        from drone_swarm import polygon_sweep

        polygon = [
            (35.0, -117.0),
            (35.001, -117.0),
            (35.001, -116.999),
            (35.0, -116.999),
        ]
        plans = polygon_sweep(polygon, 10.0, 2)
        assert len(plans) == 2


# ---------------------------------------------------------------------------
# 4. CLI commands parse without error
# ---------------------------------------------------------------------------

class TestCLIParsing:
    """The CLI parser should accept all documented sub-commands and flags."""

    def test_build_parser_returns_parser(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        assert parser is not None

    def test_version_subcommand(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_init_subcommand(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"

    def test_init_force_flag(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["init", "--force"])
        assert args.force is True

    def test_simulate_subcommand_defaults(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["simulate"])
        assert args.command == "simulate"
        assert args.drones == 3
        assert args.speedup == 1

    def test_simulate_custom_args(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["simulate", "--drones", "5", "--speedup", "2"])
        assert args.drones == 5
        assert args.speedup == 2

    def test_status_subcommand(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["status", "--connection", "tcp:127.0.0.1:5760"])
        assert args.command == "status"
        assert args.connection == "tcp:127.0.0.1:5760"

    def test_preflight_subcommand(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "preflight",
            "--connection", "tcp:127.0.0.1:5760",
            "--id", "alpha",
        ])
        assert args.command == "preflight"
        assert args.id == "alpha"

    def test_no_command_returns_none(self):
        from drone_swarm.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_main_no_args_returns_zero(self):
        """``dso`` with no arguments prints help and returns 0."""
        from drone_swarm.cli import main

        rc = main([])
        assert rc == 0

    def test_main_version_returns_zero(self):
        from drone_swarm.cli import cmd_version

        # Build a namespace manually to avoid SystemExit from --version flag
        import argparse

        ns = argparse.Namespace()
        rc = cmd_version(ns)
        assert rc == 0


# ---------------------------------------------------------------------------
# 5. Version string is valid semver
# ---------------------------------------------------------------------------

class TestVersionString:
    """The package version must be a valid semver string."""

    # Matches MAJOR.MINOR.PATCH with optional pre-release and build metadata.
    _SEMVER_RE = re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    def test_version_from_package(self):
        from drone_swarm import __version__

        assert self._SEMVER_RE.match(__version__), (
            f"__version__ = {__version__!r} is not valid semver"
        )

    def test_version_from_version_module(self):
        from drone_swarm._version import __version__

        assert self._SEMVER_RE.match(__version__), (
            f"_version.__version__ = {__version__!r} is not valid semver"
        )

    def test_versions_match(self):
        from drone_swarm import __version__ as pkg_version
        from drone_swarm._version import __version__ as mod_version

        assert pkg_version == mod_version, (
            f"Package version {pkg_version!r} != _version module {mod_version!r}"
        )
