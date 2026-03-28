---
title: Hardware Standardization Spec
type: protocol
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, hardware, bom]
---

# Hardware Standardization Spec

## Minimum Viable Drone (MVD)

Any drone that meets this spec can join the swarm. No exceptions, no "preferred" models.

### Required Components

| Component | Minimum Spec | Recommended (Cheap) | Why |
|-----------|-------------|---------------------|-----|
| Flight Controller | 32-bit, ArduPilot-capable, 1x UART free | SpeedyBee F405 V4 (~$35) | Runs ArduPilot, has enough UARTs for GPS + telemetry |
| GPS | u-blox M8N or newer, with compass | BN-880 (~$12) | ArduPilot needs GPS + compass for GUIDED mode |
| Telemetry Radio | SiK-compatible, 915MHz or 433MHz | Generic SiK radio pair (~$15) | MAVLink-native, no driver needed |
| Frame | Any — quad/hex/octo, any size | F450 clone (~$15) | Just needs to fly stable |
| Motors + ESCs | 4x matched to frame size | 4x 2212 920KV + 4x 30A ESC (~$50-60 total) | Generic, commodity. Price is for all 4 motors + 4 ESCs. |
| Battery | 3S or 4S LiPo, XT60 connector | 4S 3000mAh (~$22) | 12-15 min usable flight time |
| Propellers | Matched to motors | 1045 props (~$5/5pairs) | Consumable, buy extras |
| Power Distribution Board | Matches frame | PDB for F450 (~$8) | Distributes battery power to ESCs and FC |
| XT60 connectors + wires + solder | Standard | XT60 pair + 14AWG wire + solder (~$8) | Wiring and connections |
| Mounting hardware | Spacers, standoffs, zip ties | Nylon spacer kit + zip ties (~$5) | Physical assembly |
| Vibration damping | Foam pads or gel mounts | 3M foam pads (~$3) | Isolates FC from frame vibration (see Vibration Damping section) |
| Remote ID | FAA-compliant broadcast | ArduPilot built-in Remote ID (if FC supports DroneCAN) or standalone module (~$35, e.g., DroneTag Mini) | Required for all US flights since March 2024 (see Remote ID Compliance section) |

### Optional (Enhances Capability)

| Component | Purpose | Cost | Class |
|-----------|---------|------|-------|
| FPV camera (e.g., Caddx Ant) | Visual recon (analog feed) | ~$10 | B+ |
| Video transmitter (VTX, 25-200mW) | Transmit analog FPV to ground | ~$15 | B+ |
| Raspberry Pi Zero 2W | On-board compute (CV, mesh) | ~$15 | C |
| ESP32 + LoRa SX1276 | Drone-to-drone mesh comms | ~$8 | Any |
| Rangefinder (TFMini) | Precise altitude hold | ~$15 | Any |
| Servo + release mechanism | Payload drop | ~$5 | D |
| Fiber optic spool (5km) + SFP transmitter | Jam-proof tethered comms for strike | ~$40-60 | D (optional addon) |

### Hardware Capability Classes

The orchestrator adapts missions based on what each drone can do.

```
CLASS A — Basic (meets minimum spec only)
  Connection: Radio (SiK) — default
  Capabilities: GPS waypoint flight, telemetry
  Roles: Decoy, relay, basic recon
  Cost: ~$195-220

CLASS B — Sensor (Class A + FPV camera + VTX)
  Connection: Radio (SiK) + analog FPV video
  Capabilities: + FPV video feed
  Roles: Recon, surveillance, target marking
  Cost: ~$230-255 (adds FPV camera ~$10, VTX ~$15)

CLASS C — Compute (Class B + Raspberry Pi)
  Connection: Radio (SiK) + WiFi Mesh (ESP32) for IP video
  Capabilities: + on-board CV, mesh networking, IP video stream
  Roles: IFF-capable recon, autonomous tracking
  Cost: ~$260-285 (adds RPi Zero 2W ~$15, camera module ~$10)

CLASS D — Payload (Class A + servo mechanism)
  Connection: Radio (SiK) or Fiber Optic (for strike in EW environments)
  Capabilities: + payload release
  Roles: Delivery, strike
  Cost: ~$200-225 (base); ~$260-290 with fiber optic addon
```

The orchestrator queries each drone's class at registration and only
assigns missions that match its capabilities.

### Connection Types

Each drone communicates with the ground station via one or more connection types. The connection type affects range, bandwidth, cost, and vulnerability to electronic warfare (EW).

| Type | Hardware | Cost | Range | Bandwidth | Jammable | Notes |
|------|----------|------|-------|-----------|----------|-------|
| Radio (SiK 915MHz) | SiK radio pair | ~$15/pair | ~1km | Low (MAVLink telemetry) | Yes | Default for all classes. Adequate for telemetry + commands. |
| Fiber Optic | Fiber spool + SFP transmitter | ~$40-60/spool + transmitter | 5-10km | High | No (jam-proof) | Physical tether constrains path planning. Used for strike drones in EW-contested environments. |
| WiFi Mesh (ESP32) | ESP32 module | ~$8/module | ~500m | High (video-capable) | Yes | Enables drone-to-drone mesh and IP video streaming. |
| LoRa Mesh (SX1276) | SX1276 LoRa module | ~$8/module | ~5km+ | Very low (telemetry only) | Partially | Long range, low power. Cannot carry video. Good for decoy/relay drones at extended range. |
| 4G/LTE | LTE modem + SIM | ~$25/modem + SIM plan | Unlimited (with cell coverage) | High | Yes (cell jammers) | Useful for urban operations with cell infrastructure. Adds latency. |

