"""Deployment verification smoke test.

Run after pip-installing the built wheel to verify that
the package is importable and basic functionality works.
"""

import drone_swarm

# Verify all key exports are importable
exports = [
    "Swarm", "Drone", "DroneStatus", "Waypoint",
    "CollisionAvoidance", "Geofence", "PathPlanner",
    "FormationController", "SwarmConfig", "__version__",
]
for name in exports:
    assert hasattr(drone_swarm, name), f"Missing export: {name}"

print(f"drone-swarm {drone_swarm.__version__} installed and importable")
assert drone_swarm.__version__, "Version string is empty"

# Quick functional check
swarm = drone_swarm.Swarm()
swarm.add("test", "udp:127.0.0.1:14550")
assert "test" in swarm.drones
assert swarm.drones["test"].status == drone_swarm.DroneStatus.DISCONNECTED
print("Functional smoke test passed")
