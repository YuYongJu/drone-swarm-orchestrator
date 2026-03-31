"""Tests for drone_swarm.mission_builder -- fluent mission builder API.

Covers building, validation, serialization (JSON roundtrip), and
waypoint generation for multi-drone missions.
"""

import json
import os
import tempfile

import pytest

from drone_swarm.drone import Waypoint
from drone_swarm.mission_builder import Mission, MissionBuilder

# Reference point: Mojave, California
REF_LAT = 35.363
REF_LON = -117.669
ALT = 20.0


# ---------------------------------------------------------------------------
# Build and validate
# ---------------------------------------------------------------------------

class TestBuildAndValidate:
    def test_build_returns_builder(self):
        builder = Mission.build("Test Mission")
        assert isinstance(builder, MissionBuilder)

    def test_basic_build_with_waypoints(self):
        mission = (
            Mission.build("Basic")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.001, REF_LON + 0.001, alt=ALT)
            .validate()
        )
        assert isinstance(mission, Mission)
        assert mission.name == "Basic"
        assert len(mission.waypoints) == 2

    def test_validate_fails_no_waypoints(self):
        with pytest.raises(ValueError, match="at least one waypoint"):
            Mission.build("Empty").validate()

    def test_validate_fails_empty_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            Mission.build("  ").add_waypoint(REF_LAT, REF_LON).validate()

    def test_invalid_lat_rejected(self):
        with pytest.raises(ValueError, match="lat"):
            Mission.build("Bad").add_waypoint(100.0, REF_LON)

    def test_invalid_lon_rejected(self):
        with pytest.raises(ValueError, match="lon"):
            Mission.build("Bad").add_waypoint(REF_LAT, 200.0)

    def test_negative_altitude_rejected(self):
        with pytest.raises(ValueError, match="alt"):
            Mission.build("Bad").add_waypoint(REF_LAT, REF_LON, alt=-5)


# ---------------------------------------------------------------------------
# Formation, geofence, speed, on_complete
# ---------------------------------------------------------------------------

class TestBuilderOptions:
    def test_set_formation(self):
        mission = (
            Mission.build("Formation")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .set_formation("line", spacing=10, heading=90)
            .validate()
        )
        assert mission.formation.pattern == "line"
        assert mission.formation.spacing == 10
        assert mission.formation.heading == 90

    def test_invalid_formation_rejected(self):
        with pytest.raises(ValueError, match="Invalid formation"):
            Mission.build("Bad").set_formation("zigzag")

    def test_set_geofence(self):
        polygon = [
            (35.36, -117.67), (35.37, -117.67),
            (35.37, -117.66), (35.36, -117.66),
        ]
        mission = (
            Mission.build("Fenced")
            .add_waypoint(35.365, -117.665, alt=ALT)
            .set_geofence(polygon=polygon, alt_max=50)
            .validate()
        )
        assert mission.geofence is not None
        assert len(mission.geofence.polygon) == 4
        assert mission.geofence.alt_max == 50

    def test_geofence_too_few_vertices(self):
        with pytest.raises(ValueError, match="at least 3"):
            Mission.build("Bad").set_geofence(polygon=[(0, 0), (1, 1)])

    def test_geofence_alt_violation(self):
        polygon = [
            (35.36, -117.67), (35.37, -117.67),
            (35.37, -117.66), (35.36, -117.66),
        ]
        with pytest.raises(ValueError, match="exceeds geofence"):
            (
                Mission.build("High")
                .add_waypoint(35.365, -117.665, alt=60)
                .set_geofence(polygon=polygon, alt_max=50)
                .validate()
            )

    def test_set_speed(self):
        mission = (
            Mission.build("Fast")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .set_speed(5.0)
            .validate()
        )
        assert mission.speed_ms == 5.0

    def test_invalid_speed_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            Mission.build("Bad").set_speed(0)

    def test_on_complete_rtl(self):
        mission = (
            Mission.build("RTL")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .on_complete("rtl")
            .validate()
        )
        assert mission.complete_action == "rtl"

    def test_on_complete_land(self):
        mission = (
            Mission.build("Land")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .on_complete("land")
            .validate()
        )
        assert mission.complete_action == "land"

    def test_on_complete_loiter(self):
        mission = (
            Mission.build("Loiter")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .on_complete("loiter")
            .validate()
        )
        assert mission.complete_action == "loiter"

    def test_invalid_on_complete_rejected(self):
        with pytest.raises(ValueError, match="Invalid on_complete"):
            Mission.build("Bad").on_complete("explode")

    def test_full_chain(self):
        """Full fluent chain with every option set."""
        polygon = [
            (35.36, -117.67), (35.37, -117.67),
            (35.37, -117.66), (35.36, -117.66),
        ]
        mission = (
            Mission.build("Pipeline Inspection Run 47")
            .add_waypoint(35.363, -117.669, alt=20)
            .add_waypoint(35.365, -117.665, alt=20)
            .set_formation("line", spacing=10)
            .set_geofence(polygon=polygon, alt_max=50)
            .set_speed(5.0)
            .on_complete("rtl")
            .validate()
        )
        assert mission.name == "Pipeline Inspection Run 47"
        assert len(mission.waypoints) == 2
        assert mission.formation.pattern == "line"
        assert mission.geofence is not None
        assert mission.speed_ms == 5.0
        assert mission.complete_action == "rtl"


