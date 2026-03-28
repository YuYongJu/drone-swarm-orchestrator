"""Tests for the behavior plugin system (drone_swarm.behavior).

Covers lifecycle hooks, priority ordering, event dispatch, and
integration with SwarmOrchestrator.
"""

import pytest

from drone_swarm.behavior import Behavior, BehaviorEvent, BehaviorRegistry
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Test behaviors
# ---------------------------------------------------------------------------

class TrackingBehavior(Behavior):
    """A test behavior that records all lifecycle calls."""

    def __init__(self, name: str = "tracker", priority: int = 0):
        self.name = name
        self.priority = priority
        self.calls: list[str] = []
        self.tick_count = 0
        self.events: list[BehaviorEvent] = []

    async def setup(self, swarm):
        self.calls.append("setup")

    async def on_tick(self, swarm, drones):
        self.calls.append("tick")
        self.tick_count += 1

    async def on_event(self, swarm, event):
        self.calls.append(f"event:{event.kind}")
        self.events.append(event)

    async def teardown(self, swarm):
        self.calls.append("teardown")


# ---------------------------------------------------------------------------
# BehaviorRegistry unit tests
# ---------------------------------------------------------------------------

class TestBehaviorRegistry:
    @pytest.mark.asyncio
    async def test_add_calls_setup(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()
        behavior = TrackingBehavior()

        await registry.add(behavior, swarm)

        assert "setup" in behavior.calls
        assert len(registry.behaviors) == 1

    @pytest.mark.asyncio
    async def test_remove_calls_teardown(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()
        behavior = TrackingBehavior()

        await registry.add(behavior, swarm)
        removed = await registry.remove("tracker", swarm)

        assert removed is behavior
        assert "teardown" in behavior.calls
        assert len(registry.behaviors) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_none(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        result = await registry.remove("nonexistent", swarm)
        assert result is None

    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        await registry.add(TrackingBehavior("dup"), swarm)
        with pytest.raises(ValueError, match="already registered"):
            await registry.add(TrackingBehavior("dup"), swarm)

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        low = TrackingBehavior("low", priority=1)
        high = TrackingBehavior("high", priority=10)
        mid = TrackingBehavior("mid", priority=5)

        await registry.add(low, swarm)
        await registry.add(high, swarm)
        await registry.add(mid, swarm)

        names = [b.name for b in registry.behaviors]
        assert names == ["high", "mid", "low"]

    @pytest.mark.asyncio
    async def test_tick_calls_all_enabled(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        b1 = TrackingBehavior("b1")
        b2 = TrackingBehavior("b2")
        await registry.add(b1, swarm)
        await registry.add(b2, swarm)

        await registry.tick(swarm, {})

        assert b1.tick_count == 1
        assert b2.tick_count == 1

    @pytest.mark.asyncio
    async def test_tick_skips_disabled(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        b = TrackingBehavior("disabled_b")
        b.enabled = False
        await registry.add(b, swarm)

        await registry.tick(swarm, {})

        assert b.tick_count == 0

    @pytest.mark.asyncio
    async def test_event_dispatch(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        b = TrackingBehavior()
        await registry.add(b, swarm)

        event = BehaviorEvent("drone_lost", "alpha")
        await registry.dispatch_event(swarm, event)

        assert len(b.events) == 1
        assert b.events[0].kind == "drone_lost"
        assert b.events[0].drone_id == "alpha"

    @pytest.mark.asyncio
    async def test_get_by_name(self):
        registry = BehaviorRegistry()
        swarm = SwarmOrchestrator()

        b = TrackingBehavior("findme")
        await registry.add(b, swarm)

        assert registry.get("findme") is b
        assert registry.get("nope") is None


# ---------------------------------------------------------------------------
# SwarmOrchestrator integration
# ---------------------------------------------------------------------------

class TestSwarmBehaviorIntegration:
    @pytest.mark.asyncio
    async def test_add_and_remove_behavior(self):
        swarm = SwarmOrchestrator()
        b = TrackingBehavior("patrol")

        await swarm.add_behavior(b)
        assert swarm.get_behavior("patrol") is b
        assert len(swarm.behaviors) == 1

        removed = await swarm.remove_behavior("patrol")
        assert removed is b
        assert len(swarm.behaviors) == 0
        assert "setup" in b.calls
        assert "teardown" in b.calls

    @pytest.mark.asyncio
    async def test_behavior_receives_drones(self):
        """Behaviors can see registered drones via on_tick."""
        swarm = SwarmOrchestrator()
        swarm.register_drone("alpha", "udp:127.0.0.1:14550")

        seen_drones: dict = {}

        class SpyBehavior(Behavior):
            name = "spy"

            async def on_tick(self, swarm, drones):
                seen_drones.update(drones)

        await swarm.add_behavior(SpyBehavior())
        await swarm._behavior_registry.tick(swarm, swarm.drones)

        assert "alpha" in seen_drones


# ---------------------------------------------------------------------------
# BehaviorEvent
# ---------------------------------------------------------------------------

class TestBehaviorEvent:
    def test_repr(self):
        e = BehaviorEvent("collision_risk", "bravo")
        assert "collision_risk" in repr(e)
        assert "bravo" in repr(e)

    def test_data_defaults_to_empty(self):
        e = BehaviorEvent("test")
        assert e.data == {}

    def test_data_preserved(self):
        e = BehaviorEvent("low_battery", "alpha", {"battery_pct": 15.0})
        assert e.data["battery_pct"] == 15.0
