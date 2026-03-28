---
title: Security Architecture Design
type: design
status: in-progress
created: 2026-03-26
updated: 2026-03-26
phase: "1-6"
tags: [drone-swarm, security, iff, encryption, mavlink, gps-spoofing, anti-jamming]
closes-gaps: [C1, C2, C3, C4, C6, C8, L6, L10, L11]
---

# Drone Swarm Orchestrator -- Security Architecture Design

**Version:** 1.0
**Last Updated:** 2026-03-26
**Status:** Comprehensive Design -- Phased Implementation

## Related Documents

- [[SYSTEM_ARCHITECTURE]] -- Backend module breakdown and data flow
- [[GAP_ANALYSIS]] -- Security gaps C1-C4, C6, C8 that this document addresses
- [[API_DESIGN]] -- JWT auth spec, rate limiting spec (implemented here)
- [[ROADMAP]] -- Phase timeline for security feature rollout
- [[PRODUCT_SPEC]] -- IFF and encryption mentioned in Phase 5 defense features
- [[COMMS_PROTOCOL]] -- SiK radio configuration and MAVLink v2 message types
- [[HARDWARE_SPEC]] -- FC boards, radio hardware, secure element options

---

## Table of Contents

1. [Overview and Threat Model](#1-overview-and-threat-model)
2. [A -- MAVLink v2 Signing (Phase 1)](#2-a--mavlink-v2-signing-phase-1)
3. [B -- Ground Station Security (Phase 1)](#3-b--ground-station-security-phase-1)
4. [C -- GPS Spoofing and Jamming Detection (Phase 3)](#4-c--gps-spoofingjamming-detection-phase-3)
5. [D -- Encrypted Communications (Phase 3-4)](#5-d--encrypted-communications-phase-3-4)
6. [E -- Anti-Jamming (Phase 4)](#6-e--anti-jamming-phase-4)
7. [F -- Data Wipe on Capture (Phase 4)](#7-f--data-wipe-on-capture-phase-4)
8. [G -- IFF System (Phase 3-5)](#8-g--iff-system-phase-3-5)
9. [H -- Airspace Compliance (Phase 1)](#9-h--airspace-compliance-phase-1)
10. [Implementation Priority Matrix](#10-implementation-priority-matrix)

---

## 1. Overview and Threat Model

### Design Philosophy

Security is not a bolt-on feature. Every phase of the drone swarm platform must include the security measures appropriate to that phase's deployment context. The principle is **defense in depth**: no single security layer is trusted alone, and compromise of one layer does not compromise the system.

### Threat Actors

| Threat Actor | Capability | Motivation | Relevant Phases |
|---|---|---|---|
| Hobbyist/curious | SDR receiver, basic radio knowledge | Curiosity, mischief | Phase 1+ |
| Competitor operator | Same equipment as us, knowledge of SiK/MAVLink | Interference, sabotage | Phase 1+ |
| Criminal | Jamming equipment, GPS spoofer ($200) | Theft of drones, disruption | Phase 2+ |
| State-level adversary | Full-spectrum EW, cyber, SIGINT | Military advantage | Phase 4+ |
| Insider threat | Legitimate access to ground station | Sabotage, espionage | Phase 1+ |

### Attack Surface

```
                     ATTACK SURFACE MAP
  ┌──────────────────────────────────────────────────┐
  │                   GROUND STATION                  │
  │  [REST API] [WebSocket] [USB] [Radio Link]       │
  │  Auth ──► B       B       -      A,D             │
  └───────┬──────────┬───────┬───────┬───────────────┘
          │ TLS (B)  │       │       │ MAVLink Signing (A)
          ▼          ▼       │       │ AES-256 (D)
     [Browser]  [ATAK/CoT]  │       │
                             │       ▼
                     ┌───────┴───────────────────────┐
                     │          RADIO LINK            │
                     │  SiK 915MHz / ESP32 Mesh      │
                     │  Jamming target (E)            │
                     │  Interception target (D)       │
                     └───────┬───────────────────────┘
                             │
                     ┌───────▼───────────────────────┐
                     │           DRONE                │
                     │  [FC] [GPS] [Sensors] [Keys]  │
                     │  Spoofing target (C)           │
                     │  Capture target (F)            │
                     │  IFF beacon (G)                │
                     └───────────────────────────────┘
```

Letters in parentheses reference the subsystem that defends against each attack vector.

---

## 2. A -- MAVLink v2 Signing (Phase 1)

**Gap addressed:** C3 (Encrypted Communications -- first step)
**Effort:** Trivial -- ArduPilot already supports this natively
**Impact:** Prevents unauthorized command injection via radio

### 2.1 How MAVLink v2 Signing Works

MAVLink v2 includes a message signing feature that appends a cryptographic signature to every message. This does not encrypt the payload (telemetry is still readable) but it prevents an attacker from injecting forged commands.

```
MAVLink v2 Signed Message Structure:
┌──────────────┬──────────────┬──────────────────────────┐
│  MAVLink v2  │   Payload    │     Signature Block      │
│   Header     │  (cleartext) │                          │
│  (10 bytes)  │  (0-255 B)   │  link_id (1B)            │
│              │              │  timestamp (6B)           │
│              │              │  signature (6B)           │
└──────────────┴──────────────┴──────────────────────────┘

Signature = SHA-256(secret_key + header + payload + CRC + link_id + timestamp)
           → truncated to first 6 bytes
```

**Properties:**
- The secret key is a 32-byte shared secret, known to both the ground station and the FC.
- The timestamp is a monotonically increasing 6-byte value (units of 10 microseconds since 1 Jan 2015). This prevents replay attacks.
- The link_id identifies the communication channel (allows different keys per link).
- Any message that fails signature verification is silently dropped by the receiver.

### 2.2 Key Generation Per Fleet

Each fleet gets a unique 32-byte signing key. Keys are generated during the firmware flashing process and never transmitted over radio.

```
Key Generation Procedure:
1. firmware_flasher.py generates: os.urandom(32)
2. Key is saved to: fleet_keys/{fleet_id}.key  (binary file, 32 bytes)
3. Key is also saved in the fleet registration JSON for the ground station
4. Key is loaded into the FC via MAVLink SETUP_SIGNING message after flashing
5. Ground station loads the same key to sign its outgoing messages
```

**Key storage locations:**
- FC: stored in internal EEPROM (persists across reboots)
- Ground station: `fleet_keys/{fleet_id}.key` file (permissions: 0600, owner-only read/write)
- Backup: encrypted USB drive kept by fleet administrator

### 2.3 Key Rotation Procedure

Keys should be rotated:
- Every 90 days (routine rotation)
- Immediately after any drone is lost or captured
- Immediately after any personnel with key access leaves the team

```
Key Rotation Steps:
1. Generate new 32-byte key: os.urandom(32)
2. Connect each drone via USB (cannot rotate over radio -- chicken-and-egg)
3. Send SETUP_SIGNING MAVLink message with new key
4. Update fleet_keys/{fleet_id}.key on ground station
5. Verify signed communication works with each drone
6. Securely delete old key file (overwrite with random data)
7. Log rotation event in audit trail: timestamp, operator, reason
```

**Limitation:** Key rotation requires physical USB access to each drone. For large fleets, this is operationally expensive. Phase 3+ adds encrypted over-the-air key rotation using the AES-256 channel.

### 2.4 Detecting Unsigned/Forged Commands

When signing is enabled on the FC:

| Incoming Message | FC Behavior |
|---|---|
| Unsigned message | Silently dropped. Counter incremented. |
| Signed, wrong key | Silently dropped. Counter incremented. |
| Signed, old timestamp (replay) | Silently dropped. Counter incremented. |
| Signed, correct key + valid timestamp | Accepted and processed. |

**Monitoring:** The ground station should periodically query the FC for the rejected-message counter. A sudden spike indicates an active attack (someone is transmitting forged commands).

**ArduPilot parameters to enable:**
```
# Set via SETUP_SIGNING MAVLink message, not via parameters.
# ArduPilot does not expose signing as a standard parameter.
# The signing key is set programmatically via pymavlink:
#
#   conn.mav.setup_signing_send(
#       conn.target_system,
#       conn.target_component,
#       secret_key,        # 32 bytes
#       initial_timestamp  # uint64
#   )
```

---

## 3. B -- Ground Station Security (Phase 1)

**Gaps addressed:** C4 (Operator Authentication and Audit Trail), L6 (API Rate Limiting)

### 3.1 TLS for All Connections

All WebSocket and REST connections between the browser UI and the backend must use TLS 1.3.

```
Connection Security:
┌──────────┐     TLS 1.3      ┌──────────────┐
│ Browser  │ ◄═══════════════► │  FastAPI      │
│ (UI)     │   wss://          │  Backend      │
│          │   https://        │  (localhost   │
└──────────┘                   │   or LAN)     │
                               └──────────────┘

Certificate Strategy:
- Development: self-signed cert generated on first run
- Field deployment: self-signed cert with CA pinning in the UI
- Enterprise: customer provides their own cert
- Never use plain HTTP/WS in production, even on localhost
```

**Implementation:**
- FastAPI with `uvicorn --ssl-keyfile key.pem --ssl-certfile cert.pem`
- Generate self-signed cert on first run if none exists
- Pin the cert fingerprint in the UI to prevent MITM on LAN

### 3.2 JWT Authentication with Role-Based Access

Three roles, each with specific permissions:

| Role | View Telemetry | Send Commands | Modify Fleet | Manage Users | Emergency Stop |
|---|---|---|---|---|---|
| observer | Yes | No | No | No | No |
| pilot | Yes | Yes | No | No | Yes |
| admin | Yes | Yes | Yes | Yes | Yes |

**JWT Token Structure:**
```json
{
  "sub": "operator_callsign",
  "role": "pilot",
  "fleet_id": "alpha-fleet",
  "iat": 1711411200,
  "exp": 1711418400,
  "jti": "unique-token-id"
}
```

**Token lifecycle:**
- Access token: 2-hour expiry
- Refresh token: 24-hour expiry, stored in httpOnly cookie
- Login: username + password (bcrypt hashed) -> access token + refresh token
- Refresh: POST /auth/refresh with valid refresh token -> new access token
- Logout: POST /auth/logout -> refresh token added to blacklist, access token invalidated
- Blacklist: in-memory set (cleared on restart -- acceptable for single-station deployment)

**Password storage:** bcrypt with cost factor 12. User database stored in `config/users.json` (encrypted at rest in Phase 3).

### 3.3 Session Management

- Each WebSocket connection requires a valid JWT in the initial handshake (sent as query parameter or first message).
- If the token expires during an active WebSocket session, the server sends a `TOKEN_EXPIRED` message and closes the connection. The client must reconnect with a refreshed token.
- Maximum 5 concurrent sessions per user. New login forces oldest session to disconnect.
- Idle timeout: 30 minutes of no commands -> session marked idle (telemetry continues but commands require re-authentication).

### 3.4 Operator Audit Trail

Every command is logged with full context. This is non-negotiable for defense customers and essential for incident investigation.

**Audit log entry format:**
```json
{
  "timestamp": "2026-03-26T14:23:01.234Z",
  "operator": "callsign_bravo",
  "role": "pilot",
  "action": "COMMAND_SEND",
  "command": "arm",
  "target_drone": "drone-03",
  "target_sysid": 3,
  "parameters": {"mode": "GUIDED"},
  "source_ip": "192.168.1.42",
  "session_id": "sess_abc123",
  "result": "ACK",
  "response_time_ms": 120
}
```

**What gets logged:**
- Every REST API call (method, path, parameters, response code)
- Every WebSocket command (type, target drone, parameters, result)
- Every authentication event (login, logout, failed login, token refresh)
- Every emergency action (emergency stop, force kill, RTL all)
- Every fleet modification (drone added, removed, parameters changed)
- Every mission lifecycle event (created, approved, launched, completed, aborted)

**Storage:** JSONL file at `logs/audit/{date}.jsonl`. Rotated daily. Retained for minimum 1 year. In Phase 3+, replicated to encrypted backup.

**Tamper protection (Phase 3):** Each audit log line includes a chained hash (hash of previous line + current line content), making retroactive modification detectable.

### 3.5 Rate Limiting on Command Endpoints

Rate limits prevent both accidental flooding (buggy UI) and intentional abuse.

| Endpoint Category | Rate Limit | Window |
|---|---|---|
| Authentication (login) | 5 requests | per minute per IP |
| Command endpoints (arm, takeoff, goto) | 30 requests | per minute per user |
| Telemetry subscription (WebSocket) | 1 connection | per user per drone |
| Fleet modification | 10 requests | per minute per user |
| Emergency stop | No limit | -- (never rate-limit safety) |

**Implementation:** Use `slowapi` middleware in FastAPI with Redis-backed or in-memory storage.

**Response on rate limit exceeded:** HTTP 429 with `Retry-After` header. Log the event in audit trail.

---

## 4. C -- GPS Spoofing/Jamming Detection (Phase 3)

**Gap addressed:** C2 (GPS Spoofing and Jamming Detection)

### 4.1 Multi-Sensor Consistency Checking

The core detection strategy is cross-referencing GPS with independent sensors that an attacker cannot spoof simultaneously.

```
Sensor Fusion for Spoofing Detection:
┌─────────┐  ┌─────────┐  ┌───────────┐  ┌──────────────┐
│   GPS   │  │ Compass │  │ Barometer │  │ Accelerometer│
│ lat/lon │  │ heading │  │ altitude  │  │ velocity     │
│ alt,spd │  │         │  │           │  │ (integrated) │
└────┬────┘  └────┬────┘  └─────┬─────┘  └──────┬───────┘
     │            │             │                │
     ▼            ▼             ▼                ▼
   ┌──────────────────────────────────────────────┐
   │         CONSISTENCY CHECKER (EKF)            │
   │                                              │
   │  GPS alt vs Baro alt: should agree ±5m       │
   │  GPS heading vs Compass: should agree ±15°   │
   │  GPS velocity vs Accel integrated: ±2 m/s    │
   │  GPS position delta vs time: ≤ max_speed     │
   └──────────────────────────────────────────────┘
```

### 4.2 Spoofing Detection Rules

| Check | Threshold | Trigger |
|---|---|---|
| Position jump | GPS moves >50m in 1 second | SPOOFING_ALERT |
| Altitude mismatch | GPS alt differs from baro alt by >20m | SPOOFING_ALERT |
| Heading mismatch | GPS track differs from compass heading by >45 degrees (while moving >2 m/s) | SPOOFING_ALERT |
| Velocity mismatch | GPS velocity differs from accelerometer-integrated velocity by >5 m/s | SPOOFING_ALERT |
| Satellite count anomaly | Sat count jumps from <5 to >12 instantly | SPOOFING_ALERT (real GPS does not do this) |
| Multi-drone inconsistency | Two drones 10m apart report GPS positions >100m apart | SPOOFING_ALERT |

### 4.3 Jamming Detection Rules

| Check | Threshold | Trigger |
|---|---|---|
| Satellite dropout | GPS sat count drops to 0 while baro/compass/accel continue working | JAMMING_DETECTED |
| GPS fix loss | No GPS fix for >5 seconds in an area with known good GPS coverage | JAMMING_DETECTED |
| Noise floor elevation | GPS reported noise floor exceeds threshold (if module reports this) | JAMMING_DETECTED |

### 4.4 Response Protocol

```
On SPOOFING_ALERT or JAMMING_DETECTED:
1. IMMEDIATELY: alert operator via ground station + audible alarm
2. IMMEDIATELY: mark GPS data as UNTRUSTED in telemetry stream
3. WITHIN 1 SECOND: switch to GPS-denied navigation mode:
   - Altitude: hold via barometer (reliable, cannot be spoofed over RF)
   - Heading: hold via compass (unless also suspected compromised)
   - Position: dead reckoning from last known good position + accelerometer
   - Speed: hold current speed or decelerate to hover
4. WITHIN 5 SECONDS: operator decides:
   - CONTINUE: accept degraded navigation and continue mission
   - RTL: return to launch using compass heading + barometer altitude
   - LAND: immediate landing at current position
5. DEFAULT (no operator response in 30s): RTL using dead reckoning
```

### 4.5 ArduPilot EKF Parameters to Enable

ArduPilot's Extended Kalman Filter (EKF) already performs some of this fusion. Enable and tune these parameters:

```
# EKF3 (preferred over EKF2 for GPS resilience)
EK3_ENABLE = 1           # Enable EKF3
AHRS_EKF_TYPE = 3        # Use EKF3

# GPS consistency checking
EK3_CHECK = 245          # Enable all consistency checks (bitmask)
                         # Bit 0: GPS max horiz pos error
                         # Bit 2: GPS max horiz speed error
                         # Bit 4: GPS max vert pos error
                         # Bit 5: GPS max vert speed error
                         # Bit 6: GPS max horiz pos drift
                         # Bit 7: GPS max vert pos drift

# GPS glitch detection thresholds
EK3_GPS_CHECK = 31       # All GPS checks enabled
EK3_GLITCH_RAD = 25      # 25m radius for glitch detection (default)

# Allow flight without GPS (needed for GPS-denied mode)
EK3_SRC1_POSXY = 3       # Primary: GPS
EK3_SRC2_POSXY = 0       # Fallback: None (dead reckoning)
EK3_SRC1_POSZ = 1        # Primary: barometer
EK3_SRC1_VELXY = 3       # Primary: GPS
EK3_SRC2_VELXY = 0       # Fallback: None
EK3_SRC1_VELZ = 3        # Primary: GPS
EK3_SRC2_VELZ = 0        # Fallback: None
EK3_SRC1_YAW = 1         # Primary: compass

# GPS failsafe
FS_EKF_ACTION = 1        # Land on EKF failsafe (safest default)
FS_EKF_THRESH = 0.8      # EKF variance threshold for failsafe
```

### 4.6 Advanced: Visual Odometry (Phase 5)

On Class C drones with Raspberry Pi companion computers and cameras:

- Run visual odometry (e.g., OpenCV `cv2.calcOpticalFlowPyrLK`) to estimate ground-plane velocity
- Compare visual velocity estimate against GPS velocity
- If they diverge significantly, trust visual odometry over GPS
- ArduPilot supports visual odometry input via VISION_POSITION_ESTIMATE MAVLink message
- Set `EK3_SRC2_POSXY = 6` (ExternalNav) and `EK3_SRC2_VELXY = 6` to use visual odometry as fallback

---

## 5. D -- Encrypted Communications (Phase 3-4)

**Gap addressed:** C3 (Encrypted Communications -- full implementation)

### 5.1 Communication Security by Layer

| Link | Phase 1 | Phase 3 | Phase 4 | Phase 6 |
|---|---|---|---|---|
| GS to FC (SiK radio) | MAVLink v2 signing (auth only) | + AES-256-GCM payload encryption | Same | Same |
| GS to Browser (LAN) | TLS 1.3 | Same | Same | Same |
| Drone-to-Drone (mesh) | None (no mesh yet) | TLS/DTLS over ESP32 WiFi mesh | Same | Same |
| GS to Fiber drones | N/A | N/A | Inherently secure (physical medium) | Same |
| GS to Cloud | N/A | N/A | N/A | mTLS + AES-256 |

### 5.2 AES-256 Encryption of MAVLink Payload (Phase 3)

MAVLink v2 signing prevents command injection but does not prevent eavesdropping. Phase 3 adds encryption.

```
Encrypted MAVLink Message:
┌──────────────┬──────────────────────────────────┬──────────────┐
│  MAVLink v2  │      Encrypted Payload           │  Signature   │
│   Header     │  AES-256-GCM(key, nonce, payload)│  Block       │
│  (cleartext) │  + 12-byte nonce + 16-byte tag   │              │
└──────────────┴──────────────────────────────────┴──────────────┘

Process:
1. Serialize MAVLink payload as normal
2. Encrypt payload with AES-256-GCM using per-drone derived key
3. Replace payload with: nonce (12B) + ciphertext + auth_tag (16B)
4. Set a custom message ID indicating encrypted payload
5. Sign the entire message with MAVLink v2 signing (signs over ciphertext)
6. Receiver: verify signature → decrypt payload → process message
```

**Why AES-256-GCM:** Provides both confidentiality (encryption) and integrity (authentication tag). GCM mode is hardware-accelerated on many microcontrollers. The authentication tag provides an additional integrity check beyond MAVLink signing.

### 5.3 ESP32 Mesh Network Encryption (Phase 3-4)

The ESP-MDF mesh network between drones uses WiFi and supports WPA3 encryption natively. Additional layers:

```
Mesh Encryption Stack:
┌─────────────────────────┐
│  Application: MAVLink   │  ← AES-256-GCM encrypted payload
├─────────────────────────┤
│  Transport: DTLS 1.3    │  ← per-session encryption
├─────────────────────────┤
│  Network: ESP-MDF Mesh  │  ← WPA3 encryption (link layer)
├─────────────────────────┤
│  Physical: WiFi 2.4GHz  │
└─────────────────────────┘
```

Three layers of encryption may seem excessive, but each layer defends against different attacks. WPA3 protects the WiFi link. DTLS protects the transport session. AES-256-GCM on the MAVLink payload protects the application data end-to-end even if the mesh infrastructure is compromised.

### 5.4 Key Management

```
Key Hierarchy:
┌─────────────────────────────────────────────┐
│  Fleet Master Key (FMK)                     │
│  Generated: once per fleet, during setup    │
│  Stored: fleet_keys/{fleet_id}.master       │
│  Purpose: derive all other keys             │
├─────────────────────────────────────────────┤
│  Per-Drone Signing Key (DSK)                │
│  Derived: HKDF(FMK, "signing" + drone_id)  │
│  Stored: FC EEPROM + fleet_keys/            │
│  Purpose: MAVLink v2 signing                │
├─────────────────────────────────────────────┤
│  Per-Drone Encryption Key (DEK)             │
│  Derived: HKDF(FMK, "encrypt" + drone_id)  │
│  Stored: FC EEPROM + fleet_keys/            │
│  Purpose: AES-256-GCM payload encryption    │
├─────────────────────────────────────────────┤
│  IFF Beacon Key (IBK)                       │
│  Derived: HKDF(FMK, "iff" + fleet_id)      │
│  Stored: all drones in fleet + GS           │
│  Purpose: HMAC signatures on IFF beacons    │
├─────────────────────────────────────────────┤
│  Mesh Session Key (MSK)                     │
│  Derived: per-session DTLS handshake        │
│  Stored: volatile memory only               │
│  Purpose: DTLS encryption of mesh traffic   │
└─────────────────────────────────────────────┘
```

**Key derivation:** Uses HKDF (HMAC-based Key Derivation Function, RFC 5869) with SHA-256. This ensures per-drone keys are cryptographically independent -- compromising one drone's key does not reveal other drones' keys or the fleet master key.

**Key distribution:** Keys are ONLY distributed during physical USB setup (firmware flashing). They are NEVER transmitted over radio. This is a fundamental security property.

**Key rotation schedule:**
- Routine rotation: every 90 days
- Emergency rotation: immediately after drone loss/capture
- Per-mission ephemeral keys (Phase 4): generate per-mission session keys derived from FMK + mission_id, valid only for mission duration

### 5.5 Fiber Optic Communications (Phase 4+)

Fiber optic tethers are inherently secure against RF interception and jamming:
- Signal cannot be intercepted without physical access to the fiber
- Immune to RF jamming
- Extremely high bandwidth (for video, telemetry, and commands simultaneously)
- Trade-off: tethered drones have limited range (typically 50-200m of fiber spool)
- Use case: critical overwatch drones that must maintain communications in any EW environment

---

## 6. E -- Anti-Jamming (Phase 4)

**Gap addressed:** L11 (EW Awareness -- subset), GAP_ANALYSIS C2 (mitigation)

### 6.1 Jamming Detection

```
Detection Pipeline:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Monitor RSSI │────►│ Analyze      │────►│ Classify     │
│ per radio    │     │ patterns     │     │ jam type     │
└──────────────┘     └──────────────┘     └──────────────┘

Detection Indicators:
- RSSI drops across ALL frequencies simultaneously → wideband jamming
- RSSI drops on ONE frequency, others fine → narrowband interference
- RSSI drops on command link, telemetry OK → targeted jamming
- Packet loss rate >50% with good RSSI → smart jamming (protocol-aware)
- All drones lose comms simultaneously → ground-station-targeted jamming
```

### 6.2 Response Protocol

```
On JAMMING_DETECTED:
1. Alert operator (if ground link still works)
2. Each drone autonomously determines response based on jamming severity:

   SEVERITY LOW (packet loss 20-50%, some telemetry getting through):
   - Continue mission with increased autonomy
   - Reduce telemetry rate to minimize required bandwidth
   - Switch to store-and-forward: log telemetry, upload when link recovers

   SEVERITY HIGH (packet loss >50%, commands not getting through):
   - Switch to last-known-good mission plan (continue waypoints autonomously)
   - Increase inter-drone mesh communication (if mesh still works)
   - Set timer: if no GS contact in 60 seconds → execute contingency

   SEVERITY CRITICAL (total link loss):
   - Execute pre-programmed contingency:
     Option A: RTL (default for commercial operations)
     Option B: Continue mission to completion, then RTL (military default)
     Option C: Loiter at current position for N minutes, then RTL
   - Contingency option set per-mission during mission planning
```

### 6.3 Mitigation Strategies

| Strategy | Phase | Effectiveness | Notes |
|---|---|---|---|
| SiK FHSS (already built-in) | Phase 1 | Low | Basic frequency hopping; defeats casual interference |
| Adaptive data rate | Phase 3 | Medium | Lower baud rate = better noise resistance |
| Directional antennas | Phase 4 | Medium | Reduces off-axis jamming; requires antenna tracker |
| Spread spectrum (custom radio) | Phase 4 | Medium-High | Requires custom radio firmware |
| Fiber optic for critical drones | Phase 4 | Complete | Cannot be jammed; limited by tether length |
| Mesh redundancy | Phase 4 | High | If one link is jammed, route through other drones |

### 6.4 Pre-Mission Jamming Assessment

Before every mission, the ground station performs a 30-second RF environment scan:
- Record baseline RSSI on all planned frequencies
- Record baseline packet loss rate
- Record baseline GPS satellite count and signal strength
- If any baseline is degraded: warn operator, recommend alternate frequencies or abort

---

## 7. F -- Data Wipe on Capture (Phase 4)

**Gap addressed:** C6 (Automated Data Wipe / Self-Destruct Protocol)

### 7.1 Tamper Detection Triggers

| Trigger | Detection Method | Confidence |
|---|---|---|
| High-G impact | Accelerometer reads >15G (crash or rough handling) | Medium (could be hard landing) |
| Geofence breach + no comms | Drone is outside geofence AND has lost GS contact for >60s | High |
| Orientation anomaly | Drone is upside-down for >30s with motors stopped | High (captured/picked up) |
| Altitude anomaly | Below ground level (barometer vs home altitude) for >30s | Medium (could be sensor error) |
| Manual trigger | Operator sends WIPE command from ground station | Absolute |
| Tamper switch (Phase 5) | Physical switch on enclosure opened | High |

**Two-out-of-three rule:** Automatic wipe requires at least TWO triggers to activate simultaneously. This prevents accidental wipes from sensor glitches. Manual wipe from the operator overrides this rule.

### 7.2 Wipe Procedure

```
On WIPE_TRIGGERED:
1. Wipe MAVLink signing keys from FC EEPROM
   - Overwrite key storage location with random bytes (3 passes)
2. Wipe IFF beacon key from memory
3. Wipe AES-256 encryption keys
4. Wipe fleet_keys/ stored on any companion computer SD card
5. Wipe mission plan from FC
6. Wipe flight logs from SD card (if time permits)
   - If time-critical: delete file allocation table only (fast wipe)
   - If time permits: overwrite with random data (secure wipe)
7. Wipe fleet registry data from companion computer
8. Set FC to factory default parameters
9. Log wipe event to volatile memory (lost on power cycle)

Total wipe time target: <5 seconds for keys, <30 seconds for full data
```

### 7.3 Hardware Security (Phase 5)

**Secure element (ATECC608A or similar, ~$1/chip):**
- Stores signing keys and encryption keys in tamper-resistant silicon
- Keys cannot be read out programmatically -- only used for signing/encryption operations inside the chip
- Tamper detection: voltage glitch detection, temperature attack detection, physical probe detection
- On tamper detection: chip self-destructs keys internally

**Encrypted storage at rest:**
- All sensitive data on SD card encrypted with a key stored in volatile memory (RAM)
- Power loss = key loss = data is unreadable
- This is the ultimate fallback: even without active wipe, simply removing power (pulling the battery) makes the data inaccessible

### 7.4 Key Revocation on Drone Loss

When a drone is confirmed lost or captured:
1. Mark drone as COMPROMISED in fleet registry
2. Rotate the fleet master key (generates new per-drone keys for all remaining drones)
3. Re-flash keys on all remaining drones via USB
4. Rotate IFF beacon key (so captured drone's transponder broadcasts invalid beacons)
5. If per-mission ephemeral keys were in use: those keys expire automatically at mission end

---

## 8. G -- IFF System (Phase 3-5)

**Gap addressed:** C1 (Identification Friend-or-Foe and Target Identification System)

### 8.1 Architecture Overview -- Three-Layer Identification

```
IFF Decision Flow:
                    ┌───────────────────┐
                    │   DETECT ENTITY   │
                    │   (radar, visual,  │
                    │    or telemetry)   │
                    └────────┬──────────┘
                             │
              ┌──────────────▼──────────────┐
              │  LAYER 1: TRANSPONDER CHECK │
              │  Is there a valid beacon    │
              │  from this position?        │
              └──────┬────────────┬─────────┘
                     │            │
                   VALID      NO BEACON
                   BEACON        │
                     │    ┌──────▼──────────────┐
                     │    │ LAYER 2: CV CHECK   │
                     │    │ (if camera avail)    │
                     │    │ Visual recognition   │
                     │    └──────┬──────────┬────┘
                     │           │          │
                     │       RECOGNIZED  UNCERTAIN
                     │       (>90%)         │
                     │           │   ┌──────▼──────────────┐
                     │           │   │ LAYER 3: BLUE FORCE │
                     │           │   │ Check ATAK/CoT feed │
                     │           │   │ Friendly within 50m?│
                     │           │   └──────┬──────────────┘
                     │           │          │
                     ▼           ▼          ▼
              ┌──────────────────────────────────┐
              │        CLASSIFICATION ENGINE      │
              │                                  │
              │  Rule: if ANY layer says FRIENDLY │
              │        → classify FRIENDLY        │
              │        (err on side of caution)   │
              │                                  │
              │  Output: FRIENDLY | HOSTILE |     │
              │          UNKNOWN  | CIVILIAN      │
              │  + confidence score (0.0 - 1.0)  │
              │  + contributing layers list       │
              └──────────────────────────────────┘
```

**Safety principle:** The IFF system is designed to PREVENT engagement of friendlies, not to AUTHORIZE engagement of hostiles. If any layer reports FRIENDLY, the classification is FRIENDLY regardless of other layers. This minimizes fratricide at the cost of potentially missing hostile targets -- the correct trade-off.

### 8.2 Layer 1 -- Transponder Beacon (Phase 3)

**Hardware:** ESP32 module (already planned for mesh networking) or dedicated 868 MHz ISM band RF module (~$10).

**Beacon format (32 bytes total):**
```
┌──────────┬──────────┬───────────┬─────────────────────┐
│ fleet_id │ drone_id │ timestamp │    HMAC-SHA256       │
│ (8 bytes)│ (4 bytes)│ (4 bytes) │ (first 16 bytes)     │
└──────────┴──────────┴───────────┴─────────────────────┘

fleet_id:   8-byte identifier for the fleet (from fleet registration)
drone_id:   4-byte identifier for the specific drone (sysid)
timestamp:  4-byte Unix timestamp (seconds, wraps every ~136 years)
HMAC:       HMAC-SHA256(IFF_beacon_key, fleet_id + drone_id + timestamp)
            truncated to 16 bytes
```

**Broadcast parameters:**
- Rate: 5 Hz (200ms interval)
- Power: 100 mW (ISM band legal limit)
- Range: matches operational radio range (~1 km with SiK, ~300m with ESP32)
- Frequency: 868 MHz ISM (EU) or 915 MHz ISM (US) -- same band as SiK radios

**Beacon validation:**
1. Receive beacon
2. Check timestamp: must be within 30 seconds of current time (prevents replay)
3. Compute HMAC with fleet's IFF beacon key
4. Compare computed HMAC with received HMAC
5. If match: entity at this position is FRIENDLY (fleet_id confirms same fleet)
6. If no match or no beacon: entity is UNKNOWN

**Key property:** The beacon key is per-fleet. Only drones in your swarm can produce valid beacons. An adversary who captures one drone gets that fleet's beacon key -- which is why key rotation on capture is critical (Section 7.4).

### 8.3 Layer 2 -- Computer Vision (Phase 5)

**Hardware:** Raspberry Pi 4/5 + camera module on Class C drones.

**ML pipeline:**
```
Camera Frame (30 fps)
       │
       ▼
  ┌──────────────┐
  │ Preprocessing │  Resize to 640x640, normalize
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │   YOLOv8n    │  Nano model, runs at ~15fps on RPi4 with TFLite
  │  (quantized) │  Detects: drone, vehicle, person, aircraft
  └──────┬───────┘
         ▼
  ┌──────────────────┐
  │ Classification    │
  │                  │
  │ Friendly drone:  │  Has IR LED pattern? → FRIENDLY
  │ Enemy drone:     │  No IR LED, matches enemy profile → HOSTILE
  │ Vehicle:         │  Check against blue force positions → FRIENDLY/UNKNOWN
  │ Person:          │  Check against blue force positions → FRIENDLY/CIVILIAN
  │ Aircraft:        │  Any manned aircraft → CIVILIAN (always avoid)
  └──────┬───────────┘
         ▼
  Confidence score + bounding box + classification
```

**Visual markers for friendly identification:**
- IR LED pattern on each friendly drone: a specific blink pattern (e.g., 3 short + 1 long) at 940nm
- Invisible to naked eye, visible to cameras (especially NoIR camera module)
- Pattern is fleet-specific (configured during setup)
- Cheap: 3x IR LEDs + resistor + small timer circuit, ~$2 per drone

**Confidence thresholds:**
- >90%: auto-classify, log decision
- 70-90%: classify with LOW_CONFIDENCE flag, alert operator
- <70%: classify UNKNOWN, alert operator for manual classification

**Training data:**
- Synthetic: 3D renders of drone models against various backgrounds (sky, trees, buildings)
- Real: flight footage from test flights, annotated with ground truth
- Augmentation: rotation, scale, blur, lighting variation, weather effects
- Target: 500+ real images per class, 5000+ synthetic images per class

### 8.4 Layer 3 -- Blue Force Tracking / ATAK Integration (Phase 5)

**Protocol:** Cursor on Target (CoT), the standard military situational awareness protocol.

**CoT message format (simplified):**
```xml
<event version="2.0" uid="drone-03" type="a-f-A-M-H-Q"
       time="2026-03-26T14:30:00Z" start="2026-03-26T14:30:00Z"
       stale="2026-03-26T14:31:00Z" how="m-g">
  <point lat="34.0522" lon="-118.2437" hae="100" ce="5" le="5"/>
  <detail>
    <contact callsign="SWARM-ALPHA-03"/>
    <__group name="Cyan" role="Team Member"/>
    <track course="270" speed="5"/>
  </detail>
</event>
```

**Integration architecture:**
```
┌──────────────┐    CoT/UDP     ┌──────────────┐
│  ATAK Server │ ◄═════════════► │  Orchestrator│
│  (TAK Server)│   multicast    │  CoT Bridge  │
│              │   239.2.3.1    │              │
└──────────────┘   :6969        └──────────────┘

Outgoing (orchestrator → ATAK):
- Publish each drone's position as a CoT event
- Update rate: 1 Hz
- Type code: a-f-A-M-H-Q (friendly, air, military, helicopter/rotary, UAS)

Incoming (ATAK → orchestrator):
- Receive all friendly ground force positions
- Receive manually-marked targets and areas of interest
- Receive restricted areas (no-fly zones placed by ground forces)
```

**Blue force proximity check:**
```
Before any engagement or close approach to a target:
1. Get target position (lat, lon)
2. Query blue force position database
3. For each known friendly position:
   distance = haversine(target, friendly)
   if distance < 50m:
     → ABORT engagement
     → Alert operator: "FRIENDLY WITHIN 50m OF TARGET"
     → Log: target position, nearest friendly callsign, distance
4. If no friendlies within 50m:
   → Proceed (subject to other IFF layers)
```

### 8.5 Integration -- The TargetClassifier Interface

```python
class TargetClassifier:
    """
    Unified IFF classification interface.
    Combines all three layers into a single classification decision.
    """

    async def classify(self, position: tuple, image_data: bytes = None) -> Classification:
        """
        Classify an entity at the given position.

        Args:
            position: (latitude, longitude, altitude_m)
            image_data: optional camera frame (JPEG bytes) for CV classification

        Returns:
            Classification with:
              - classification: FRIENDLY | HOSTILE | UNKNOWN | CIVILIAN
              - confidence: 0.0 to 1.0
              - layers: list of which layers contributed and their individual results
              - reasoning: human-readable explanation
        """
        results = []

        # Layer 1: Check transponder beacons
        beacon_result = await self.check_transponder(position)
        results.append(("transponder", beacon_result))

        # Layer 2: Run CV if image available and hardware supports it
        if image_data is not None and self.cv_available:
            cv_result = await self.run_cv_classification(image_data)
            results.append(("computer_vision", cv_result))

        # Layer 3: Check blue force tracking positions
        bft_result = await self.check_blue_force(position)
        results.append(("blue_force_tracking", bft_result))

        # SAFETY RULE: if ANY layer says FRIENDLY → final is FRIENDLY
        if any(r[1].classification == "FRIENDLY" for r in results):
            return Classification(
                classification="FRIENDLY",
                confidence=max(r[1].confidence for r in results
                              if r[1].classification == "FRIENDLY"),
                layers=results,
                reasoning="At least one IFF layer identified entity as FRIENDLY"
            )

        # If any layer says CIVILIAN → CIVILIAN (do not engage)
        if any(r[1].classification == "CIVILIAN" for r in results):
            return Classification(
                classification="CIVILIAN",
                confidence=max(r[1].confidence for r in results
                              if r[1].classification == "CIVILIAN"),
                layers=results,
                reasoning="Entity classified as CIVILIAN by at least one layer"
            )

        # If all available layers agree HOSTILE → HOSTILE
        hostile_results = [r for r in results if r[1].classification == "HOSTILE"]
        if len(hostile_results) == len(results) and len(results) >= 2:
            return Classification(
                classification="HOSTILE",
                confidence=min(r[1].confidence for r in hostile_results),
                layers=results,
                reasoning="All available IFF layers agree: HOSTILE"
            )

        # Default: UNKNOWN
        return Classification(
            classification="UNKNOWN",
            confidence=0.0,
            layers=results,
            reasoning="Insufficient data or conflicting layers — operator review required"
        )
```

### 8.6 Phase Rollout

| Phase | Capability | Hardware Needed |
|---|---|---|
| Phase 1-2 | Stub only: all entities classified UNKNOWN | None |
| Phase 3 | Layer 1 (transponder beacons): FRIENDLY/UNKNOWN | ESP32 or 868MHz RF module |
| Phase 4 | + CoT bridge for blue force position ingestion (read-only ATAK) | Network connection to TAK Server |
| Phase 5 | + Layer 2 (CV) + Layer 3 (full bidirectional ATAK) + integrated classifier | RPi + camera + IR LEDs |

---

## 9. H -- Airspace Compliance (Phase 1)

**Gap addressed:** C8 (Airspace Deconfliction and Regulatory Compliance)

### 9.1 Compliance Checks

```
Pre-Flight Airspace Check:
┌─────────────────────────────────────────────────┐
│  1. Check flight location against:              │
│     - B4UFLY database (FAA facility maps)       │
│     - Active TFRs (Temporary Flight             │
│       Restrictions)                             │
│     - Active NOTAMs for the area                │
│     - Controlled airspace boundaries            │
│     - Known restricted/prohibited areas         │
│                                                 │
│  2. Result:                                     │
│     CLEAR — no restrictions                     │
│     ADVISORY — near controlled airspace,        │
│       operator should verify                    │
│     RESTRICTED — LAANC authorization required   │
│     PROHIBITED — cannot fly here                │
│                                                 │
│  3. If RESTRICTED:                              │
│     - Display LAANC authorization instructions  │
│     - Block mission start until operator        │
│       confirms authorization obtained           │
│     - Log the authorization reference number    │
│                                                 │
│  4. Auto-generate geofence from airspace data:  │
│     - Ceiling: lowest of operator-set ceiling   │
│       and airspace ceiling                      │
│     - Lateral: stay within approved area        │
│     - Upload geofence to all drones             │
└─────────────────────────────────────────────────┘
```

### 9.2 Implementation by Phase

**Phase 1 (MVP):** Manual airspace check.
- Preflight checklist item: "Airspace: CLEAR / RESTRICTED / PROHIBITED"
- Operator manually checks B4UFLY app or SkyVector
- Operator manually enters LAANC authorization number if applicable
- Logged in audit trail

**Phase 2:** Semi-automated.
- Backend queries FAA UAS Facility Map data (available as KML/GeoJSON)
- Backend checks flight location against downloaded airspace boundaries
- Displays result in preflight check: "Airspace: CLEAR" or "Airspace: CLASS D - LAANC REQUIRED"
- Still requires manual LAANC authorization

**Phase 3:** Fully automated.
- Direct LAANC API integration (via AirMap, Aloft, or DroneUp APIs)
- Auto-submit LAANC authorization requests
- Auto-receive approval and generate compliant geofence
- Query live NOTAMs from FAA API
- Query live TFRs

### 9.3 NOTAM Awareness

```
NOTAM Check (Phase 2+):
1. Query aviationweather.gov NOTAM API for area within 5nm of flight location
2. Parse NOTAMs for relevance:
   - TFRs (Temporary Flight Restrictions): BLOCK flight
   - Airshows, parachute ops, rocket launches: WARN operator
   - Construction cranes, new obstacles: ADD to geofence exclusion zones
3. Display relevant NOTAMs in preflight check panel
4. Require operator acknowledgment before mission start
```

### 9.4 Geofence Generation from Airspace Data

```
Geofence Auto-Generation:
1. Get mission area polygon from mission planner
2. Overlay with airspace boundaries
3. If mission area intersects restricted airspace:
   a. If LAANC authorization covers the intersection: include with ceiling limit
   b. If no authorization: clip mission area to exclude restricted airspace
4. Generate ArduPilot geofence polygon + ceiling
5. Upload to all drones via MAVLink MISSION_ITEM (fence type)
6. Verify upload success
7. Parameters already set: FENCE_ENABLE=1, FENCE_ACTION=1 (RTL on breach)
```

---

## 10. Implementation Priority Matrix

| Subsystem | Phase | Effort | Impact | Dependencies |
|---|---|---|---|---|
| A: MAVLink v2 Signing | 1 | Trivial | Critical | firmware_flasher.py changes |
| B: Ground Station Security (TLS + JWT) | 1 | Moderate | Critical | FastAPI backend |
| B: Audit Trail | 1 | Moderate | Critical | Flight logger extension |
| B: Rate Limiting | 1 | Trivial | Medium | slowapi library |
| H: Airspace Compliance (manual) | 1 | Trivial | High | Preflight check extension |
| C: GPS Spoofing Detection | 3 | Moderate | Critical | EKF parameter tuning |
| C: GPS Jamming Detection | 3 | Moderate | Critical | RSSI monitoring |
| D: AES-256 Encryption | 3 | Moderate | Critical | Key management system |
| D: Mesh DTLS | 3 | Moderate | High | ESP32 mesh (Phase 3) |
| G: IFF Layer 1 (transponder) | 3 | Moderate | Critical | ESP32 or RF module |
| H: Airspace (semi-auto) | 3 | Moderate | High | FAA data download |
| E: Anti-Jamming Detection | 4 | Moderate | High | RSSI monitoring |
| E: Anti-Jamming Response | 4 | Complex | High | Autonomous behavior |
| F: Data Wipe (software) | 4 | Moderate | Critical (military) | Key management |
| G: IFF Layer 3 (ATAK/CoT) | 4 | Moderate | High | TAK Server access |
| F: Data Wipe (hardware) | 5 | Complex | High | Secure element hardware |
| G: IFF Layer 2 (CV) | 5 | Complex | High | RPi + camera + ML model |
| G: IFF Full Integration | 5 | Moderate | Critical | All three layers |
| D: Cloud mTLS | 6 | Moderate | Medium | Cloud infrastructure |

---

*This document defines the complete security architecture for the drone swarm orchestrator platform. Implementation proceeds in phases, with each phase building on the previous. Phase 1 items (MAVLink signing, TLS, JWT auth, audit trail) should be implemented before any field deployment. Phase 3 items (GPS spoofing detection, encryption, IFF transponder) are required before any operation in contested or multi-operator environments. Phase 5 items (CV-based IFF, hardware tamper protection) are required for defense-grade deployment.*
