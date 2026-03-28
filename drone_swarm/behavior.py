"""
Behavior plugin system for extensible swarm logic.

Behaviors are the primary extension point for the drone-swarm SDK. They run
inside the telemetry loop and can react to swarm state at ~10 Hz without
modifying core SDK code.

Inspired by Brooks' subsumption architecture (1986) and modern game-engine
component patterns (Unity MonoBehaviour, Godot Node). Each behavior has
lifecycle hooks that the orchestrator calls automatically.

Usage::

    from drone_swarm.behavior import Behavior

    class PatrolBehavior(Behavior):
        name = "patrol"

        async def on_tick(self, swarm, drones):
            for drone_id, drone in drones.items():
                if drone.battery_pct < 30:
                    await swarm.return_to_launch(drone_id)

    swarm.add_behavior(PatrolBehavior())
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .drone import Drone
    from .swarm import SwarmOrchestrator

logger = logging.getLogger("drone_swarm.behavior")


class BehaviorEvent:
    """An event dispatched to behaviors.

    Attributes:
        kind: Event type string (e.g., ``"drone_lost"``, ``"geofence_breach"``).
        drone_id: ID of the drone that triggered the event, if applicable.
        data: Arbitrary event-specific payload.
    """

    __slots__ = ("data", "drone_id", "kind")

    def __init__(
        self,
        kind: str,
        drone_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.kind = kind
        self.drone_id = drone_id
        self.data = data or {}

    def __repr__(self) -> str:
        return f"BehaviorEvent({self.kind!r}, drone_id={self.drone_id!r})"


class Behavior:
    """Base class for swarm behaviors.

    Subclass this and override the lifecycle hooks you need. Register
    instances on the orchestrator with ``swarm.add_behavior()``.

    Lifecycle (called by the telemetry loop)::

        setup()          -- once, when the behavior is added
        on_tick()        -- every telemetry cycle (~10 Hz)
        on_event()       -- when a specific event occurs
        teardown()       -- once, when the behavior is removed

    Attributes:
        name: Human-readable identifier. Must be unique per swarm.
        priority: Higher priority behaviors run first. Collision avoidance
            should have higher priority than mission behaviors.
        enabled: Set to ``False`` to temporarily skip without removing.
    """

    name: str = "unnamed"
    priority: int = 0
    enabled: bool = True

    async def setup(self, swarm: SwarmOrchestrator) -> None:
        """Called once when the behavior is added to the swarm.

        Use this to initialize state, subscribe to events, or validate
        that the swarm is configured correctly for this behavior.
        """

    async def on_tick(
        self,
        swarm: SwarmOrchestrator,
        drones: dict[str, Drone],
    ) -> None:
        """Called every telemetry cycle (~10 Hz) with current drone states.

        This is the main hook for reactive behaviors. Keep it fast —
        anything over ~10ms will delay the telemetry loop.

        Args:
            swarm: The orchestrator instance (for sending commands).
            drones: Snapshot of all registered drones with current telemetry.
        """

    async def on_event(
        self,
        swarm: SwarmOrchestrator,
        event: BehaviorEvent,
    ) -> None:
        """Called when a specific event occurs.

        Built-in event kinds:

        - ``"drone_lost"`` — heartbeat timeout, drone marked LOST
        - ``"drone_connected"`` — successful MAVLink connection
        - ``"geofence_breach"`` — drone left the geofence boundary
        - ``"geofence_warning"`` — drone near the geofence boundary
        - ``"collision_risk"`` — pair of drones too close
        - ``"low_battery"`` — battery below RTL threshold
        - ``"mission_complete"`` — drone finished all waypoints
        - ``"health_critical"`` — health score dropped below 25

        Args:
            swarm: The orchestrator instance.
            event: The event with kind, drone_id, and data payload.
        """

    async def teardown(self, swarm: SwarmOrchestrator) -> None:
        """Called once when the behavior is removed from the swarm.

        Use this to clean up state, cancel tasks, or release resources.
        """


class BehaviorRegistry:
    """Manages registered behaviors and dispatches lifecycle calls.

    The orchestrator owns one registry. Behaviors are stored sorted by
    priority (highest first) so higher-priority behaviors execute before
    lower-priority ones each tick.
    """

    def __init__(self) -> None:
        self._behaviors: list[Behavior] = []

    @property
    def behaviors(self) -> list[Behavior]:
        """All registered behaviors, sorted by priority (highest first)."""
        return list(self._behaviors)

    def get(self, name: str) -> Behavior | None:
        """Look up a behavior by name."""
        for b in self._behaviors:
            if b.name == name:
                return b
        return None

    async def add(
        self, behavior: Behavior, swarm: SwarmOrchestrator,
    ) -> None:
        """Register a behavior and call its ``setup()`` hook."""
        if self.get(behavior.name) is not None:
            raise ValueError(
                f"Behavior {behavior.name!r} is already registered. "
                f"Remove it first or use a different name."
            )
        self._behaviors.append(behavior)
        self._behaviors.sort(key=lambda b: b.priority, reverse=True)
        await behavior.setup(swarm)
        logger.info(
            "Behavior %r added (priority=%d)", behavior.name, behavior.priority,
        )

    async def remove(
        self, name: str, swarm: SwarmOrchestrator,
    ) -> Behavior | None:
        """Unregister a behavior by name and call its ``teardown()`` hook."""
        behavior = self.get(name)
        if behavior is None:
            return None
        self._behaviors.remove(behavior)
        await behavior.teardown(swarm)
        logger.info("Behavior %r removed", name)
        return behavior

    async def tick(
        self,
        swarm: SwarmOrchestrator,
        drones: dict[str, Drone],
    ) -> None:
        """Call ``on_tick()`` on all enabled behaviors (highest priority first)."""
        for behavior in self._behaviors:
            if behavior.enabled:
                try:
                    await behavior.on_tick(swarm, drones)
                except Exception:
                    logger.exception(
                        "Error in behavior %r on_tick", behavior.name,
                    )

    async def dispatch_event(
        self,
        swarm: SwarmOrchestrator,
        event: BehaviorEvent,
    ) -> None:
        """Dispatch an event to all enabled behaviors."""
        for behavior in self._behaviors:
            if behavior.enabled:
                try:
                    await behavior.on_event(swarm, event)
                except Exception:
                    logger.exception(
                        "Error in behavior %r on_event(%s)",
                        behavior.name, event.kind,
                    )
