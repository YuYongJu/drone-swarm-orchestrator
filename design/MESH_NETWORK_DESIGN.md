---
title: Mesh Network Design
type: design
status: draft
phase: 3
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, mesh-network, lora, esp32, comms]
---

# Mesh Network Design

Phase 3 feature: drone-to-drone mesh networking using ESP32 + LoRa (SX1276) on each drone.

---

## A. Overview

The mesh network enables:

- **Drone-to-drone communication** without routing through the ground station
- **Range extension** via multi-hop relay -- drones beyond direct radio range can be reached through intermediaries
- **Swarm coordination in degraded environments** -- GPS-denied, comms-degraded, or electronic warfare scenarios
- **Ground station failover** -- if the SiK radio link to the ground station is lost, drones can still coordinate formation, share position, and execute missions via the mesh

This supplements (does not replace) the primary SiK 915MHz MAVLink radio link described in [[COMMS_PROTOCOL]]. The SiK link remains the high-bandwidth, low-latency path for individual drone command and control. The mesh provides resilience, mutual awareness, and autonomous coordination.

---

## B. Hardware

| Component | Specification | Notes |
|-----------|--------------|-------|
| MCU | ESP32-S3 | WiFi/BLE not used; chosen for processing power and low cost |
| Transceiver | SX1276 LoRa | Long range, low power, spread spectrum |
| Frequency | 433 MHz | Separate band from SiK 915MHz to avoid interference |
| Module cost | ~$8-12 per drone | ESP32-S3 + SX1276 breakout or integrated module (e.g., Heltec WiFi LoRa 32) |
| Connection | UART to flight controller, or USB/SPI to Raspberry Pi companion computer |
| Antenna | Separate from SiK antenna | Quarter-wave whip or helical for 433MHz |
| Power | 3.3V from FC regulator | ~120mA transmit, ~15mA receive |

### Weight and Power Impact

- Module weight: ~8-12g (including antenna)
- Average power draw: ~25mA (mostly listening, periodic transmit)
- Negligible impact on flight time for 5" or larger quads

---

## C. Network Topology

```
              ┌──────────────────┐
              │  Ground Station  │
              │  (ESP32 via USB) │
              └──┬───────────────┘
                 │ LoRa 433MHz
                 │
     ┌───────────┼───────────────┐
     │           │               │
  ┌──┴──┐   ┌───┴──┐        ┌───┴──┐
  │Alpha│───│Bravo │────────│Charlie│
  │(hub)│   └──┬───┘        └───┬──┘
  └─────┘      │                │
            ┌──┴──┐          ┌──┴──┐
            │Delta│──────────│Echo │
            └─────┘          └─────┘
```

- **Hybrid star-mesh**: the ground station is the primary hub, but every drone can talk to every other drone directly
- Each drone is both a **node** and a potential **relay**
- Messages can hop up to **3 times** (max TTL = 3) to prevent infinite loops and limit airtime
- TTL is decremented at each hop; messages with TTL = 0 are not forwarded
- The drone with the strongest link to the ground station is designated the **mesh leader** and coordinates swarm state broadcasts

---

## D. Message Protocol

A lightweight binary protocol designed for LoRa's limited bandwidth. No JSON, no text -- every byte counts.

### Frame Format

```
┌─────────────────────────────────────────────────────────┐
│ Header (8 bytes) │ Payload (0-200 bytes) │ CRC (2 bytes)│
└─────────────────────────────────────────────────────────┘

Header:
  Offset  Size    Field                   Type
  0       1       Protocol version        uint8
  1       1       Message type            uint8
  2       2       Source drone ID         uint16 (big-endian)
  4       2       Destination drone ID    uint16 (big-endian, 0xFFFF = broadcast)
  6       1       TTL / hop count         uint8
  7       1       Sequence number         uint8

Payload:
  Variable length, depends on message type. Max 200 bytes (LoRa constraint).

CRC:
  2 bytes CRC-16/CCITT for integrity check over header + payload.
```

