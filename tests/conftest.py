"""Shared fixtures for drone-swarm tests.

All fixtures here are designed to work WITHOUT pymavlink or ArduPilot SITL.
SITL integration tests (marked ``@pytest.mark.sitl``) are skipped by default;
pass ``--sitl`` to enable them.
"""

import pytest

from drone_swarm.config import SwarmConfig
from drone_swarm.drone import (
    Drone,
    DroneCapabilities,
    DroneRole,
    Waypoint,
)
from drone_swarm.swarm import SwarmOrchestrator


# ---------------------------------------------------------------------------
# --sitl CLI flag and automatic skip for @pytest.mark.sitl tests
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--sitl",
        action="store_true",
        default=False,
        help="Run SITL integration tests (requires a running SITL instance)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "sitl: mark test as requiring a running ArduPilot SITL instance",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--sitl"):
        # --sitl passed: don't skip SITL tests
        return
    skip_sitl = pytest.mark.skip(reason="SITL tests disabled (pass --sitl to run)")
    for item in items:
        if "sitl" in item.keywords:
            item.add_marker(skip_sitl)

# ---------------------------------------------------------------------------
# Basic data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_capabilities():
    """A DroneCapabilities with all defaults."""
    return DroneCapabilities()


@pytest.fixture
def sensor_capabilities():
    """A DroneCapabilities for a sensor-equipped drone."""
    return DroneCapabilities(
        hw_class="B",
        has_camera=True,
        has_compute=True,
        max_speed_ms=8.0,
        max_altitude_m=120.0,
        endurance_min=18.0,
    )


@pytest.fixture
def payload_capabilities():
    """A DroneCapabilities for a payload-carrying drone."""
    return DroneCapabilities(
        hw_class="D",
        has_camera=True,
        has_payload=True,
        max_speed_ms=4.0,
        max_altitude_m=80.0,
        endurance_min=8.0,
    )


@pytest.fixture
def sample_waypoint():
    """A waypoint near Edwards AFB, CA."""
    return Waypoint(lat=34.9592, lon=-117.8814, alt=10.0)


@pytest.fixture
def default_config():
    """A SwarmConfig with all defaults."""
    return SwarmConfig()


@pytest.fixture
def sample_drone():
    """A Drone in DISCONNECTED state with default capabilities."""
    return Drone(
        drone_id="alpha",
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
    )


@pytest.fixture
def orchestrator():
    """A SwarmOrchestrator with no drones registered (no pymavlink needed)."""
    return SwarmOrchestrator()


@pytest.fixture
def orchestrator_with_drones(orchestrator):
    """An orchestrator with 3 drones registered (DISCONNECTED, no connections)."""
    orchestrator.register_drone("alpha", "udp:127.0.0.1:14550", DroneRole.RECON)
    orchestrator.register_drone("bravo", "udp:127.0.0.1:14560", DroneRole.RELAY)
    orchestrator.register_drone(
        "charlie",
        "udp:127.0.0.1:14570",
        DroneRole.STRIKE,
        DroneCapabilities(hw_class="D", has_payload=True),
    )
    return orchestrator
