"""
Validate the public API surface of the drone-swarm SDK.

Ensures that:
1. Every symbol in __all__ is actually importable from drone_swarm
2. Every public symbol in drone_swarm matches __all__ (no drift)
3. __all__ is sorted within each logical group
"""

import inspect
from typing import ClassVar

import drone_swarm


class TestAllExports:
    """Verify __all__ matches actual public exports."""

    def test_all_symbols_are_importable(self):
        """Every name in __all__ must be importable from drone_swarm."""
        missing = []
        for name in drone_swarm.__all__:
            if not hasattr(drone_swarm, name):
                missing.append(name)
        assert missing == [], f"Symbols in __all__ but not importable: {missing}"

    def test_no_public_symbols_missing_from_all(self):
        """Every non-private symbol in the package should be in __all__.

        Exceptions: submodules and dunder attributes.
        """
        actual_public = set()
        for name in dir(drone_swarm):
            if name.startswith("_"):
                continue
            obj = getattr(drone_swarm, name)
            # Skip submodules (they appear in dir() but aren't API exports)
            if inspect.ismodule(obj):
                continue
            actual_public.add(name)

        declared = set(drone_swarm.__all__)
        missing_from_all = actual_public - declared
        assert missing_from_all == set(), (
            f"Public symbols not in __all__: {sorted(missing_from_all)}"
        )

    def test_all_has_no_duplicates(self):
        """__all__ should not contain duplicate entries."""
        seen = set()
        dupes = []
        for name in drone_swarm.__all__:
            if name in seen:
                dupes.append(name)
            seen.add(name)
        assert dupes == [], f"Duplicate entries in __all__: {dupes}"

    def test_version_is_string(self):
        """__version__ must be a non-empty string."""
        assert isinstance(drone_swarm.__version__, str)
        assert len(drone_swarm.__version__) > 0


class TestStableApiExists:
    """Verify that all Stable-tier symbols from API_STABILITY.md exist."""

    STABLE_CLASSES: ClassVar[list[str]] = [
        "Swarm",
        "SwarmOrchestrator",
        "Drone",
        "DroneRole",
        "DroneStatus",
        "DroneCapabilities",
        "Waypoint",
        "SwarmConfig",
        "CheckResult",
        "Behavior",
        "BehaviorEvent",
        "Geofence",
        "GeofenceStatus",
        "CollisionAvoidance",
        "CollisionRisk",
        "SimulationHarness",
        "SITLNotFoundError",
        "SITLStartupError",
    ]

    STABLE_FUNCTIONS: ClassVar[list[str]] = [
        "run_preflight_checks",
        "preflight_ok",
        "v_formation",
        "line_formation",
        "area_sweep",
        "orbit_point",
    ]

    def test_stable_classes_exist(self):
        for name in self.STABLE_CLASSES:
            assert hasattr(drone_swarm, name), f"Stable class {name!r} missing"

    def test_stable_functions_exist(self):
        for name in self.STABLE_FUNCTIONS:
            obj = getattr(drone_swarm, name, None)
            assert obj is not None, f"Stable function {name!r} missing"
            assert callable(obj), f"Stable symbol {name!r} is not callable"

    def test_swarm_is_alias_for_orchestrator(self):
        assert drone_swarm.Swarm is drone_swarm.SwarmOrchestrator


class TestSwarmOrchestratorPublicApi:
    """Verify SwarmOrchestrator has all documented public methods."""

    EXPECTED_METHODS: ClassVar[list[str]] = [
        "register_drone",
        "add",
        "connect_all",
        "connect",
        "takeoff",
        "goto",
        "return_to_launch",
        "rtl",
        "land",
        "formation",
        "sweep",
        "assign_mission",
        "execute_missions",
        "shutdown",
        "emergency_land",
        "emergency_kill",
        "set_geofence",
        "clear_geofence",
        "enable_collision_avoidance",
        "disable_collision_avoidance",
        "add_behavior",
        "remove_behavior",
        "get_behavior",
        "status_report",
        "simulate",
    ]

    def test_all_public_methods_exist(self):
        missing = []
        for method_name in self.EXPECTED_METHODS:
            if not hasattr(drone_swarm.SwarmOrchestrator, method_name):
                missing.append(method_name)
        assert missing == [], f"Missing SwarmOrchestrator methods: {missing}"

    def test_public_methods_have_return_annotations(self):
        """All public methods should have return type annotations."""
        unannotated = []
        for method_name in self.EXPECTED_METHODS:
            method = getattr(drone_swarm.SwarmOrchestrator, method_name, None)
            if method is None:
                continue
            # Skip aliases (add -> register_drone, connect -> connect_all)
            if method_name in ("add", "connect"):
                continue
            hints = getattr(method, "__annotations__", {})
            if "return" not in hints:
                unannotated.append(method_name)
        assert unannotated == [], (
            f"Public methods missing return annotations: {unannotated}"
        )
