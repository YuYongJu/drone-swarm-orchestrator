---
title: Swarm Communication Protocol
type: protocol
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, comms, mavlink]
---

# Swarm Communication Protocol

## Overview

```
                    ┌─────────────────────┐
                    │   Ground Station     │
                    │   (Python + Laptop)  │
                    └──┬──────┬──────┬────┘
                       │      │      │
                   SiK 915MHz Radio (MAVLink)
                   (dedicated link per drone)
                       │      │      │
                    ┌──┴──┐┌──┴──┐┌──┴──┐
                    │Alpha││Bravo││Charlie│
                    └─────┘└─────┘└──────┘
```

## Layer 1: Physical — SiK 915MHz Telemetry Radio

- **Why SiK**: Cheap ($15/pair), 1+ km range, MAVLink-native, no config needed
- **Topology**: Star — each drone has a dedicated radio link to ground station
- **Baud rate**: 57600 (default SiK)
- **Frequency**: 915MHz (US) or 433MHz (EU/other) — check your local regs
- **Channels**: Each pair on a different NetID to avoid interference

### Setup per radio pair:
```
Radio A (ground) → USB to laptop, NetID=25 (drone alpha)
Radio B (ground) → USB to laptop, NetID=26 (drone bravo)
Radio C (ground) → USB to laptop, NetID=27 (drone charlie)
Each drone has the matching radio with same NetID.
```

## Layer 2: Protocol — MAVLink v2

- **Why MAVLink**: Industry standard for drone comms, ArduPilot speaks it natively
- **Version**: MAVLink v2 (signing capable, extensible)
- **System IDs**: Each drone gets a unique SYSID_THISMAV (1, 2, 3...)
- **Ground station**: SYSID = 255 (GCS convention)

### Key message types used:

| Message | Direction | Purpose |
|---------|-----------|---------|
| HEARTBEAT | Drone → GCS | "I'm alive" (1Hz) |
| GLOBAL_POSITION_INT | Drone → GCS | GPS position, altitude, heading |
| SYS_STATUS | Drone → GCS | Battery, sensor health |
| COMMAND_LONG | GCS → Drone | Arm, takeoff, mode changes |
| SET_POSITION_TARGET_GLOBAL_INT | GCS → Drone | Go to waypoint |
| MISSION_ITEM_INT | GCS → Drone | Upload mission waypoints |
| STATUSTEXT | Drone → GCS | Human-readable status messages |

## Layer 3: Orchestration Protocol (our custom layer)

Built on top of MAVLink — the orchestrator translates high-level swarm
commands into per-drone MAVLink messages.

### Command flow:

```
Operator: "Formation V, heading north, move to grid X"
    │
    ▼
Orchestrator: computes per-drone waypoints from formation geometry
    │
    ├──→ Alpha: SET_POSITION_TARGET (leader position)
    ├──→ Bravo: SET_POSITION_TARGET (left wing position)
    └──→ Charlie: SET_POSITION_TARGET (right wing position)
```

### State machine per drone:

```
DISCONNECTED → CONNECTED → ARMED → AIRBORNE → RETURNING → LANDED
                                       │
                                       └──→ LOST (heartbeat timeout)
```

### Failsafe behaviors:

| Condition | Action |
|-----------|--------|
| Heartbeat lost > 5s | Mark LOST, replan around missing unit |
| Battery < 20% | Auto-RTL that drone, replan swarm |
| GCS radio lost (drone side) | ArduPilot failsafe: RTL after 30s |
| All comms lost | Each drone RTLs independently (firmware-level) |

## Future: Mesh Networking (Phase 2+)

Star topology doesn't scale past ~5-8 drones (USB port limit, bandwidth).
Phase 2 would add drone-to-drone mesh:

- **Hardware**: ESP32 with LoRa (SX1276) on each drone — ~$8/module
- **Protocol**: Custom lightweight packets for swarm state sharing
- **Benefit**: Drones can relay commands, share position, coordinate
  without ground station (critical for denied comms environments)

## Radio Configuration Checklist

For each SiK radio pair:
1. Set matching NetID (unique per pair)
2. Set AIR_SPEED to 64 (good balance of range vs throughput)
3. Set MAVLINK to 2 (MAVLink v2 framing)
4. Set MAX_WINDOW to 131 (better for telemetry)
5. Verify with Mission Planner → Setup → Optional Hardware → SiK Radio

---

## Related Documents

- [[HARDWARE_SPEC]] -- Radio hardware specifications and BOM
- [[SYSTEM_ARCHITECTURE]] -- Orchestrator that sits above this protocol layer
- [[API_DESIGN]] -- API commands that translate to MAVLink messages
- [[INTEGRATION_AUDIT]] -- Protocol-to-code state machine audit
- [[GLOSSARY]] -- MAVLink, SiK, and protocol terminology
- [[DECISION_LOG]] -- Star topology decision rationale