# ---------------------------------------------------------------------------
# Serialization (JSON roundtrip)
# ---------------------------------------------------------------------------

class TestSerialization:
    def _build_mission(self) -> Mission:
        polygon = [
            (35.36, -117.67), (35.37, -117.67),
            (35.37, -117.66), (35.36, -117.66),
        ]
        return (
            Mission.build("Roundtrip Test")
            .add_waypoint(35.363, -117.669, alt=20)
            .add_waypoint(35.365, -117.665, alt=25)
            .set_formation("v", spacing=12)
            .set_geofence(polygon=polygon, alt_max=50)
            .set_speed(4.5)
            .on_complete("land")
            .validate()
        )

    def test_to_dict_and_from_dict(self):
        original = self._build_mission()
        data = original.to_dict()
        restored = Mission.from_dict(data)

        assert restored.name == original.name
        assert len(restored.waypoints) == len(original.waypoints)
        assert restored.formation.pattern == original.formation.pattern
        assert restored.formation.spacing == original.formation.spacing
        assert restored.geofence is not None
        assert len(restored.geofence.polygon) == 4
        assert restored.speed_ms == original.speed_ms
        assert restored.complete_action == original.complete_action

    def test_to_dict_roundtrip_json_safe(self):
        """to_dict output can survive JSON serialization."""
        original = self._build_mission()
        data = original.to_dict()
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        restored = Mission.from_dict(restored_data)
        assert restored.name == original.name
        assert len(restored.waypoints) == 2

    def test_save_and_load_json(self, tmp_path):
        original = self._build_mission()
        path = os.path.join(str(tmp_path), "missions", "test_mission.json")
        original.save_json(path)

        assert os.path.exists(path)

        loaded = Mission.load_json(path)
        assert loaded.name == original.name
        assert len(loaded.waypoints) == len(original.waypoints)
        assert loaded.formation.pattern == original.formation.pattern
        assert loaded.speed_ms == original.speed_ms
        assert loaded.complete_action == original.complete_action
        assert loaded.geofence is not None
        assert loaded.geofence.alt_max == original.geofence.alt_max

    def test_save_json_creates_directories(self, tmp_path):
        mission = (
            Mission.build("DirTest")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .validate()
        )
        nested = os.path.join(str(tmp_path), "a", "b", "c", "mission.json")
        mission.save_json(nested)
        assert os.path.exists(nested)

    def test_minimal_mission_roundtrip(self):
        """Mission with only required fields survives roundtrip."""
        original = (
            Mission.build("Minimal")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .validate()
        )
        data = original.to_dict()
        restored = Mission.from_dict(data)
        assert restored.name == "Minimal"
        assert len(restored.waypoints) == 1
        assert restored.speed_ms is None
        assert restored.complete_action is None
        assert restored.geofence is None


# ---------------------------------------------------------------------------
# Waypoint generation
# ---------------------------------------------------------------------------

class TestGenerateWaypoints:
    def test_round_robin_distribution(self):
        mission = (
            Mission.build("RoundRobin")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.001, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.002, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.003, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.004, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.005, REF_LON, alt=ALT)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=3)
        assert len(result) == 3
        # 6 waypoints / 3 drones = 2 each
        assert len(result[0]) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 2

    def test_formation_line_generates_per_drone(self):
        mission = (
            Mission.build("LineFormation")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.002, REF_LON + 0.002, alt=ALT)
            .set_formation("line", spacing=10)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=3)
        assert len(result) == 3
        # Each drone gets a waypoint per mission waypoint
        for drone_wps in result:
            assert len(drone_wps) == 2  # 2 waypoints in mission, 1 per drone per wp
            for wp in drone_wps:
                assert isinstance(wp, Waypoint)

    def test_formation_v_generates_per_drone(self):
        mission = (
            Mission.build("VFormation")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .set_formation("v", spacing=15)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=5)
        assert len(result) == 5
        for drone_wps in result:
            assert len(drone_wps) >= 1

    def test_geofence_polygon_sweep(self):
        polygon = [
            (35.36, -117.67), (35.37, -117.67),
            (35.37, -117.66), (35.36, -117.66),
        ]
        mission = (
            Mission.build("Sweep")
            .add_waypoint(35.365, -117.665, alt=ALT)
            .set_geofence(polygon=polygon, alt_max=50)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=2)
        assert len(result) == 2
        # Each drone should get at least some waypoints from the sweep
        total_wps = sum(len(wps) for wps in result)
        assert total_wps >= 2

    def test_zero_drones_returns_empty(self):
        mission = (
            Mission.build("Zero")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=0)
        assert result == []

    def test_single_drone_gets_all_waypoints(self):
        mission = (
            Mission.build("Solo")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.001, REF_LON, alt=ALT)
            .add_waypoint(REF_LAT + 0.002, REF_LON, alt=ALT)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=1)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_waypoints_are_waypoint_instances(self):
        mission = (
            Mission.build("TypeCheck")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .validate()
        )
        result = mission.generate_waypoints(num_drones=1)
        for wp in result[0]:
            assert isinstance(wp, Waypoint)


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr(self):
        mission = (
            Mission.build("Repr Test")
            .add_waypoint(REF_LAT, REF_LON, alt=ALT)
            .set_formation("v")
            .validate()
        )
        r = repr(mission)
        assert "Repr Test" in r
        assert "waypoints=1" in r
        assert "'v'" in r