### Message Types

#### 1. HEARTBEAT (type = 0x01, payload = 14 bytes)

```
  Offset  Size    Field       Type        Notes
  0       2       drone_id    uint16      Redundant with header, but allows relay identification
  2       4       latitude    int32       Degrees × 1e7 (MAVLink convention)
  6       4       longitude   int32       Degrees × 1e7
  10      2       altitude    int16       Meters relative to home (±32767m)
  12      1       battery     uint8       Percentage (0-100)
  13      1       status      uint8       Bitmask: armed, airborne, GPS fix, failsafe
```

- Broadcast every **2 seconds** by all drones
- All drones maintain a **neighbor position table** based on received heartbeats
- Heartbeats with TTL > 0 are rebroadcast (flooding), so every drone builds awareness of the entire swarm

#### 2. POSITION_SHARE (type = 0x02, payload = 20 bytes)

```
  Offset  Size    Field       Type        Notes
  0       2       drone_id    uint16
  2       4       latitude    int32       Degrees × 1e7
  6       4       longitude   int32       Degrees × 1e7
  10      2       altitude    int16       Meters relative to home
  12      2       heading     uint16      Degrees × 100 (0-35999)
  14      2       speed       uint16      cm/s ground speed
  16      2       vx          int16       cm/s velocity north
  18      2       vy          int16       cm/s velocity east
```

- Sent on **significant position change** (>2m displacement or >5 degree heading change)
- Enables inter-drone **collision avoidance** without ground station involvement
- Higher resolution than heartbeat for dynamic maneuvers

#### 3. COMMAND_RELAY (type = 0x03, payload = variable, max 200 bytes)

```
  Offset  Size    Field           Type        Notes
  0       2       original_src    uint16      Original command source (e.g., GCS = 0xFFFE)
  2       2       target_drone    uint16      Final destination drone
  4       1       command_type    uint8       Enum: arm, disarm, RTL, goto, mode_change, etc.
  5       N       command_data    bytes       Command-specific payload
```

- Relays ground station commands through the mesh to drones out of direct SiK range
- Source is the ground station (via a relay drone), destination is the target drone
- Directed routing (not broadcast) -- uses the routing table

#### 4. SWARM_STATE (type = 0x04, payload = variable, max 200 bytes)

```
  Offset  Size    Field           Type        Notes
  0       1       formation_type  uint8       Enum: line, V, circle, grid, orbit
  1       1       mission_phase   uint8       Enum: staging, transit, on_station, RTL
  2       1       drone_count     uint8       Number of active drones in swarm
  3       N×4     role_table      bytes       Per-drone: [drone_id(2), role(1), slot(1)]
```

- Broadcast by the **mesh leader** (the drone closest to ground station with strongest link)
- Allows drones to maintain formation and mission awareness even without ground station link
- Updated when formation changes, mission phase transitions, or role reassignment occurs

#### 5. ALERT (type = 0x05, payload = 12 bytes)

```
  Offset  Size    Field           Type        Notes
  0       2       drone_id        uint16      Alerting drone
  2       1       alert_type      uint8       Enum: lost_drone, collision, low_battery, iff_alert, geofence
  3       1       severity        uint8       1=info, 2=warning, 3=critical
  4       4       latitude        int32       Location of alert (degrees × 1e7)
  8       4       longitude       int32
```

- **Highest priority** -- preempts other messages in the transmit queue
- Broadcast to all drones (destination = 0xFFFF, TTL = 3)
- Used for emergency coordination: drone lost, collision imminent, low battery, IFF alert

#### 6. IFF_BEACON (type = 0x06, payload = 32 bytes)

```
  Offset  Size    Field           Type        Notes
  0       4       fleet_id        uint32      Identifies the fleet/operator
  4       2       drone_id        uint16      Individual drone
  6       4       timestamp       uint32      Unix epoch seconds (for replay protection)
  10      2       capabilities    uint16      Bitmask of drone capabilities
  12      20      hmac_sig        bytes       HMAC-SHA1 signature over fields 0-11 using IFF key
```

