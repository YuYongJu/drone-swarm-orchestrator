# drone-swarm

**Coordinate multiple ArduPilot drones with Python.**

drone-swarm is an open-source SDK that turns a collection of ArduPilot-compatible drones into a coordinated swarm. Connect, takeoff, fly formations, execute missions, and land — all from a simple Python API.

```python
from drone_swarm import Swarm

async def main():
    swarm = Swarm()
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5762")
    swarm.add("charlie", "tcp:127.0.0.1:5763")

    await swarm.connect()
    await swarm.takeoff(altitude=10)
    await swarm.formation("v", spacing=15)
    await swarm.rtl()
    await swarm.shutdown()
```

## Why drone-swarm?

| Problem | Status Quo | drone-swarm |
|---------|-----------|-------------|
| Coordinate multiple drones | Write raw MAVLink from scratch | `swarm.formation("v")` |
| Test without hardware | Set up SITL manually per drone | `Swarm.simulate(n=5)` |
| Handle failures mid-flight | Hope for the best | Auto-failsafe + replanning |
| Switch autopilots | Rewrite everything | Same API for ArduPilot + PX4 |

## Quick Install

```bash
pip install drone-swarm
```

Then follow the [Quickstart Guide](getting-started/quickstart.md) to fly your first simulated swarm in under 5 minutes.

## Features

- **Swarm coordination** — synchronized takeoff, landing, formations, and missions
- **Formation flying** — V-shape, line, grid, circle, orbit, and custom formations
- **Mission planning** — area sweep, patrol, follow, and intercept patterns
- **Safety first** — preflight checks, geofencing, emergency stop, heartbeat monitoring
- **Simulation** — built-in SITL launcher for testing without hardware
- **Hardware-agnostic** — works with any ArduPilot-compatible flight controller
- **Async-native** — built on asyncio for concurrent multi-drone operations
- **Extensible** — plugin system for custom missions and sensors

## Who is this for?

- **Developers** building drone applications (agriculture, inspection, SAR, security)
- **Researchers** studying swarm robotics and multi-agent coordination
- **Students** learning about autonomous systems and MAVLink
- **Startups** building commercial drone services
- **Defense integrators** needing an open, auditable swarm layer

## License

drone-swarm is licensed under the [MIT License](https://opensource.org/licenses/MIT). Use it however you want.
