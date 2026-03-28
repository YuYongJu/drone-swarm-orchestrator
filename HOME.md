---
title: Drone Swarm Orchestrator
type: index
status: active
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, project-home, sdk, developer-platform]
related: [MESH_NETWORK_DESIGN, COMMS_PROTOCOL, GAP_ANALYSIS]
---

# Drone Swarm Orchestrator

An open-source Python SDK for multi-drone coordination -- `pip install drone-swarm`.

**"Stripe for Drones"** -- the developer platform that turns ArduPilot drones into coordinated fleets. Hardware-agnostic, simulation-first, built for developers building the next generation of drone applications.

```bash
pip install drone-swarm
```

```python
from drone_swarm import Swarm, Formation

swarm = Swarm.connect(["udp:127.0.0.1:14550", "udp:127.0.0.1:14560"])
swarm.arm_all()
swarm.takeoff(altitude=20)
swarm.fly_formation(Formation.V_SHAPE, spacing=10)
```

---

## Quick Status

| Item | Status |
|------|--------|
| Current Phase | Phase 0 Complete, Phase 1 In Progress |
| Next Step | SDK packaging + PyPI release + SITL simulation harness |
| Open Issues | 8 FAIL items from [[INTEGRATION_AUDIT]] to resolve before SDK v0.1 |
| Key Blocker | SDK API surface finalization |

---

## Who This Is For

| Audience | Use Case |
|----------|----------|
| **Drone application developers** | Build multi-drone apps (agriculture, SAR, inspection) without writing orchestration from scratch |
| **Precision agriculture companies** | Coordinate survey/spray fleets across large acreage |
| **Search-and-rescue teams** | Deploy coordinated grid searches with off-the-shelf drones |
| **Infrastructure inspection firms** | Automate multi-drone inspection workflows for utilities, bridges, pipelines |
| **Drone show operators** | Choreograph synchronized light shows with commodity hardware |
| **Wildfire response agencies** | Real-time perimeter mapping and hotspot monitoring with drone swarms |
| **Researchers and universities** | Testbed for swarm algorithms that runs on real hardware, not just simulation |

---

## Project Documents

### Product & Strategy

- [[PRODUCT_SPEC]] -- SDK product specification with prioritized feature list (P0-P3)
- [[BUSINESS_PLAN]] -- Open-core business model, market analysis, developer platform economics
- [[ROADMAP]] -- Phased development plan: SDK -> Cloud Dashboard -> Enterprise -> Marketplace

### Design

- [[UI_DESIGN]] -- Cloud dashboard and developer console UI/UX design
- [[SYSTEM_ARCHITECTURE]] -- Technical system architecture and module breakdown
- [[API_DESIGN]] -- Python SDK API surface + REST and WebSocket API specification
- [[MESH_NETWORK_DESIGN]] -- Mesh networking protocol (ESP32 + LoRa drone-to-drone comms)
- [[OPERATIONS_DESIGN]] -- Battery management, maintenance scheduling, logistics, training, weather, firmware updates
- [[GLOSSARY]] -- Definitions of key terms used across the project

### Quality

- [[TESTING_STRATEGY]] -- Testing approach across unit, integration, SITL, and field testing
- [[PRESSURE_TEST]] -- Independent engineering review of all design documents
- [[INTEGRATION_AUDIT]] -- Cross-document consistency audit with FAIL/WARNING/PASS items
- [[DECISION_LOG]] -- Record of key architectural and strategic decisions

### Hardware & Protocols

- [[HARDWARE_SPEC]] -- Bill of materials, assembly checklist, hardware capability classes
- [[COMMS_PROTOCOL]] -- MAVLink communication protocol, radio configuration, state machine
- [[MOTOR_TEST_PROTOCOL]] -- Step-by-step guide for running motor thrust tests on a test stand
- [[CG_MEASUREMENT_PROTOCOL]] -- How to measure and correct center of gravity on assembled drones

### SDK Source (`src/`)

- `src/swarm.py` -- Core swarm orchestrator: async state management, telemetry, command dispatch
- `src/mission_planner.py` -- Formation geometry: line, V-shape, area sweep, orbit patterns
- `src/firmware_flasher.py` -- Flash ArduPilot firmware and swarm parameters to flight controllers
- `src/fleet_registry.py` -- Drone registration via QR code or manual entry
- `src/preflight.py` -- Pre-flight check suite: comms, GPS, battery, compass, failsafe, Remote ID, vibration
- `src/demo.py` -- End-to-end integration demo script (3-drone formation flight)
- `src/calibration_engine.py` -- Auto-calibration system that learns from flight data to correct loadout checker predictions
- `src/mesh_protocol.py` -- Mesh networking protocol: binary message encoding, neighbour table, geographic routing
- `src/battery_tracker.py` -- Battery health tracking: cycle count, degradation model, puffing detection, retirement alerts
- `src/maintenance_tracker.py` -- Maintenance scheduling: flight hours, prop/motor hours, calibration tracking, crash inspection
- `src/api_server.py` -- Minimal FastAPI backend -- run with `python api_server.py` or `uvicorn api_server:app`
- `src/parts_db/` -- JSON parts database (motors, props, batteries, frames, ESCs, payloads) with thrust test data

### Wireframes

- `design/wireframe.html` -- Initial wireframe concept
- `design/wireframe-v2.html` -- V2 with marker-based drone tracking
- `design/wireframe-v3-markers.html` -- V3 with refined marker system
- `design/wireframe-v4-feeds.html` -- V4 feed-first UI design (current)
- `design/wireframe-full.png` -- V1 screenshot
- `design/wireframe-v2-full.png` -- V2 screenshot
- `design/wireframe-v3-full.png` -- V3 screenshot
- `design/wireframe-v4-full.png` -- V4 screenshot

### Reference

- [[ARCHITECTURE]] -- Earlier architecture overview (see [[SYSTEM_ARCHITECTURE]] for the current version)

---

#drone-swarm #project-home #sdk #developer-platform
