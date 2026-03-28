---
title: Decision Log
type: reference
status: in-progress
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, decisions, architecture]
---

# Decision Log

Key architectural, strategic, and engineering decisions made during the design of the Drone Swarm Orchestrator.

---

## DEC-001: ArduPilot over PX4

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Use ArduPilot as the primary flight controller firmware |
| Alternatives | PX4, custom firmware |
| Rationale | ArduPilot has a larger community, more mature documentation, better support for budget hardware (SpeedyBee F405), and the most complete MAVLink implementation via pymavlink. PX4 is supported as secondary but not the development target. Custom firmware was rejected as unnecessary -- the project focuses on swarm intelligence above the autopilot layer. |
| Status | Confirmed |
| References | [[ARCHITECTURE]], [[HARDWARE_SPEC]], [[COMMS_PROTOCOL]] |

---

## DEC-002: Python + Next.js Stack

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Python for the orchestrator backend, Next.js for the ground station UI |
| Alternatives | Rust + Tauri, C++ + Qt, Go + HTMX, Electron + Node.js |
| Rationale | pymavlink is the most mature MAVLink library and is Python-native. Python's asyncio provides adequate performance for command dispatch at ~10Hz. Next.js enables rapid UI development with React components and can be deployed as a web app or wrapped in Electron for offline use. The team has strongest expertise in this stack. |
| Status | Confirmed |
| References | [[SYSTEM_ARCHITECTURE]], [[API_DESIGN]] |

---

## DEC-003: asyncio over Threads

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Rewrite swarm.py to use asyncio instead of threading |
| Alternatives | Threading with locks, multiprocessing, Trio |
| Rationale | The original threaded model created race conditions in shared drone state (identified in [[PRESSURE_TEST]]). asyncio provides cooperative concurrency with explicit yield points, making state access patterns predictable. Per-drone asyncio locks replace the global state dict. Trio was considered but asyncio has broader ecosystem support. |
| Status | Confirmed |
| References | [[PRESSURE_TEST]], [[SYSTEM_ARCHITECTURE]] |

---

## DEC-004: 4S Battery over 3S

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Recommend 4S 3000mAh LiPo as the standard battery |
| Alternatives | 3S 2200mAh, 4S 2200mAh, 6S 1300mAh |
| Rationale | The 3S 2200mAh originally specified provided only 8-12 minutes of flight time, which is insufficient for meaningful multi-drone missions. The 4S 3000mAh provides 12-15 minutes at a modest weight increase (~250g vs ~180g). The 2212 920KV motors handle 4S voltage well. 6S was rejected as overkill for the F450 frame class and requires more expensive ESCs. |
| Status | Confirmed |
| References | [[HARDWARE_SPEC]], [[PRESSURE_TEST]] |

---

## DEC-005: Star Topology First, Mesh in Phase 3

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Start with star topology (dedicated SiK radio per drone), introduce mesh networking in Phase 3 |
| Alternatives | Mesh from day one, WiFi mesh, cellular backhaul |
| Rationale | Star topology with SiK radios is dead simple: plug in USB radios, assign NetIDs, and MAVLink just works. No custom firmware, no mesh routing complexity. This is sufficient for 3-5 drones. Mesh networking (ESP32 + LoRa) begins integration in Phase 3 when scaling past 5-8 drones makes star topology impractical due to USB hub limits and RF interference. WiFi mesh has insufficient range; cellular adds latency and infrastructure dependency. |
| Status | Confirmed |
| References | [[COMMS_PROTOCOL]], [[ROADMAP]], [[SYSTEM_ARCHITECTURE]] |

---

## DEC-006: Feed-First UI Design

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Design the ground station UI around a real-time feed/dashboard model with the map as the primary view |
| Alternatives | Tab-based navigation, wizard-style workflow, terminal-only interface |
| Rationale | Field operators need at-a-glance situational awareness. The feed-first design puts the map with live drone positions front and center, with telemetry cards, alerts, and controls accessible without navigating away. Wireframe iterations (v1 through v4) validated this approach. Terminal-only was rejected as unusable for non-technical operators (Phase 2 target). |
| Status | Confirmed |
| References | [[UI_DESIGN]], [[PRODUCT_SPEC]] |

---

## DEC-007: Open-Source Core with Commercial Defense Layer

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Release the core orchestrator as open-source (Apache 2.0); defense features (encryption, IFF, ATAK) under commercial license |
| Alternatives | Fully proprietary, fully open-source, freemium SaaS only |
| Rationale | Open-source core builds community, credibility, and a hiring pipeline. Defense customers can audit the code. The defense layer (mesh encryption, IFF, ATAK integration) is the monetization path and likely ITAR-controlled regardless. Fully proprietary loses community leverage. Fully open-source has no revenue model for defense R&D. Open core is the proven model (GitLab, Elastic, HashiCorp). |
| Status | Confirmed |
| References | [[BUSINESS_PLAN]], [[ROADMAP]] |

---

## DEC-008: Two-Tier Emergency Stop

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Decision | Implement two distinct emergency actions: E-LAND (controlled descent) and KILL MOTORS (immediate disarm) |
| Alternatives | Single emergency stop, three-tier (pause/land/kill), software-only kill |
| Rationale | A single emergency stop is ambiguous -- sometimes you need drones to land safely (E-LAND), other times you need immediate motor cutoff regardless of consequences (KILL). The [[PRESSURE_TEST]] identified the need for escalating emergency responses. E-LAND commands LAND mode for controlled descent; KILL MOTORS force-disarms and the drone drops. Both bypass command locks and require no confirmation. The UI uses distinct colors and positions to prevent accidental activation. |
| Status | Confirmed |
| References | [[UI_DESIGN]], [[PRESSURE_TEST]], [[API_DESIGN]] |

---

## Related Documents

- [[PRESSURE_TEST]] -- Engineering review that drove several decisions
- [[SYSTEM_ARCHITECTURE]] -- Technical architecture reflecting these decisions
- [[BUSINESS_PLAN]] -- Business model decisions
- [[ROADMAP]] -- Phased implementation of decisions
