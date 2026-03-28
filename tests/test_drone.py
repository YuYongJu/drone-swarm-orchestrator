"""Tests for drone_swarm.drone -- enums, dataclasses, and state transitions."""

from dataclasses import fields

import pytest

from drone_swarm.drone import (
    VALID_TRANSITIONS,
    DroneCapabilities,
    DroneRole,
    DroneStatus,
    Waypoint,
)

# ---------------------------------------------------------------------------
# DroneRole enum
# ---------------------------------------------------------------------------

class TestDroneRole:
    def test_has_all_expected_members(self):
        expected = {"RECON", "RELAY", "STRIKE", "DECOY"}
        assert {r.name for r in DroneRole} == expected

    def test_values_are_lowercase(self):
        for role in DroneRole:
            assert role.value == role.name.lower()

    def test_construction_from_value(self):
        assert DroneRole("recon") is DroneRole.RECON
        assert DroneRole("strike") is DroneRole.STRIKE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DroneRole("bomber")


# ---------------------------------------------------------------------------
# DroneStatus enum
# ---------------------------------------------------------------------------

class TestDroneStatus:
    def test_has_all_expected_members(self):
        expected = {
            "DISCONNECTED", "CONNECTED", "ARMED",
            "AIRBORNE", "RETURNING", "LANDED", "LOST",
        }
        assert {s.name for s in DroneStatus} == expected

    def test_values_are_lowercase(self):
        for status in DroneStatus:
            assert status.value == status.name.lower()

    def test_every_status_has_transitions_entry(self):
        """Every status must appear as a key in VALID_TRANSITIONS."""
        for status in DroneStatus:
            assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"

    def test_disconnected_can_only_reach_connected(self):
        assert VALID_TRANSITIONS[DroneStatus.DISCONNECTED] == {DroneStatus.CONNECTED}

    def test_airborne_cannot_go_directly_to_landed(self):
        assert DroneStatus.LANDED not in VALID_TRANSITIONS[DroneStatus.AIRBORNE]

    def test_lost_can_recover_to_connected_or_disconnect(self):
        allowed = VALID_TRANSITIONS[DroneStatus.LOST]
        assert DroneStatus.CONNECTED in allowed
        assert DroneStatus.DISCONNECTED in allowed


# ---------------------------------------------------------------------------
# DroneCapabilities dataclass
# ---------------------------------------------------------------------------

class TestDroneCapabilities:
    def test_defaults(self, default_capabilities):
        caps = default_capabilities
        assert caps.hw_class == "A"
        assert caps.has_camera is False
        assert caps.has_compute is False
        assert caps.has_payload is False
        assert caps.max_speed_ms == 5.0
        assert caps.max_altitude_m == 100.0
        assert caps.endurance_min == 12.0

    def test_custom_values(self, sensor_capabilities):
        caps = sensor_capabilities
        assert caps.hw_class == "B"
        assert caps.has_camera is True
        assert caps.has_compute is True
        assert caps.max_speed_ms == 8.0

    def test_is_dataclass(self):
        assert len(fields(DroneCapabilities)) > 0


# ---------------------------------------------------------------------------
# Waypoint dataclass
# ---------------------------------------------------------------------------

class TestWaypoint:
    def test_construction(self, sample_waypoint):
        wp = sample_waypoint
        assert wp.lat == pytest.approx(34.9592)
        assert wp.lon == pytest.approx(-117.8814)
        assert wp.alt == pytest.approx(10.0)

    def test_equality(self):
        a = Waypoint(1.0, 2.0, 3.0)
        b = Waypoint(1.0, 2.0, 3.0)
        assert a == b

    def test_inequality(self):
        a = Waypoint(1.0, 2.0, 3.0)
        b = Waypoint(1.0, 2.0, 4.0)
        assert a != b


# ---------------------------------------------------------------------------
# Drone dataclass
# ---------------------------------------------------------------------------

class TestDrone:
    def test_default_state_is_disconnected(self, sample_drone):
        assert sample_drone.status == DroneStatus.DISCONNECTED

    def test_default_role_is_recon(self, sample_drone):
        assert sample_drone.role == DroneRole.RECON

    def test_default_battery_is_full(self, sample_drone):
        assert sample_drone.battery_pct == 100.0

    def test_mission_starts_empty(self, sample_drone):
        assert sample_drone.mission == []

    def test_connection_defaults_to_none(self, sample_drone):
        assert sample_drone.connection is None

    def test_default_position_is_zero(self, sample_drone):
        assert sample_drone.lat == 0.0
        assert sample_drone.lon == 0.0
        assert sample_drone.alt == 0.0
