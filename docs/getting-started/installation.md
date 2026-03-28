# Installation

## Requirements

- Python 3.11 or newer
- pip 21.0 or newer

## Install from PyPI

```bash
pip install drone-swarm
```

## Install with extras

```bash
# Simulation support (ArduPilot SITL helpers)
pip install drone-swarm[sim]

# Development (tests, linting)
pip install drone-swarm[dev]

# Everything
pip install drone-swarm[all]
```

## Install from source

```bash
git clone https://github.com/yuyongju/drone-swarm-orchestrator.git
cd drone-swarm-orchestrator
pip install -e ".[dev]"
```

## Verify installation

```python
import drone_swarm
print(drone_swarm.__version__)
# 0.1.0
```

## Next steps

- [Quickstart Guide](quickstart.md) — fly your first simulated swarm in 5 minutes
- [Core Concepts](concepts.md) — understand how drone-swarm works