- Broadcast by all friendly drones every **5 seconds**
- Contains a cryptographic signature that proves fleet membership
- Receiving drones verify the HMAC against their shared IFF key
- Unknown or failed-verification beacons trigger an IFF_ALERT
- Separate encryption key from the fleet signing key (defense in depth)

---

## E. Routing Algorithm

### Broadcast Messages (Heartbeat, Alert, IFF Beacon)

- **Flooding with TTL**: message is rebroadcast by every node that receives it
- Duplicate suppression: track (source_id, seq) pairs; drop messages already seen
- TTL decremented at each hop; dropped when TTL = 0

### Directed Messages (Command Relay, targeted Swarm State)

- **Geographic routing** based on the neighbor position table:
  1. Each drone knows which neighbors it can hear directly (from heartbeats)
  2. Each drone knows the approximate GPS position of all drones (from heartbeats)
  3. To reach drone X: find the direct neighbor whose GPS position is closest to X, forward to them
  4. If no neighbor is closer to X than self, drop the message (routing hole -- should not happen with <50 drones in reasonable proximity)

- **Routing table**: `dict[dest_drone_id, next_hop_drone_id]`
  - Rebuilt every 10 seconds from the heartbeat-derived neighbor table
  - Simple and sufficient for swarms of <50 drones

### Why Not a Complex Routing Protocol?

For <50 drones in a swarm with known GPS positions, geographic routing is optimal:
- No route discovery phase (positions already known from heartbeats)
- No routing protocol overhead (AODV, OLSR would waste bandwidth)
- Convergence is immediate (updated every heartbeat cycle)
- Failure recovery is automatic (lost neighbor disappears from table in 6 seconds)

---

## F. Bandwidth Budget

LoRa parameters: **SF7, BW125kHz** -- effective throughput ~5.5 kbps.

| Traffic Type | Msg Size (bytes) | Drones | Rate (Hz) | Bytes/sec |
|-------------|----------------:|-------:|----------:|----------:|
| Heartbeat | 24 (8 hdr + 14 pay + 2 CRC) | 8 | 0.5 | 96 |
| Position Share | 30 (8 + 20 + 2) | 8 | 0.5 | 120 |
| IFF Beacon | 42 (8 + 32 + 2) | 8 | 0.2 | 67 |
| Protocol overhead | ~50 | -- | -- | 50 |
| **Subtotal** | | | | **333** |

Remaining capacity: ~5,500 - 333 = **~5,167 bytes/sec** (~4.0 kbps) available for:
- Command relays
- Alert messages
- Swarm state broadcasts

**Conclusion**: LoRa at SF7/BW125 is sufficient for telemetry mesh with 8 drones. NOT sufficient for video or high-rate sensor data. Scaling beyond ~20 drones may require reducing heartbeat rate or using higher LoRa bandwidth settings.

---

## G. Mesh + Ground Station Integration

```
┌───────────────┐     USB/Serial     ┌────────────┐
│ Ground Station│◄───────────────────►│ ESP32 Node │
│ (Orchestrator)│                     │ (LoRa 433) │
└───────┬───────┘                     └────────────┘
        │                                    │
        │ SiK 915MHz (MAVLink)        LoRa 433MHz (Mesh)
        │                                    │
        ▼                                    ▼
   ┌─────────┐                         ┌─────────┐
   │ Drone A │◄────── LoRa Mesh ──────►│ Drone B │
   └─────────┘                         └─────────┘
```

### Integration Rules

1. The ground station's orchestrator receives mesh data via one ESP32 node connected over USB serial
2. Mesh telemetry **supplements** (does not replace) the SiK radio telemetry
3. If SiK link to a drone drops but mesh heartbeats are still arriving, the drone is marked **DEGRADED** (not LOST) -- it is alive but out of direct radio range
4. Commands can be multi-hop routed: `Ground Station -> SiK -> Relay Drone -> LoRa Mesh -> Target Drone`
5. The orchestrator merges telemetry from both sources, preferring SiK (lower latency) when available

