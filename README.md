# drone-swarm

**Python SDK for multi-drone swarm orchestration.**

[![PyPI version](https://img.shields.io/pypi/v/drone-swarm)](https://pypi.org/project/drone-swarm/)
[![Downloads](https://img.shields.io/pepy/dt/drone-swarm)](https://pepy.tech/project/drone-swarm)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://img.shields.io/github/actions/workflow/status/YuYongJu/drone-swarm-orchestrator/ci.yml?label=CI)](https://github.com/YuYongJu/drone-swarm-orchestrator/actions)
[![Python](https://img.shields.io/pypi/pyversions/drone-swarm)](https://pypi.org/project/drone-swarm/)

> **Status: alpha (0.1.x).** The SDK runs against SITL and the test suite passes, but the project is pre-1.0 — expect API breakage between minor versions, and don't fly real hardware off this without your own preflight and safety review. Production drone work needs more eyes than a single maintainer.

Turn a collection of ArduPilot drones into a coordinated swarm with 10 lines of Python.

```python
from drone_swarm import Swarm
import asyncio

async def main():
    swarm = Swarm()
    swarm.add("alpha", "udp:127.0.0.1:14550")
    swarm.add("bravo", "udp:127.0.0.1:14560")
    await swarm.connect()
    await swarm.takeoff(altitude=10)
    await swarm.formation("v", spacing=15)
    await swarm.rtl()

asyncio.run(main())
```

## Why drone-swarm?

| Problem | Status Quo | drone-swarm |
|---|---|---|
| Coordinate multiple drones | Raw MAVLink from scratch | `swarm.formation("v")` |
| Test without hardware | Manual SITL setup per drone | `Swarm.simulate(n=5)` |
| Handle mid-flight failures | Hope for the best | Auto-failsafe + replanning |
| Preflight safety checks | DIY scripts | `run_preflight_checks()` |

## Features

- **Swarm coordination** -- synchronized takeoff, landing, RTL, and formations
- **Formation flying** -- V-shape, line, grid, circle, orbit, and custom patterns
- **Mission planning** -- area sweep, patrol, orbit point, and intercept
- **Safety first** -- preflight checks (GPS, battery, compass, failsafes, Remote ID, vibration), geofencing, emergency land/kill
- **Simulation** -- built-in SITL launcher for hardware-free testing
- **Async-native** -- built on asyncio for concurrent multi-drone I/O
- **Telemetry** -- real-time position, battery, and heartbeat monitoring with auto-RTL on low battery
- **Configurable** -- YAML/dict config with sensible defaults

## Quick Install

```bash
pip install drone-swarm
```

Requires Python 3.11+. For simulation support:

```bash
pip install drone-swarm[sim]
```

## Documentation

Full docs, tutorials, and API reference: [docs/index.md](docs/index.md)

## Who is this for?

- **Developers** prototyping drone applications (agriculture, inspection, SAR, mapping) on SITL
- **Researchers** studying swarm robotics and multi-agent coordination
- **Students** learning autonomous systems and MAVLink

Not yet recommended for production commercial or defense deployments — the surface area is real but the operational hours behind it are not.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/yuyongju/drone-swarm.git
cd drone-swarm
pip install -e ".[dev]"
pytest
```

## License

MIT License. See [LICENSE](LICENSE) for details.