**Class-to-Connection Defaults:**
- Class A: Radio (SiK) -- default, no additional hardware needed
- Class B: Radio + analog FPV video (add VTX ~$15 and FPV camera ~$10 to BOM)
- Class C: Radio + WiFi Mesh (ESP32) for IP video stream (RPi camera)
- Class D: Radio or Fiber Optic (strike drones often use fiber in EW environments)

## Physical Assembly Checklist

### Antenna Placement
- GPS module: mounted on a mast 3-5cm above the frame, away from ESCs/power wires
- SiK radio antenna: vertical, zip-tied to a landing leg, pointing DOWN (ground station is below)
- If using FPV: VTX antenna opposite side from GPS to reduce interference

### Wiring
```
Battery ──→ PDB (frame) ──→ 4x ESC ──→ 4x Motor
                │
                ├──→ FC (5V BEC pad)
                ├──→ GPS (FC UART port - usually SERIAL3)
                └──→ SiK Radio (FC TELEM1 port - usually SERIAL1)
```

### Vibration Damping

Vibration is a significant problem on budget builds with clone frames and cheap motors. Bad vibration causes EKF failures, barometer noise, and compass interference. ArduPilot will refuse to arm or produce erratic flight if vibration levels are too high.

- **Flight controller:** Mount on 3M double-sided foam tape or gel pads (e.g., Moon Gel, Kyosho Zeal). Do NOT hard-mount the FC to the frame.
- **GPS module:** Mount on a mast 3-5cm above the frame with foam isolation at the base. This separates the GPS/compass from motor vibration and electromagnetic interference.
- **Propellers:** Balance all propellers before first flight. Use a prop balancer (~$10) or the tape method (add small pieces of tape to the lighter blade until balanced). Unbalanced props are the #1 source of vibration.
- **Verification:** After first flight, check ArduPilot VIBE logs. X/Y/Z vibration levels should be below 30 m/s/s. If above 60, do not fly until resolved.

### Remote ID Compliance

US flights require Remote ID broadcast since March 2024. Flying without Remote ID is a federal violation and would be catastrophic for credibility with defense customers.

- **Option A: ArduPilot built-in Remote ID broadcast.** If the flight controller supports DroneCAN, ArduPilot can broadcast Remote ID natively via a DroneCAN-compatible transponder. No additional hardware cost beyond the DroneCAN node.
- **Option B: Standalone Remote ID module (~$35, e.g., DroneTag Mini).** Plug-and-play module that broadcasts independently. Works with any FC. Recommended if FC does not support DroneCAN.
- **Preflight requirement:** Remote ID broadcast must be verified as active during preflight checks. The preflight system must confirm Remote ID is transmitting before allowing arm.

### Shared Equipment (One-Time Costs)

These items are shared across the fleet and only need to be purchased once:

| Item | Cost | Notes |
|------|------|-------|
| LiPo balance charger | ~$40 | e.g., ToolkitRC M6 or ISDT Q6. Multi-port charger ($100+) recommended for 5+ drones. |
| RC transmitter | ~$60 | e.g., RadioMaster Zorro. Needed for manual override and initial tuning. |
| USB hub (powered, 7-10 port) | ~$15 | For connecting multiple SiK radios to the ground station. |
| Soldering iron + supplies | ~$25 | For wiring, connector installation, and repairs. |
| Prop balancer | ~$10 | Essential for reducing vibration on budget builds. |
| **Total shared equipment** | **~$150** | |

### Total System Cost: 3-Drone Fleet

| Item | Cost |
|------|------|
| 3x Class A drones | ~$585-660 |
| Shared equipment (one-time) | ~$150 |
| **Total** | **~$735-810** |

A realistic 3-drone fleet costs **under $1000** including shared equipment. Budget ~$750-900 depending on component sourcing.

### Weight Budget (F450 class)
- Frame + motors + ESCs + props: ~450g
- FC + GPS + radio: ~80g
- Battery 4S 3000mAh: ~250g
- Total: ~780g
- Max safe AUW: ~1200g (leaves ~420g for payload/extras)

---

## Related Documents

- [[COMMS_PROTOCOL]] -- Communication hardware and radio configuration
- [[PRODUCT_SPEC]] -- Feature requirements driving hardware selection
- [[ROADMAP]] -- Hardware procurement timeline and budget
- [[PRESSURE_TEST]] -- Review of hardware cost and battery specs
- [[INTEGRATION_AUDIT]] -- BOM completeness audit
- [[GLOSSARY]] -- Hardware terminology definitions
- [[DECISION_LOG]] -- 4S battery and hardware decisions