### Code Integration

The mesh node runs as an async task alongside the main orchestrator loop in `src/swarm.py`. The `MeshNode` class (in `src/mesh_protocol.py`) provides:

- `broadcast_heartbeat()` -- called every 2 seconds with current telemetry
- `get_neighbor_positions()` -- returns the neighbor table for collision avoidance
- `send_command()` -- routes a command through the mesh to a target drone
- `handle_received()` -- processes incoming mesh packets

---

## H. Failure Modes

| Failure | Detection | Response |
|---------|-----------|----------|
| Mesh leader lost | No heartbeat from leader for 6s | Next-closest drone to ground station assumes leader role |
| All mesh links lost to a drone | No heartbeat from drone for 6s on any neighbor | Drone falls back to autonomous behavior (RTL or continue mission per failsafe config) |
| Ground station lost, mesh alive | No GCS heartbeat on mesh for 10s | Drones enter **autonomous swarm mode**: continue mission, maintain formation via mesh, RTL when mission complete or battery low |
| LoRa interference | High CRC error rate, packet loss >50% | Fall back to SiK-only communication; mesh features degraded |
| Mesh partition (swarm splits into 2 groups) | Heartbeat loss between groups | Each partition operates independently with local leader; rejoins when connectivity restored |

---

## I. Security

### Message Signing

- All mesh messages are signed with a shared **fleet key** using HMAC-SHA256 (truncated to 4 bytes appended after CRC)
- Prevents message injection by unauthorized transmitters
- Fleet key is provisioned during firmware flashing (see [[HARDWARE_SPEC]])

### IFF Encryption

- IFF beacons use a **separate IFF key** for HMAC signature
- Defense in depth: compromise of the fleet key does not compromise IFF
- IFF key rotation is managed by the ground station and distributed via encrypted mesh command

### Position Data

- Position data in heartbeats and position shares is **not encrypted** (bandwidth constraint)
- Accepted risk: an adversary with LoRa receive capability can intercept drone positions
- Mitigation: LoRa spread spectrum modulation makes interception harder than conventional radio; an attacker needs to know the exact frequency, spreading factor, and bandwidth
- Future (Phase 5): if bandwidth allows, AES-128 encryption of full mesh traffic

### Replay Protection

- Sequence numbers in headers prevent replay of old messages
- IFF beacons include timestamps; beacons older than 30 seconds are rejected
- Duplicate detection via (source_id, seq) pair tracking

---

## J. Implementation Phases

| Phase | Milestone | Dependencies |
|-------|-----------|--------------|
| 3.1 | ESP32 firmware: encode/decode mesh messages, serial bridge to FC | ESP32-S3 + SX1276 hardware |
| 3.2 | Python `MeshNode` class integrated with orchestrator | Phase 3.1 |
| 3.3 | Heartbeat + neighbor table working on 2 drones | Phase 3.2, 2 flight-ready drones |
| 3.4 | Geographic routing + command relay tested | Phase 3.3 |
| 3.5 | Mesh leader election + autonomous swarm mode | Phase 3.4 |
| 3.6 | IFF beacon system with HMAC verification | Phase 3.5, IFF key management |

---

## Related Documents

- [[COMMS_PROTOCOL]] -- Primary SiK radio communication protocol (mesh supplements this)
- [[SYSTEM_ARCHITECTURE]] -- Overall system architecture showing where mesh fits
- [[HARDWARE_SPEC]] -- BOM including ESP32 + LoRa module
- [[GAP_ANALYSIS]] -- Identified mesh networking as a Phase 3 gap (C3, M2)
- [[PRODUCT_SPEC]] -- Mesh networking in Phase 3 feature list
- [[GLOSSARY]] -- LoRa, ESP32, IFF, TTL, and mesh terminology
- [[DECISION_LOG]] -- Geographic routing decision rationale
