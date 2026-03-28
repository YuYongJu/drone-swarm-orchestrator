---
title: Software Architecture (Legacy)
type: design
status: needs-review
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, architecture]
---

> **Note:** This is the earlier architecture overview. See [[SYSTEM_ARCHITECTURE]] for the current, comprehensive system architecture document.

# Software Architecture — Drone Swarm Orchestrator

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GROUND STATION (Laptop)                      │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Operator UI  │  │   Mission    │  │    Swarm Orchestrator    │  │
│  │  (Phase 2:    │→ │   Planner    │→ │                          │  │
│  │  Next.js app) │  │              │  │  - State management      │  │
│  └──────────────┘  │  - Formation  │  │  - Telemetry aggregation │  │
│                     │  - Sweep      │  │  - Command dispatch      │  │
│                     │  - Orbit      │  │  - Failsafe logic        │  │
│                     │  - Custom     │  │  - Mission execution     │  │
│                     └──────────────┘  └─────┬──┬──┬──────────────┘  │
│                                             │  │  │                  │
│                                         MAVLink connections         │
│                                         (SiK 915MHz radios)        │
└─────────────────────────────────────────────┼──┼──┼─────────────────┘
                                              │  │  │
                                    ┌─────────┘  │  └─────────┐
                                    ▼            ▼            ▼
                               ┌────────┐  ┌────────┐  ┌────────┐
                               │ Drone  │  │ Drone  │  │ Drone  │
                               │ Alpha  │  │ Bravo  │  │Charlie │
                               │        │  │        │  │        │
                               │ArduPilot│ │ArduPilot│ │ArduPilot│
                               └────────┘  └────────┘  └────────┘
```

## Module Breakdown

### 1. SwarmOrchestrator (`swarm.py`) — Core

The central brain. Responsibilities:
- Maintain drone registry (ID, connection, role, status)
- Background telemetry loop (position, battery, heartbeat monitoring)
- Translate high-level commands (takeoff_all, assign_mission) to per-drone MAVLink
- Failsafe enforcement (lost contact → replan, low battery → RTL)
- Concurrent mission execution (one thread per drone)

### 2. Mission Planner (`mission_planner.py`) — Tactics

Pure functions that compute waypoint lists from geometric parameters:
- `line_formation()` — drones in a row
- `v_formation()` — V-shape with configurable angle
- `area_sweep()` — divide-and-conquer area coverage
- `orbit_point()` — circle a point of interest

These are stateless — they just return lists of Waypoints.
The orchestrator feeds them into `assign_mission()`.

### 3. Demo Script (`demo.py`) — Integration Test

End-to-end demo: connect → takeoff → V-formation → area sweep → RTL.
Works with both real hardware and SITL (Software In The Loop) simulation.

## Development Phases

### Phase 1: Core Orchestration (NOW — weeks 1-3)
```
src/
├── swarm.py             ✅ Multi-drone connection, telemetry, commands
├── mission_planner.py   ✅ Formation and sweep patterns
├── demo.py              ✅ Integration demo script
└── requirements.txt     ✅ pymavlink, dronekit
```

### Phase 2: Ground Station UI (month 2)
```
ground-station/          Next.js + Vercel app
├── app/
│   ├── page.tsx         Map view (Mapbox/Leaflet) with drone positions
│   ├── api/
│   │   ├── swarm/       WebSocket endpoint for live telemetry
│   │   └── command/     REST endpoints for swarm commands
│   └── components/
│       ├── DroneMap     Real-time drone positions on map
│       ├── SwarmPanel   Formation controls, mission builder
│       ├── Telemetry    Per-drone status cards
│       └── Timeline     Mission progress visualization
├── lib/
│   └── mavlink-bridge   Node.js ↔ Python bridge (child process or WebSocket)
```

### Phase 3: Autonomy Layer (month 3-4)
```
src/
├── autonomy/
│   ├── path_planner.py     Obstacle-aware pathfinding (A* / RRT)
│   ├── collision_avoid.py  Inter-drone deconfliction
│   ├── dynamic_replan.py   Replan when drones are lost/added
│   └── task_allocator.py   Optimal role assignment (Hungarian algorithm)
```

### Phase 4: IFF + Targeting (month 5+, requires clearances)
```
src/
├── iff/
│   ├── transponder.py      Encrypted beacon verification
│   ├── cv_classifier.py    On-board visual identification
│   └── blue_force.py       Friendly position overlay from C2
```

## Key Design Decisions

1. **Star topology first, mesh later** — USB radios are simpler and
   sufficient for 3-5 drones. Mesh adds complexity we don't need yet.

2. **ArduPilot as firmware, not custom** — battle-tested, massive community,
   handles low-level flight control. We focus on swarm intelligence above it.

3. **Python for orchestration** — pymavlink is the most mature MAVLink
   library. Performance isn't a bottleneck (commands are <1KB, ~10Hz).

4. **Stateless mission planner** — formations are pure geometry.
   The orchestrator owns all state. This makes testing trivial.

5. **Thread-per-drone for missions** — simple concurrency model.
   Drones execute independently; the orchestrator monitors all.

## Simulation (SITL) Setup

Test without hardware using ArduPilot SITL:

```bash
# Terminal 1 — drone alpha
sim_vehicle.py -v ArduCopter --instance 0 --out=udp:127.0.0.1:14550

# Terminal 2 — drone bravo
sim_vehicle.py -v ArduCopter --instance 1 --out=udp:127.0.0.1:14560

# Terminal 3 — drone charlie
sim_vehicle.py -v ArduCopter --instance 2 --out=udp:127.0.0.1:14570

# Terminal 4 — run the demo
cd src && python demo.py
```

---

## Related Documents

- [[SYSTEM_ARCHITECTURE]] -- Current, comprehensive system architecture (supersedes this document)
- [[COMMS_PROTOCOL]] -- Communication protocol details
- [[HARDWARE_SPEC]] -- Hardware specifications
- [[DECISION_LOG]] -- Architecture decision rationale
