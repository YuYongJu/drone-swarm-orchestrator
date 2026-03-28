"""Tests for drone_swarm.swarm -- orchestrator, state machine, registration.

All tests run WITHOUT pymavlink connections or SITL. We only exercise the
orchestrator's in-memory logic: registration, state transitions, role
validation, status reporting, and replanning.
"""

import pytest

from drone_swarm.config import SwarmConfig
from drone_swarm.drone import (
    DroneCapabilities,
    DroneRole,
    DroneStatus,
)
from drone_swarm.swarm import Swarm, SwarmOrchestrator

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegisterDrone:
    def test_register_adds_drone(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550")
        assert "alpha" in orchestrator.drones

    def test_register_creates_lock(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550")
        assert "alpha" in orchestrator._drone_locks

    def test_registered_drone_starts_disconnected(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550")
        assert orchestrator.drones["alpha"].status == DroneStatus.DISCONNECTED

    def test_register_with_role(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550", DroneRole.STRIKE)
        assert orchestrator.drones["alpha"].role == DroneRole.STRIKE

    def test_register_with_capabilities(self, orchestrator):
        caps = DroneCapabilities(hw_class="D", has_payload=True)
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550", capabilities=caps)
        assert orchestrator.drones["alpha"].capabilities.has_payload is True

    def test_add_is_alias_for_register(self, orchestrator):
        # Bound methods are not identity-equal, so compare underlying functions
        assert orchestrator.add.__func__ is orchestrator.register_drone.__func__

    def test_register_multiple_drones(self, orchestrator_with_drones):
        assert len(orchestrator_with_drones.drones) == 3


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_valid_transition_succeeds(self):
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        result = await orch._transition("alpha", DroneStatus.CONNECTED)
        assert result is True
        assert orch.drones["alpha"].status == DroneStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_invalid_transition_fails(self):
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        # DISCONNECTED -> ARMED is not valid
        result = await orch._transition("alpha", DroneStatus.ARMED)
        assert result is False
        # Status should remain DISCONNECTED
        assert orch.drones["alpha"].status == DroneStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_full_lifecycle_forward(self):
        """Walk through DISCONNECTED -> CONNECTED -> ARMED -> AIRBORNE -> RETURNING -> LANDED."""
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")

        path = [
            DroneStatus.CONNECTED,
            DroneStatus.ARMED,
            DroneStatus.AIRBORNE,
            DroneStatus.RETURNING,
            DroneStatus.LANDED,
        ]
        for status in path:
            result = await orch._transition("alpha", status)
            assert result is True, f"Transition to {status} should succeed"
            assert orch.drones["alpha"].status == status

    @pytest.mark.asyncio
    async def test_airborne_to_landed_is_invalid(self):
        """Drones must go through RETURNING before landing."""
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        await orch._transition("alpha", DroneStatus.CONNECTED)
        await orch._transition("alpha", DroneStatus.ARMED)
        await orch._transition("alpha", DroneStatus.AIRBORNE)
        result = await orch._transition("alpha", DroneStatus.LANDED)
        assert result is False

    @pytest.mark.asyncio
    async def test_lost_recovery(self):
        """A LOST drone can recover to CONNECTED."""
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        await orch._transition("alpha", DroneStatus.CONNECTED)
        await orch._transition("alpha", DroneStatus.ARMED)
        await orch._transition("alpha", DroneStatus.AIRBORNE)
        await orch._transition("alpha", DroneStatus.LOST)
        result = await orch._transition("alpha", DroneStatus.CONNECTED)
        assert result is True


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class TestOrchestratorConfig:
    def test_default_config_applied(self, orchestrator):
        assert orchestrator.HEARTBEAT_TIMEOUT == 15.0
        assert orchestrator.BATTERY_RTL_THRESHOLD == 20.0

    def test_custom_config_applied(self):
        cfg = SwarmConfig.from_dict(
            {"heartbeat_timeout_s": 30.0, "battery_rtl_threshold_pct": 25.0},
        )
        orch = SwarmOrchestrator(config=cfg)
        assert orch.HEARTBEAT_TIMEOUT == 30.0
        assert orch.BATTERY_RTL_THRESHOLD == 25.0


# ---------------------------------------------------------------------------
# Role validation & auto-assign
# ---------------------------------------------------------------------------

class TestRoleValidation:
    def test_recon_requires_camera(self, orchestrator):
        orchestrator.register_drone(
            "alpha", "udp:127.0.0.1:14550",
            capabilities=DroneCapabilities(has_camera=False),
        )
        assert orchestrator.validate_role("alpha", DroneRole.RECON) is False

    def test_recon_with_camera_passes(self, orchestrator):
        orchestrator.register_drone(
            "alpha", "udp:127.0.0.1:14550",
            capabilities=DroneCapabilities(has_camera=True),
        )
        assert orchestrator.validate_role("alpha", DroneRole.RECON) is True

    def test_strike_requires_payload(self, orchestrator):
        orchestrator.register_drone(
            "alpha", "udp:127.0.0.1:14550",
            capabilities=DroneCapabilities(has_payload=False),
        )
        assert orchestrator.validate_role("alpha", DroneRole.STRIKE) is False

    def test_relay_always_valid(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550")
        assert orchestrator.validate_role("alpha", DroneRole.RELAY) is True

    def test_decoy_always_valid(self, orchestrator):
        orchestrator.register_drone("alpha", "udp:127.0.0.1:14550")
        assert orchestrator.validate_role("alpha", DroneRole.DECOY) is True


class TestAutoAssignRoles:
    def test_auto_assigns_based_on_capabilities(self, orchestrator):
        orchestrator.register_drone(
            "alpha", "udp:127.0.0.1:14550",
            capabilities=DroneCapabilities(has_camera=True),
        )
        orchestrator.register_drone(
            "bravo", "udp:127.0.0.1:14560",
            capabilities=DroneCapabilities(has_payload=True),
        )
        orchestrator.register_drone(
            "charlie", "udp:127.0.0.1:14570",
            capabilities=DroneCapabilities(),  # no camera, no payload
        )
        orchestrator.auto_assign_roles()
        assert orchestrator.drones["alpha"].role == DroneRole.RECON
        assert orchestrator.drones["bravo"].role == DroneRole.STRIKE
        assert orchestrator.drones["charlie"].role == DroneRole.RELAY


# ---------------------------------------------------------------------------
# Status & helpers
# ---------------------------------------------------------------------------

class TestStatusReport:
    def test_status_report_includes_all_drones(self, orchestrator_with_drones):
        report = orchestrator_with_drones.status_report()
        assert "alpha" in report
        assert "bravo" in report
        assert "charlie" in report

    def test_status_report_header(self, orchestrator_with_drones):
        report = orchestrator_with_drones.status_report()
        assert "SWARM STATUS" in report


class TestActiveDrones:
    @pytest.mark.asyncio
    async def test_no_active_when_all_disconnected(self):
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        assert orch.active_drones() == []

    @pytest.mark.asyncio
    async def test_active_includes_airborne(self):
        orch = SwarmOrchestrator()
        orch.register_drone("alpha", "udp:127.0.0.1:14550")
        await orch._transition("alpha", DroneStatus.CONNECTED)
        await orch._transition("alpha", DroneStatus.ARMED)
        await orch._transition("alpha", DroneStatus.AIRBORNE)
        assert "alpha" in orch.active_drones()


# ---------------------------------------------------------------------------
# Swarm alias
# ---------------------------------------------------------------------------

class TestSwarmAlias:
    def test_swarm_is_orchestrator(self):
        assert Swarm is SwarmOrchestrator
