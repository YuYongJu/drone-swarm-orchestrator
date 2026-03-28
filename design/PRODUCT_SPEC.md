---
title: Product Specification
type: spec
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, product, requirements, sdk, developer-platform]
---

# Drone Swarm Orchestrator -- Product Specification

**Document Version:** 2.0
**Last Updated:** 2026-03-26
**Status:** Active
**Owner:** Product Team

> "pip install drone-swarm. Connect your drones. Fly formations in 10 lines of Python."

---

## Table of Contents

1. [Vision & Mission Statement](#1-vision--mission-statement)
2. [User Personas](#2-user-personas)
3. [Core Value Propositions](#3-core-value-propositions)
4. [Feature Requirements](#4-feature-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Constraints & Assumptions](#6-constraints--assumptions)
7. [Success Metrics](#7-success-metrics)
8. [Competitive Positioning Matrix](#8-competitive-positioning-matrix)
9. [Glossary](#9-glossary)

---

## 1. Vision & Mission Statement

### Vision

A world where building a multi-drone application is as straightforward as building a web app. Any developer, any ArduPilot drone, any use case -- agriculture, search-and-rescue, inspection, wildfire response, drone shows.

### Mission

Build the open-source developer platform for multi-drone applications. We are **Stripe for Drones**: a clean Python SDK that abstracts away the complexity of MAVLink, fleet coordination, and swarm behavior so developers can focus on their application, not the plumbing. We are **Kubernetes for Drones**: declare what you want the fleet to do, and the platform handles assignment, coordination, failover, and telemetry across whatever hardware shows up on the network.

### What This Product Is

Drone Swarm Orchestrator (DSO) is an open-source Python SDK (`pip install drone-swarm`) and developer platform that turns a heterogeneous collection of ArduPilot-compatible drones into a programmable, coordinated fleet. It provides:

- A **Python SDK** installable via pip with a clean, Pythonic API for multi-drone control.
- A **simulation harness** built on ArduPilot SITL for testing swarm applications without hardware.
- An **orchestration engine** that plans missions, assigns roles, manages formations, and handles real-time replanning.
- A **firmware flasher** that configures each drone for swarm participation.
- A **fleet registry** that tracks every airframe, its capabilities, and its health.
- A **telemetry pipeline** that collects, stores, and streams flight data.
- A **cloud dashboard** (paid tier) for fleet analytics, mission management, and team collaboration.

### Who It's For

| Audience | Why They Care |
|---|---|
| **Drone application developers** | Need a SDK to build multi-drone features without becoming MAVLink experts. Want to `pip install` and start coding, not spend months on orchestration plumbing. |
| **Precision agriculture companies** | Building spray/survey products that coordinate drone fleets across large acreage. Need reliable formation flying and area coverage algorithms. |
| **Search-and-rescue technology teams** | Building coordinated grid search applications. Time-critical missions demand fault tolerance and fast deployment. |
| **Infrastructure inspection companies** | Building automated inspection workflows for utilities, bridges, pipelines. Need repeatable multi-drone mission execution. |
| **Drone show companies** | Choreographing synchronized formations with commodity hardware. Need precise timing and position control. |
| **Wildfire response agencies** | Building real-time perimeter mapping and hotspot monitoring with coordinated drone swarms. |
| **Researchers and universities** | Need a flexible testbed for swarm algorithms that runs on real hardware, not just simulation. Want a platform to publish reusable behaviors. |

---

## 2. User Personas

### 2.1 Application Developer (Primary Persona)

**Name:** Alex Kim
**Role:** Software engineer building a drone-powered crop monitoring SaaS product.
**Technical Level:** High. Python, REST APIs, cloud infrastructure. New to drones and MAVLink.

**Goals:**
- Add multi-drone coordination to their application without becoming a drone expert.
- Go from `pip install` to a working simulation in under 30 minutes.
- Deploy the same code to real hardware with minimal changes.
- Focus on application logic (crop analysis, route optimization) not MAVLink plumbing.

**Frustrations:**
- MAVLink is complex and poorly documented for multi-vehicle use cases.
- Existing drone SDKs are single-vehicle only.
- No standard way to test swarm code without physical hardware.
- Academic swarm code is research-quality, not production-quality.

**Key Workflows:**
1. `pip install drone-swarm` and read the quickstart guide.
2. Write a swarm behavior in Python against the SDK API.
3. Test in SITL: `dso sim run --drones 5 --script my_behavior.py`.
4. Deploy to physical fleet with configuration swap (sim -> hardware).

**Design Implications:**
- SDK-first: everything accessible via Python API, not just CLI.
- Comprehensive documentation with tutorials, examples, and API reference.
- SITL as a first-class development tool with zero hardware requirement.
- Type hints, docstrings, and IDE-friendly API design.
- PyPI packaging with minimal dependencies.

---

### 2.2 Drone Technician / DevOps

**Name:** Jake Okoye
**Role:** Builds drones from kits, flashes firmware, maintains the fleet hardware.
**Technical Level:** Medium-high. Comfortable with CLI tools, soldering, PID tuning.

**Goals:**
- Flash swarm-ready firmware to a new drone in under 5 minutes.
- Register the drone in the fleet with its hardware capabilities (camera, payload, endurance).
- Run bench tests and confirm MAVLink connectivity before handing off to developers.
- Diagnose and repair drones after missions using telemetry logs.

**Frustrations:**
- Firmware tools that only work on one OS.
- Fleet management that lives in a spreadsheet.
- Having to remember which drone has which radio address.

**Key Workflows:**
1. Connect drone via USB, run `dso flash --profile recon-lite`.
2. Run `dso register --scan` (reads QR from airframe label).
3. Run `dso preflight --drone RECON-07` to validate sensors and comms.
4. After mission: `dso logs download --drone RECON-07 --mission M-2026-0042`.

**Design Implications:**
- CLI-first tooling with scriptable commands.
- Hardware tier auto-detection during flash.
- QR-based identity system printed on adhesive labels.
- Log viewer with filtering by drone, mission, and event type.

---

### 2.3 Integration Developer

**Name:** Priya Chatterjee
**Role:** Extends the platform -- writes custom behaviors, integrates sensors, builds plugins, contributes to the open-source project.
**Technical Level:** High. Python, JavaScript, MAVLink, embedded systems.

**Goals:**
- Write a custom swarm behavior (e.g., "distributed wildfire perimeter tracker") and publish it to the marketplace.
- Integrate a new sensor payload and surface its data through the SDK.
- Run swarm algorithms against the SITL simulator before deploying to hardware.
- Contribute upstream to the open-source project.

**Frustrations:**
- Monolithic systems that can't be extended without forking.
- Poor API documentation.
- No simulation environment that matches real-world behavior.

**Key Workflows:**
1. Scaffold a new behavior module: `dso dev new-behavior perimeter-tracker`.
2. Implement logic in Python against the Behavior API.
3. Test in SITL: `dso sim run --drones 5 --behavior perimeter-tracker`.
4. Publish to marketplace: `dso publish behavior perimeter-tracker`.

**Design Implications:**
- Plugin architecture with well-defined extension points.
- Behavior API with clear lifecycle hooks (init, tick, on_event, teardown).
- SITL integration as a first-class development tool.
- Comprehensive API documentation with examples.
- Contributor guide and code-of-conduct for the open-source community.
- Marketplace for sharing and monetizing custom behaviors.

---

### 2.4 Field Operator (Secondary Persona)

**Name:** Sergeant Maria Reyes
**Role:** Non-technical operator who runs missions from a tablet in the field, using applications built on the SDK.
**Technical Level:** Low. Can follow checklists. Cannot write code or configure firmware.

**Goals:**
- Launch a coordinated mission in under 10 minutes from arrival on-site.
- Monitor fleet status at a glance (battery, GPS lock, signal strength).
- Trigger pre-planned missions with one tap.
- Trust the system to handle failures without manual intervention.

**Frustrations:**
- Complex GCS software with too many settings.
- Missions that require a laptop and a mouse in the field.
- Systems that fail silently or require debugging mid-operation.

**Key Workflows:**
1. Power on drones, scan QR codes to confirm fleet roster.
2. Run automated pre-flight checks.
3. Select a mission template, tap "Launch."
4. Monitor the map, receive alerts, tap "RTL All" if needed.

**Design Implications:**
- Applications built on the SDK must be able to expose simple operator interfaces.
- SDK provides building blocks for touch-first UIs (status streams, command APIs).
- Traffic-light status indicators (green/yellow/red) per drone.
- One-button emergency actions always visible.

---

## 3. Core Value Propositions

### 3.1 SDK-First: pip install and Go

DSO is distributed as a Python package on PyPI. Developers install with `pip install drone-swarm` and have access to the full orchestration engine, simulation harness, and fleet management tools. No Docker, no custom build system, no vendor account required.

```python
from drone_swarm import Swarm, Formation, Mission

# Connect to SITL or real drones
swarm = Swarm.connect(["sitl://localhost:5760"] * 3)
swarm.arm_all()
swarm.takeoff(altitude=20)
swarm.fly_formation(Formation.V_SHAPE, spacing=10)
swarm.execute(Mission.area_sweep(bounds=[(lat1,lon1), (lat2,lon2)]))
swarm.rtl_all()
```

### 3.2 Hardware-Agnostic (Any ArduPilot Drone)

DSO does not sell drones. It orchestrates whatever you bring. Any airframe running ArduPilot can join the swarm. The platform classifies drones into hardware tiers and assigns roles accordingly.

**Hardware Tier Classification:**

| Tier | Typical Build | Estimated Cost | Capabilities | Typical Roles |
|---|---|---|---|---|
| **Class A** | F450 frame, Pixhawk 6C mini, GPS, SiK radio | $195-220 | GPS waypoint flight, basic telemetry | Relay node, formation filler, sensor carrier |
| **Class B** | S500 frame, Pixhawk 6C, GPS + compass, SiK radio, FPV camera | $230-255 | Everything in A + live video, longer endurance | Recon, overwatch, area scan |
| **Class C** | Custom frame, Cube Orange, RTK GPS, companion computer (RPi 4), LTE modem | $300-500 | Everything in B + precision nav, onboard compute, mesh relay | Leader, edge compute, relay hub |
| **Class D** | Heavy-lift frame, redundant flight controller, multi-sensor payload, encrypted comms | $800+ | Everything in C + payload delivery, hardened comms | Command relay, payload delivery |

The platform auto-detects hardware capabilities during the flash/register step and assigns the correct tier. The SDK respects tier constraints -- you cannot assign a Class A drone to a role that requires onboard compute.

### 3.3 Simulation-First Development

Every feature of the SDK works identically in SITL simulation and on real hardware. Developers can build and test complete applications without owning a single drone:

```bash
# Start a 5-drone simulation
dso sim start --drones 5

# Run your application against simulated drones
python my_app.py --fleet sitl

# Same code, real drones
python my_app.py --fleet production
```

### 3.4 DIY-First (Commodity Parts, $195-285/Drone)

The barrier to entry is the cost of a Class A drone: approximately $195-220 in commodity parts ordered from standard hobby suppliers. No proprietary hardware. No custom PCBs for the base tier. The bill of materials for each tier is published and maintained as part of the project documentation.

**Design principle:** If a component is available from three or more independent suppliers, it's a valid choice. Single-source components are flagged and avoided where possible.

### 3.5 Resilient (Handles Comms Drops, Drone Loss, Battery Failures)

The swarm does not depend on any single drone. The orchestration engine continuously monitors fleet health and replans in real time:

| Failure Mode | System Response |
|---|---|
| **Comms loss (single drone)** | Drone executes onboard failsafe (loiter, then RTL). Fleet replans around the gap. |
| **Comms loss (ground station)** | All drones execute pre-programmed autonomous continuation for N seconds, then RTL. |
| **Battery critical (single drone)** | Drone RTLs. Its role is reassigned to the next capable drone. |
| **Battery critical (multiple drones)** | Mission degrades gracefully. Application is notified via callback. Minimum-viable coverage is maintained as long as possible. |
| **Drone lost (crash / flyaway)** | Detected via telemetry timeout. Fleet replans. Last known position logged. |
| **GPS degradation** | Drone demotes itself to "reduced capability." Excluded from precision roles. |

### 3.6 Progressively Capable (Free SDK to Enterprise)

You don't need the full stack on day one. A developer can start with a SITL simulation and scale to enterprise deployment:

- **Day 1:** `pip install drone-swarm`, run tutorials in SITL, zero cost.
- **Month 1:** 3 physical drones, basic formations, open-source SDK.
- **Month 3:** 10 drones, cloud dashboard for telemetry and fleet analytics.
- **Month 6:** 20+ drones with mesh networking, custom behaviors from marketplace.
- **Year 1:** Enterprise tier with encrypted comms, ATAK integration, and compliance features.

---

## 4. Feature Requirements

### Priority Definitions

| Priority | Definition | Timeline |
|---|---|---|
| **P0** | Must have for the SDK v0.1 release. Without these, the SDK does not function. | SDK MVP |
| **P1** | Required for SDK v1.0. Without these, the SDK is a toy. | v1.0 |
| **P2** | Cloud platform and competitive differentiators. These make the platform better than alternatives. | v2.0 |
| **P3** | Enterprise/defense-grade features. Required for enterprise and government adoption. | v3.0 |

---

### P0 -- SDK MVP (Must Have for PyPI Release)

#### P0.1 Multi-Drone Connection and Telemetry

**Description:** The SDK connects to multiple drones simultaneously over MAVLink and provides a Pythonic interface to continuous telemetry (position, altitude, heading, battery, GPS fix quality, armed/disarmed state).

**Acceptance Criteria:**
- Connect to at least 3 drones simultaneously via SiK 915MHz radios or SITL.
- Provide async telemetry streams with update rate of at least 2 Hz.
- Detect and handle MAVLink heartbeat timeout (no heartbeat for 5 seconds triggers "comms lost" state).
- Support MAVLink v2 protocol.
- Clean Python API: `swarm = Swarm.connect([...])`, `drone.telemetry.battery`, etc.

**Technical Notes:**
- Each drone gets a unique MAVLink system ID (1-250).
- SDK runs a MAVLink router (mavlink-router or equivalent) to multiplex connections.
- Telemetry is available via async iterators and callback registration.

---

#### P0.2 Formation Flight API

**Description:** A Python API to command a group of drones to fly in a specified geometric formation, maintaining relative positions as the formation moves.

**Supported Formations:**
- **V-formation:** Classic chevron. Configurable angle and spacing.
- **Line:** Single-file or abreast. Configurable spacing and orientation.
- **Orbit:** Drones circle a point at configurable radius, altitude, and angular spacing.
- **Sweep:** Parallel tracks covering a rectangular area. Configurable track spacing and overlap.

**Acceptance Criteria:**
- Developer selects a formation type and parameters via SDK API.
- Drones autonomously navigate to their assigned positions within the formation.
- Formation moves as a unit when given a waypoint or heading command.
- Formation maintains coherence during transit (drones correct for drift).
- If a drone is removed, remaining drones close the gap.
- API: `swarm.fly_formation(Formation.V_SHAPE, spacing=10)`.

**Technical Notes:**
- Formation positions are computed as offsets from a "formation origin" (typically the leader drone or a virtual point).
- Position commands sent as MAVLink `SET_POSITION_TARGET_GLOBAL_INT` at 1-2 Hz.
- Initial implementation: leader-follower with ground station computing offsets. Future: distributed consensus.

---

#### P0.3 Firmware Flasher with Swarm Configuration

**Description:** A CLI tool that flashes ArduPilot firmware to a connected flight controller and applies swarm-specific configuration (MAVLink system ID, failsafe parameters, telemetry rates, radio channel).

**Acceptance Criteria:**
- Flash firmware via USB connection using `dso flash`.
- Auto-detect flight controller type (Pixhawk 6C, Cube Orange, etc.).
- Apply swarm parameter set: system ID, failsafe RTL altitude, battery failsafe voltage, telemetry stream rates, MAVLink signing key.
- Support hardware tier profiles (Class A/B/C/D) that set appropriate defaults.
- Idempotent: re-running the flash command on an already-configured drone updates parameters without full reflash unless firmware version has changed.

**Technical Notes:**
- Built on top of `pymavlink` and ArduPilot's bootloader protocol.
- Parameter templates stored as YAML files, one per hardware tier.
- MAVLink signing key is generated per-fleet and embedded during flash.

---

#### P0.4 Fleet Registry with QR Codes

**Description:** A database of all drones in the fleet, their hardware capabilities, and current status. Each drone has a printed QR code label for quick identification.

**Acceptance Criteria:**
- `dso register` creates a new fleet entry with: drone ID, hardware tier, MAVLink system ID, radio address, build date, component list.
- `dso register --scan` reads a QR code (via webcam or phone camera) containing the drone's unique ID and auto-populates registration.
- Fleet registry is stored locally (SQLite) and optionally synced to cloud dashboard.
- QR code encodes: drone ID, system ID, hardware tier, fleet membership.
- `dso fleet list` shows all registered drones with health status.
- SDK API: `Fleet.list()`, `Fleet.register(drone)`, `Fleet.get(drone_id)`.

**Technical Notes:**
- QR code format: JSON payload, base64-encoded, using standard QR encoding.
- QR labels are generated as printable PDFs via `dso fleet print-labels`.
- Registry schema supports custom metadata fields for user extensions.

---

#### P0.5 Pre-Flight Safety Checks

**Description:** Automated checks run before any drone is cleared for launch, validating hardware health, configuration, and environmental conditions.

**Check Sequence:**

| Check | Pass Criteria | Failure Action |
|---|---|---|
| MAVLink heartbeat | Receiving heartbeat at expected rate | Block launch, flag comms issue |
| GPS fix | 3D fix with HDOP < 2.0 | Block launch, flag GPS issue |
| Battery voltage | Above configured minimum (e.g., 90% capacity) | Block launch, flag battery |
| Accelerometer calibration | Within tolerance | Block launch, require recalibration |
| Compass calibration | Heading consistent with GPS track | Warn, allow override |
| Radio signal strength | RSSI above threshold | Warn, allow override |
| Firmware version | Matches fleet-expected version | Block launch, require reflash |
| MAVLink signing | Signing active and key matches fleet | Block launch, require reflash |
| Geofence loaded | Geofence present if mission requires it | Block launch if mission requires geofence |
| Failsafe parameters | RTL altitude, battery failsafe, comms failsafe all configured | Block launch |

**Acceptance Criteria:**
- CLI: `dso preflight --drone <id>` runs all checks and reports pass/fail with details.
- CLI: `dso preflight --fleet` runs checks on all registered and connected drones.
- SDK API: `drone.preflight()` returns structured results.
- Failed checks produce actionable error messages ("GPS HDOP is 3.2, need < 2.0. Move drone to open area or wait for better satellite geometry.").
- Results are logged and attached to the mission record.

---

#### P0.6 Failsafe: Auto-RTL on Battery/Comms Loss

**Description:** Every drone in the fleet has onboard failsafe logic that triggers Return-to-Launch (RTL) when critical failures are detected, independent of ground station connectivity.

**Failsafe Triggers:**

| Trigger | Threshold | Action |
|---|---|---|
| Battery voltage critical | Configurable (default: 3.5V/cell) | RTL immediately |
| Battery voltage low | Configurable (default: 3.6V/cell) | Alert operator, continue mission for N seconds, then RTL |
| GCS heartbeat lost | Configurable (default: 10 seconds) | Loiter for 30 seconds, then RTL |
| GPS lost | No fix for 5 seconds | Hold altitude, attempt to reacquire. RTL if no fix after 30 seconds. |
| Geofence breach | Exits defined boundary | RTL immediately |

**Acceptance Criteria:**
- Failsafe parameters are baked into firmware during the flash step.
- Failsafes operate entirely onboard -- no ground station dependency.
- SDK receives failsafe events via callbacks when comms are available.
- RTL altitude is staggered per drone (based on system ID) to prevent collision during mass RTL.
- All failsafe events are logged with timestamp and trigger reason.

---

#### P0.7 Dynamic Replanning When Drones Are Lost

**Description:** When a drone is lost (crash, RTL, comms failure), the orchestration engine automatically replans the mission to maintain coverage with remaining assets.

**Acceptance Criteria:**
- Loss detection within 5 seconds of last telemetry.
- Remaining drones receive updated position assignments within 10 seconds of loss detection.
- Formations close gaps automatically.
- Sweep patterns are recalculated to maintain area coverage.
- If remaining drones are insufficient for the mission type, the application is notified via callback with options: continue degraded, pause, or abort.
- Replanning events are logged with before/after fleet state.
- SDK API: `swarm.on_replan(callback)`.

---

#### P0.8 SITL Simulation Harness

**Description:** A built-in simulation environment that runs ArduPilot SITL instances and provides the same SDK API as real hardware, enabling developers to build and test applications without physical drones.

**Acceptance Criteria:**
- `dso sim start --drones N` launches N SITL instances.
- SDK connects to simulated drones identically to real drones.
- Simulation supports all formation types and mission patterns.
- Configurable environmental conditions (wind, GPS noise).
- Test harness for CI/CD: run automated scenario tests against SITL.
- Zero hardware requirement for development.

**Technical Notes:**
- Built on ArduPilot SITL with automated instance management.
- Docker-based SITL option for reproducible environments.
- Headless mode for CI/CD pipelines.

---

#### P0.9 Mission Logging and Replay

**Description:** Every mission is recorded end-to-end -- all telemetry, commands, events, and operator actions -- and can be replayed programmatically or in the UI.

**Acceptance Criteria:**
- Mission recording starts automatically at launch and stops at mission end.
- All MAVLink messages are logged per drone (binary .tlog format).
- Commands and system events are logged with timestamps.
- `dso logs list` shows all recorded missions with metadata (date, duration, drone count, outcome).
- SDK API: `Mission.replay(mission_id)` for programmatic replay.
- Logs are exportable as CSV (telemetry) and JSON (events).

---

### P1 -- v1.0 (Production SDK)

#### P1.1 Live Role Reassignment Mid-Flight

Operators or the orchestration engine can reassign drone roles during an active mission (e.g., promote a Class A filler to a scout role if the original scout RTLs). Role changes propagate new behavior parameters to the affected drone within 2 seconds. SDK API: `swarm.reassign_role(drone, new_role)`.

#### P1.2 Formation Maintenance (Active Position Correction)

Continuous closed-loop control that corrects drone positions within a formation. Target: each drone stays within 3 meters of its assigned formation position in winds up to 15 knots. Uses PID-style correction based on GPS position error.

#### P1.3 Geofence API

Define geofence boundaries programmatically. Support polygon and circular geofences. Geofences are uploaded to each drone's flight controller during pre-flight. Breach triggers configurable action (RTL, loiter, or land). SDK API: `swarm.set_geofence(Geofence.polygon(points))`.

#### P1.4 Mission Builder API

Programmatic mission planning: define waypoints, set altitudes, assign formations per leg, configure loiter points and search patterns. Missions are saved as reusable templates. Export to standard formats (QGC plan files) for interoperability. SDK API: `Mission.build().add_waypoint(...).set_formation(...)`.

#### P1.5 Telemetry Streaming API

Structured telemetry streaming for the entire fleet. Per-drone data: battery voltage and percentage with trend line, GPS fix quality and satellite count, radio signal strength (RSSI), altitude (AGL and MSL), ground speed, flight mode, and armed/disarmed state. SDK API: `async for telemetry in swarm.telemetry_stream()`.

#### P1.6 Automated SITL Test Suite for CI/CD

An automated test harness that spins up N simulated drones using ArduPilot SITL and runs mission scenarios end-to-end. Tests validate: formation accuracy, failsafe behavior, replanning correctness, and telemetry pipeline integrity. Runs in CI/CD (GitHub Actions). Minimum test scenarios: 3-drone formation flight, mid-mission drone loss, battery failsafe trigger, comms loss recovery.

#### P1.7 Behavior Plugin System

Plugin architecture for custom swarm behaviors. Developers implement the Behavior interface (init, tick, on_event, teardown) and register behaviors with the SDK. Behaviors can be loaded dynamically, shared as Python packages, and tested in SITL. SDK API: `@behavior("perimeter-patrol")`.

---

### P2 -- v2.0 (Cloud Platform)

#### P2.1 Cloud Dashboard

Web-based dashboard for fleet management, mission monitoring, and analytics. Real-time map with drone positions, telemetry charts, mission history, and team collaboration. Hosted as a paid SaaS service.

#### P2.2 Telemetry Analytics and Alerting

Cloud-based analytics on fleet telemetry: flight time trends, battery degradation curves, maintenance predictions, anomaly detection. Configurable alerts via webhook, email, or SMS.

#### P2.3 Drone-to-Drone Mesh Networking (ESP32 + LoRa)

Add ESP32 modules with LoRa radios to enable direct drone-to-drone communication. Drones can relay commands and telemetry through the mesh, extending range beyond direct ground station reach. Mesh topology is self-healing -- if a relay drone is lost, the mesh re-routes.

**Hardware:** ESP32-S3 + SX1276 LoRa module per drone. Estimated additional cost: $15-25 per drone.

#### P2.4 Autonomous Path Planning with Obstacle Avoidance

Drones compute local paths that avoid known obstacles (terrain, structures, no-fly zones) using onboard compute (Class C+ drones). Obstacle data loaded from mission planning or shared in real time via mesh. Initially 2D (altitude deconfliction), then 3D path planning.

#### P2.5 Collision Avoidance Between Drones

Inter-drone collision avoidance using shared position data. Each drone maintains a safety bubble (configurable, default 5m radius). If two bubbles overlap on projected trajectories, the lower-priority drone yields. Priority is based on role, then system ID.

#### P2.6 Task Allocation Algorithm

Optimal assignment of drones to roles based on: hardware tier, battery remaining, distance to role start position, current task load. Uses a combinatorial auction or Hungarian algorithm variant. Re-runs on fleet changes (drone lost, drone added, battery thresholds crossed).

#### P2.7 Multi-Operator Support

Multiple operators can connect to the same mission simultaneously. Role-based access: Admin (full control), Operator (monitor + emergency actions), Viewer (read only). Operator actions are attributed and logged.

#### P2.8 REST and WebSocket API

RESTful API and WebSocket API for external systems. Endpoints for: fleet status, mission control (start/pause/abort), telemetry streaming, mission planning (CRUD), drone command (per-drone or fleet-wide). OpenAPI 3.0 specification. API key authentication. Rate limiting.

---

### P3 -- v3.0 (Enterprise / Defense Tier)

#### P3.1 IFF System (Identification, Friend or Foe)

Multi-layer identification system:
- **Layer 1: Transponder.** Each friendly drone broadcasts an encrypted beacon on a dedicated frequency. Receivable by other fleet drones and ground stations.
- **Layer 2: Computer Vision.** Onboard cameras (Class C+ drones) identify airframes by visual markers (IR strobes, painted patterns).
- **Layer 3: Blue Force Tracking.** All friendly positions are shared on a common operating picture. Any airborne object not in the BFT database is flagged as unknown.

#### P3.2 Encrypted Communications

All MAVLink traffic encrypted end-to-end. MAVLink v2 signing as the baseline (P0). AES-256 encryption of the full data link for P3. Key management: per-fleet keys with rotation schedule. Mesh traffic encrypted at the LoRa layer.

#### P3.3 ATAK / Link 16 Integration

Publish drone positions and mission status to ATAK (Android Team Awareness Kit) via Cursor-on-Target (CoT) protocol. Receive target designations and no-fly zones from ATAK. Stretch: Link 16 message injection via TAK Server bridge for integration with conventional military C2.

#### P3.4 Classification-Ready Architecture

Architecture supports deployment in classified environments: air-gapped operation (no internet dependency -- already a baseline requirement), audit logging for all operator actions and system events, role-based access control with CAC/PIV smart card support, data-at-rest encryption for mission logs and fleet database, STIG-hardened deployment configurations.

#### P3.5 Autonomous Target Tracking

Onboard computer vision (Class C+ drones) detects and tracks designated targets. Target handoff between drones as they transit through coverage areas. Tracking data shared via mesh or ground station relay. Operator-in-the-loop: all tracking is for situational awareness; no autonomous engagement.

#### P3.6 Compliance and Audit Package

SOC 2 Type II readiness, FedRAMP pathway documentation, ITAR compliance framework, SBOM generation, and third-party security audit reports. Required for enterprise and government customers.

---

## 5. Non-Functional Requirements

### 5.1 Latency

| Path | Requirement |
|---|---|
| SDK command to drone execution | < 500ms end-to-end |
| Telemetry update to SDK callback | < 500ms |
| Failsafe detection to action | < 2 seconds (onboard) |
| Replanning trigger to new assignments | < 10 seconds |
| Formation position correction loop | 1-2 Hz update rate |

### 5.2 Scalability

| Metric | Requirement |
|---|---|
| Maximum drones per SDK instance | 50 (P0: 3, P1: 10, P2: 50) |
| Maximum concurrent operators per mission | 5 (P2) |
| Maximum simultaneous missions | 1 per instance (P0/P1), 3 (P2) |
| Telemetry storage (cloud) | 90 days at full rate |
| Fleet registry size | 500 drones per fleet database |
| PyPI package size | < 50MB installed |

### 5.3 Reliability

- **Graceful degradation:** Any single component failure (one drone, one radio, one operator terminal) must not halt the mission. The system adapts and continues.
- **No single point of failure in the air:** Every airborne drone can operate independently if all external systems fail. Onboard failsafes are the last line of defense.
- **SDK recovery:** If the SDK application crashes, it reconnects to all drones on restart. Drones continue their last commanded behavior during the outage.
- **Data integrity:** Mission logs are written to disk in append-only mode. No log corruption on crash.

### 5.4 Portability

| Platform | Support Level |
|---|---|
| Linux (Ubuntu 22.04+) | Primary. Full support. |
| macOS (13+) | Development. Full support. |
| Windows (10/11) | Development. Full support via WSL2. |
| Raspberry Pi 4 / 5 (Ubuntu) | Edge deployment. Full support. |
| Docker | Containerized SDK + SITL for CI/CD. |
| GitHub Actions / CI | SITL test suite runs in CI. |

**Minimum hardware for SDK:** Python 3.10+, 2GB RAM, any modern CPU.

### 5.5 Offline-First

- All core SDK operations (connect, fly, log) work with zero internet connectivity.
- Cloud dashboard features require internet but the SDK never does.
- Map tiles can be pre-cached for the area of operations.
- Firmware binaries are bundled in the installation package.
- No telemetry or data is sent to external servers by default. Cloud sync is opt-in.

### 5.6 Security

| Layer | Mechanism |
|---|---|
| Radio link (MAVLink) | MAVLink v2 signing (P0). AES-256 encryption (P3). |
| Cloud API | API key + OAuth 2.0. TLS for all connections. |
| Fleet database | File-level encryption at rest (P3). |
| Mission logs | Append-only writes. Checksummed. Encrypted at rest (P3). |
| SDK distribution | Signed PyPI releases. Reproducible builds. SBOM published. |

---

## 6. Constraints & Assumptions

### Technical Constraints

| Constraint | Rationale |
|---|---|
| **ArduPilot as firmware (ArduPilot-native)** | ArduPilot has broader hardware support, a larger hobbyist community, and more accessible documentation. PX4 support is a future extension. |
| **Python as SDK language** | Python has the best MAVLink library ecosystem (pymavlink, dronekit). Largest developer community for the target audience. Performance-critical paths can use asyncio or Cython. Acceptable for up to 50 drones. |
| **Star topology first, mesh later** | Star topology (all drones talk to ground station) is simpler, more reliable, and sufficient for the SDK MVP. Mesh networking (P2) adds complexity in routing, latency, and testing. |
| **SiK 915MHz for telemetry** | Proven, cheap ($15-20/radio), sufficient range (1-2km with stock antennas, 5km+ with directional). Legal under FCC Part 15 (900MHz ISM band, < 1W). |
| **No internet dependency for core SDK** | Non-negotiable. SAR, remote agricultural, and field use cases all require fully offline operation. Cloud features are additive, never required. |
| **FCC Part 15 compliance** | All radio emissions must comply with FCC Part 15 rules for the 900MHz ISM band. No amateur radio license required for basic operation. |

### Assumptions

- Developers have basic Python proficiency and can install packages via pip.
- For hardware deployment, operators have basic drone piloting skills or training equivalent to FAA Part 107.
- Each drone is physically labeled with its QR code and system ID.
- The area of operations has adequate GPS satellite coverage (>8 satellites visible).
- Wind conditions are within the airframe's rated capability (typically < 20 knots for Class A).
- All drones in a mission are running the same ArduPilot firmware version.

### Regulatory Considerations

- FAA Part 107 governs commercial small UAS operations in the United States.
- Swarm operations may require Part 107 waivers for: operations beyond VLOS, operations over people, multiple drones per pilot.
- FCC Part 15 governs the 915MHz ISM band used for SiK radios.
- Export control (ITAR/EAR) may apply to enterprise/defense features (P3). Legal review required before P3 development.
- International operations require compliance with local aviation and radio regulations.

---

## 7. Success Metrics

### SDK v0.1 (PyPI Release / P0)

| Metric | Target |
|---|---|
| PyPI downloads (first 3 months) | 5,000+ |
| GitHub stars | 1,000+ |
| SITL tutorial completion | Under 30 minutes from install to first formation |
| Fleet size supported | 3 drones |
| Formation types | At least 4 (V-shape, line, orbit, sweep) |
| Total hardware cost for demo | Under $1000 (3x Class A drones + shared equipment) |
| Demo video | Filmed with telemetry overlay, published on YouTube |

### SDK v1.0

| Metric | Target |
|---|---|
| PyPI downloads (cumulative) | 25,000+ |
| GitHub stars | 3,000+ |
| External contributors | 25+ |
| Fleet size | 10 drones (mixed Class A/B) |
| Published behaviors (community) | 10+ |
| Test coverage | Automated SITL tests for all P0 + P1 features |
| Discord community | 500+ members |

### v2.0 (Cloud Platform)

| Metric | Target |
|---|---|
| Cloud dashboard users | 200+ |
| Paying customers (cloud) | 50+ |
| MRR from cloud services | $25K+ |
| Fleet size supported | 50+ drones |
| Mesh networking | At least 5 drones communicating via LoRa mesh |
| Third-party integrations | 5+ built on the API |
| Marketplace behaviors published | 25+ |

### v3.0 (Enterprise / Defense)

| Metric | Target |
|---|---|
| Enterprise customers | 5+ |
| ARR from enterprise tier | $500K+ |
| Encrypted comms | AES-256 on all data links |
| ATAK integration | Drones visible in ATAK COP |
| Security audit | Third-party audit with zero critical findings |
| Compliance certifications | SOC 2 Type II in progress |

---

## 8. Competitive Positioning Matrix

| Capability | **DSO (This Product)** | **Swarmer** | **Auterion** | **Shield AI (Hivemind)** | **ArduPilot + QGC** | **DroneKit** |
|---|---|---|---|---|---|---|
| **Primary offering** | Python SDK for multi-drone apps | Swarm coordination SaaS | Enterprise drone OS | Autonomous aircraft AI | Single-drone autopilot | Single-drone Python SDK |
| **Multi-drone** | Yes (core feature) | Yes | Limited | Yes | No | No |
| **Open source** | Yes (SDK core) | No | Partially (PX4) | No | Yes | Yes (archived) |
| **SDK / developer-first** | Yes (pip install) | No (SaaS only) | No (enterprise only) | No | No (no SDK) | Yes (single drone) |
| **Hardware-agnostic** | Yes (any ArduPilot) | Limited | Certified hardware | Proprietary | Yes | Yes |
| **SITL simulation** | Built-in | Unknown | No | No | Manual setup | Manual setup |
| **Cloud platform** | Yes (paid tier) | Yes (core) | Yes | No | No | No |
| **Mesh networking** | Yes (P2, LoRa) | Unknown | No | Proprietary | No | No |
| **Price** | Free SDK, paid cloud | SaaS subscription | $50K+ | >$1M | Free | Free |
| **Target user** | Developers | Enterprise operators | Enterprise | Large DoD | Hobbyists | Developers (single drone) |

### Competitive Summary

**vs. Swarmer:** Swarmer offers swarm coordination as a closed SaaS platform. DSO is open-source and SDK-first -- developers own their code and can run offline. Swarmer targets operators; DSO targets developers building products.

**vs. Auterion:** Auterion provides an enterprise drone operating system but focuses on single-drone fleet management and requires certified hardware. DSO is hardware-agnostic, open-source, and focused on multi-drone coordination as a developer tool.

**vs. Shield AI:** Shield AI targets billion-dollar DoD programs with proprietary, vertically integrated solutions. DSO targets the developer ecosystem building civilian and dual-use drone applications. Different markets, different business models.

**vs. ArduPilot + QGC:** ArduPilot and QGroundControl are the foundation DSO is built on. QGC is an excellent single-drone ground station, but it has no swarm coordination, no formation flight, no fleet management, and no SDK. DSO is the multi-drone developer layer on top of the ArduPilot ecosystem.

**vs. DroneKit:** DroneKit was the original Python SDK for drones but is effectively archived and only supports single-vehicle control. DSO is the spiritual successor: modern Python, async-first, multi-drone native, actively maintained.

---

## 9. Glossary

| Term | Definition |
|---|---|
| **AGL** | Above Ground Level. Altitude measured relative to the terrain directly below. |
| **ArduPilot** | Open-source autopilot firmware for drones, rovers, boats, and submarines. |
| **ATAK** | Android Team Awareness Kit. Military situational awareness app. |
| **BFT** | Blue Force Tracking. System for tracking friendly forces on a common map. |
| **C2** | Command and Control. Systems and processes for directing operations. |
| **CAC** | Common Access Card. US DoD smart card for authentication. |
| **CoT** | Cursor-on-Target. XML messaging protocol used by ATAK and military C2 systems. |
| **DSO** | Drone Swarm Orchestrator. This product. |
| **FCC Part 15** | US regulations governing unlicensed radio transmissions, including ISM bands. |
| **GCS** | Ground Control Station. The operator's interface to the drone fleet. |
| **HDOP** | Horizontal Dilution of Precision. Measure of GPS horizontal accuracy. Lower is better. |
| **IFF** | Identification, Friend or Foe. System for distinguishing friendly and hostile units. |
| **ISM Band** | Industrial, Scientific, and Medical radio band. Unlicensed spectrum (e.g., 915MHz, 2.4GHz). |
| **ITAR** | International Traffic in Arms Regulations. US export control law. |
| **LoRa** | Long Range. Low-power wide-area network modulation technique. |
| **MAVLink** | Micro Air Vehicle Link. Lightweight protocol for drone communication. |
| **MSL** | Mean Sea Level. Altitude measured relative to sea level. |
| **PyPI** | Python Package Index. The repository for Python packages (`pip install`). |
| **PX4** | Open-source autopilot firmware (alternative to ArduPilot). |
| **QGC** | QGroundControl. Open-source ground control station for MAVLink vehicles. |
| **RSSI** | Received Signal Strength Indicator. Measure of radio signal quality. |
| **RTL** | Return to Launch. Failsafe mode where the drone flies back to its launch point. |
| **SAR** | Search and Rescue. |
| **SBOM** | Software Bill of Materials. List of all software components in a product. |
| **SDK** | Software Development Kit. A set of tools and libraries for building applications. |
| **SiK** | Silicon Labs-based radio firmware for MAVLink telemetry radios. |
| **SITL** | Software In The Loop. ArduPilot simulator that runs full firmware on a PC. |
| **VLOS** | Visual Line of Sight. Regulatory requirement that the pilot can see the drone. |

---

*This document is the single source of truth for the Drone Swarm Orchestrator product. All design, engineering, and planning decisions should reference and align with this specification. Proposed changes should be submitted as revisions to this document with rationale.*

---

## Related Documents

- [[ROADMAP]] -- Phased implementation timeline for features defined here
- [[BUSINESS_PLAN]] -- Open-core business model and developer platform economics
- [[HARDWARE_SPEC]] -- Hardware requirements and bill of materials
- [[SYSTEM_ARCHITECTURE]] -- Technical architecture implementing these requirements
- [[UI_DESIGN]] -- Cloud dashboard and developer console UI design
- [[TESTING_STRATEGY]] -- Testing approach for validating these requirements
- [[INTEGRATION_AUDIT]] -- Cross-document consistency check against this spec
- [[DECISION_LOG]] -- Key decisions made during design
