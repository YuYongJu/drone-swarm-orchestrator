---
title: Vision Alignment Audit
type: review
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, audit, strategy, alignment]
---

# Vision Alignment Audit

**Auditor:** Product Strategy Review
**Date:** 2026-03-26
**Scope:** All design documents, protocols, source code, business plan, roadmap, and supporting materials
**Method:** Evaluated every artifact against the product vision ("bring any drone, join the swarm"), the roadmap phases, the user journey of a student builder, and the defense go-to-market strategy.

---

## Relevance Score: 8/10
## Coherence Score: 7/10
## Completeness Score: 8/10

---

## Systems That Are Exactly Right (keep as-is)

### 1. Core Orchestrator (swarm.py)
The heart of the product. Async rewrite addresses the pressure test findings. State machine for drone status transitions, RTL altitude staggering, role-based capability assignment -- all directly serve the "bring any drone, join the swarm" value proposition. This is Phase 0 done right.

### 2. Firmware Flasher (firmware_flasher.py)
Clean CLI interface. Auto-detects board type. Applies swarm-specific parameters including 4S battery thresholds (fixed per integration audit). This is the literal on-ramp for "bring your drone" -- without it, there is no product.

### 3. Fleet Registry (fleet_registry.py)
QR code registration, hardware capability classes, JSON-per-drone storage. Simple, file-based, field-friendly. Exactly the right level of complexity for Phase 1.

### 4. Pre-Flight Checks (preflight.py)
Covers comms, GPS, battery, compass, failsafes. This is a safety-critical system and it exists with proper pass/fail semantics. Essential for the demo video and every phase after.

### 5. Demo Script (demo.py)
Three drones, V-formation, area sweep, RTL. This is the "3 drones, one command" moment the entire GTM strategy depends on. Correctly uses asyncio. Ready for SITL testing today.

### 6. Mission Planner (mission_planner.py)
Line, V-formation, area sweep, orbit patterns. Math is correct. Outputs Waypoint lists compatible with the orchestrator. Four formation types is the right number for the demo -- enough to impress, not so many that quality suffers.

### 7. Flight Logger (flight_logger.py)
Async, buffered JSONL writes, separate files for telemetry/events/commands/errors. Clean design that supports the post-flight analysis workflow. Correctly uses run_in_executor for file I/O.

### 8. Flight Report Generator (flight_report.py)
Reads logger output, generates Markdown reports with per-drone stats, anomaly detection, and recommendations. This directly supports the "iterate and improve" step in the user journey.

### 9. Comms Protocol (COMMS_PROTOCOL.md)
Star topology with SiK radios, MAVLink v2, clear channel assignment scheme. Correctly scoped for Phase 1. Does not over-promise mesh networking.

### 10. Hardware Spec (HARDWARE_SPEC.md)
Thorough BOM with realistic pricing ($195-220 per Class A drone). Assembly checklist, antenna placement, vibration damping, Remote ID compliance. Connection type matrix is excellent. The hardware tier system (Class A-D) is one of the product's strongest design decisions.

### 11. Testing Strategy (TESTING_STRATEGY.md)
Layered approach: unit -> integration -> safety -> performance -> field. SITL setup for N drones is well documented. Coverage targets are realistic. CI pipeline design is appropriate.

### 12. UI Design (UI_DESIGN.md)
The Mission Feed concept is genuinely innovative for this space. "Glove-first" design principles are exactly right for the field operator persona. The responsive breakpoints show real thought about how this will actually be used. The wireframe evolution (v1 through v4) shows iterative design discipline.

### 13. Business Plan (BUSINESS_PLAN.md)
Realistic revenue projections. Honest about defense sales timelines (18-36 months). Good competitive analysis that correctly positions against Shield AI/Anduril (not competing, complementary). The open-core model is well-reasoned. Hardware kit margins are honest (15-25% at startup scale).

### 14. Pressure Test (PRESSURE_TEST.md) and Integration Audit (INTEGRATION_AUDIT.md)
The fact that these exist and are thorough demonstrates engineering discipline. The threading issues, cost discrepancies, and voltage threshold bugs were caught before hardware ordering. This is how good projects are run.

---

## Systems That Are Over-Engineered (simplify or defer)

### 1. IFF Transponder (iff_transponder.py) -- DEFER to Phase 3+
The IFF transponder has a full three-layer architecture (transponder, computer vision, blue force tracking) with HMAC-based challenge-response, replay detection, and a fusion engine. This is Phase 5 functionality written during Phase 0. The stub implementation (returns UNKNOWN) is fine as a placeholder, but the full implementation is ~300+ lines of code that cannot be tested without mesh hardware and CV hardware that does not exist yet.

**Recommendation:** Keep the stub and the data classes. Move the full implementation to a branch or mark it clearly as Phase 3-5 code. Do not invest more time here until the mesh radio hardware is in hand.

### 2. Calibration Engine (calibration_engine.py) -- DEFER to Phase 2+
Auto-calibration that learns from flight data to correct loadout checker predictions. This is a genuinely good idea, but it requires multiple flights of real data to be useful. During Phase 1, the team will have at most a handful of flights. The loadout checker itself is already somewhat over-engineered for a team that will build exactly one drone configuration (Class A with known components).

**Recommendation:** Keep the file but do not prioritize. This becomes valuable at Phase 2-3 when the fleet is heterogeneous and flight data is accumulating.

### 3. Payload Profiles (payload_profiles.py) -- SIMPLIFY
The payload profiles include "RPG Grenade" (400g) and "Small Mortar Round" (600g). While these are realistic for the defense use case, having munitions in the open-source codebase is a liability and optics problem. The ITAR implications are non-trivial -- even listing these as payload profiles could attract regulatory scrutiny before the project is ready for it.

**Recommendation:** Remove the munitions profiles from the open-source core. Keep generic payload profiles (camera, thermal, smoke marker, water bottle for testing). Add munitions profiles only in the commercial defense module, after ITAR counsel has been engaged.

### 4. Loadout Checker (loadout_checker.py) -- SOMEWHAT OVER-ENGINEERED
A "video-game-style build system" with stat bars, compatibility reports, and parts database integration. This is a cool feature that will appeal to the hobbyist community, but it is not on the critical path for the demo or Phase 1. The core functionality (can this drone fly with this loadout?) is needed; the elaborate UI presentation is not.

**Recommendation:** Keep the core calculation logic. Defer the interactive CLI, comparison mode, and stat bar formatting to Phase 2 when it becomes a community engagement tool.

### 5. Security Design (SECURITY_DESIGN.md) -- SCOPE IS CORRECT BUT TIMING IS AGGRESSIVE
The security design covers MAVLink signing, GPS spoofing detection, encrypted comms, anti-jamming, data wipe on capture, and IFF. The phased approach is good, but the document treats some Phase 4-5 features (anti-jamming, data wipe) with the same level of detail as Phase 1 features (MAVLink signing). This creates the impression that all of this needs to be built now.

**Recommendation:** Add a clear "Phase 1 Implementation Scope" section at the top that lists only what needs to be done before the demo: MAVLink v2 signing configuration in the firmware flasher (which already supports it) and basic ground station auth. Everything else is future work.

### 6. Operations Design (OPERATIONS_DESIGN.md) -- PARTIALLY PREMATURE
Battery management, maintenance scheduling, spare parts logistics, field deployment protocols, training, weather integration, fleet analytics, firmware update management. This is a comprehensive operations manual for a fleet that does not exist yet. The battery tracker and maintenance tracker have corresponding code implementations.

**Recommendation:** The battery tracker and maintenance tracker code is premature for Phase 1 (the team will have 3 batteries and 3 drones -- a spreadsheet would suffice). However, these are good Phase 2-3 tools. Keep the code, but do not block Phase 1 on them. The operations design document is valuable for Phase 3+ planning but should be clearly labeled as forward-looking.

---

## Systems That Are Under-Designed (need more work)

### 1. Ground Station UI -- NO CODE EXISTS
The UI design document is excellent. Four iterations of wireframes exist. The system architecture specifies Next.js + Leaflet + Zustand. The API design is thorough. But there is zero frontend code. No `package.json`, no React components, no WebSocket client, no map integration. The demo script outputs to the terminal.

**This is the single largest gap in the project.** The demo video requires a ground station UI showing real-time positions on a map. Without it, the demo is "3 drones controlled from a Python script" -- which is technically impressive but visually uncompelling.

**Recommendation:** The ground station UI is the highest priority for Phase 1 Week 1. Even a minimal version (map with drone markers, connection status panel, mission controls) would transform the demo. The wireframe v4 design is ready to implement.

### 2. SITL Integration -- NOT WIRED UP
The testing strategy document describes how to set up SITL. The demo script has SITL connection strings. But there is no integration test harness, no CI configuration, no automated SITL launcher. The orchestrator has never been tested against SITL because there is no glue code to spin up SITL instances and connect them.

**Recommendation:** Write a `scripts/launch_sitl.sh` that starts N ArduPilot SITL instances with correct system IDs and UDP ports. Write a basic integration test that registers 3 simulated drones, runs preflight, executes a short mission, and verifies telemetry was received. This is Phase 1 Week 1 work.

### 3. FastAPI Backend -- NOT IMPLEMENTED
The API design document specifies 40+ REST endpoints and a WebSocket protocol. The system architecture shows FastAPI on port 8000 and WebSocket on port 8001. But there is no `main.py`, no FastAPI app, no route handlers. The orchestrator currently runs as a standalone Python script (demo.py calls it directly).

**Recommendation:** Implement a minimal FastAPI wrapper around the orchestrator for Phase 1: `GET /api/v1/swarm/status`, `POST /api/v1/swarm/arm`, `POST /api/v1/swarm/takeoff`, `POST /api/v1/swarm/mission`, `WebSocket /ws/v1/stream` for telemetry. This is the bridge between the backend and the frontend.

### 4. Motor Test Protocol and CG Measurement Protocol -- GOOD BUT INCOMPLETE
Both protocols are well-written field guides. However, neither integrates back into the software system. The motor test protocol says "this data feeds directly into the loadout checker" but there is no import path or data format for connecting thrust test results to the parts database.

**Recommendation:** Define a JSON schema for motor test results and add a `dso import-thrust-data` command that ingests test results into the parts database. Low priority -- Phase 2 at earliest.

### 5. Mesh Network Design -- GOOD DESIGN, NO HARDWARE INTEGRATION PATH
The mesh protocol (mesh_protocol.py) implements binary encoding, CRC, neighbor tables, and geographic routing. The design document (MESH_NETWORK_DESIGN.md) specifies ESP32 + SX1276. But the actual hardware-to-software integration path is missing: how does the ESP32 firmware get flashed? How does the mesh module connect to the flight controller? How does the orchestrator discover mesh-connected drones?

**Recommendation:** This is Phase 3 work. For now, document the hardware integration plan as a section in the mesh design doc. No code action needed yet.

---

## Missing From the Vision (gaps in the user journey)

Walking through the complete user journey of a student at Northeastern:

### a. Orders parts from the shopping list -- SUPPORTED
HARDWARE_SPEC.md has a complete BOM with links and pricing. The student knows exactly what to buy.

### b. Assembles 3 drones following the hardware spec -- MOSTLY SUPPORTED
Assembly checklist exists. Antenna placement, vibration damping, and wiring guidance are included. CG measurement protocol exists.

**Gap:** No step-by-step assembly guide with photos. The checklist assumes the student knows how to solder ESCs to a PDB, mount a flight controller, and wire a GPS module. A visual assembly guide (even just annotated photos) would significantly reduce the barrier.

### c. Flashes firmware -- SUPPORTED
`firmware_flasher.py` handles this. CLI interface is clear.

### d. Registers drones in fleet -- SUPPORTED
`fleet_registry.py` handles this. QR code generation for labels is mentioned but `dso fleet print-labels` is not implemented.

**Gap:** The QR label printing command is mentioned in the product spec but does not exist in code. Minor -- a student can hand-write labels.

### e. Runs preflight -- SUPPORTED
`preflight.py` handles this with proper pass/fail reporting.

### f. Runs the demo script -- PARTIALLY SUPPORTED
`demo.py` exists and works against SITL (in theory). But without a ground station UI, the student sees terminal output only. The demo video needs split-screen aerial footage + ground station UI.

**Gap:** No ground station UI. This is the critical missing piece.

### g. Analyzes flight data -- SUPPORTED
`flight_logger.py` + `flight_report.py` provide post-flight analysis with anomaly detection.

### h. Iterates and improves -- SUPPORTED
The calibration engine, loadout checker, and maintenance tracker provide tools for iteration.

### i. Films the demo video -- PARTIALLY SUPPORTED
The demo script produces a coordinated flight. But the video needs a compelling ground station view.

**Gap:** No screen recording integration or "demo mode" that shows the ground station UI at its best. Consider a `dso demo --record` flag that auto-captures the ground station screen.

### j. Eventually builds the ground station UI -- THE STUDENT IS THE ONE BUILDING IT?
The roadmap Phase 1 Week 1 says "Scaffold ground station UI." This is framed as a development task, not a user task. If the student is the sole developer, this is on the critical path and blocks the demo video.

**Gap:** The roadmap assumes the student will build the ground station UI in Week 1. This is a significant development effort (React + Leaflet + WebSocket + state management). Consider whether a simpler approach (e.g., a single-page HTML file with Leaflet and raw WebSocket) could get a map view working in 1-2 days instead of a full Next.js scaffolding effort.

### k. Scales to 8+ drones -- DESIGNED BUT UNTESTED
Phase 3 targets 8 drones. The architecture supports it. Mesh networking begins. But USB hub limitations with star topology at 5-8 drones are a known risk.

**Gap:** No fallback plan documented for if the star topology fails at 5+ drones before mesh is ready. The roadmap acknowledges this risk but the mitigation is "mesh networking" which is Phase 3 work.

### l. Applies to AFWERX/DIU -- SUPPORTED BY DOCUMENTATION
The business plan has a clear government accelerator strategy. The roadmap Phase 5 milestone is "AFWERX or DIU pitch-ready."

**Gap:** No SBIR proposal template or AFWERX application guide. The student will need to figure out the application process independently. Consider adding a `docs/defense-applications/` directory with guidance.

---

## Contradictions Found

### 1. Class A Drone Cost: PRODUCT_SPEC vs. HARDWARE_SPEC
- **PRODUCT_SPEC.md:** Lists Class A at "$120-140" (line 205 area) and "$195-285" (line 694)
- **HARDWARE_SPEC.md:** Lists Class A at "$195-220"
- **ROADMAP.md:** Lists at "~$200 each"
- **Integration Audit:** Already flagged this. PRODUCT_SPEC has not been updated.

**Status:** Known issue, documented in INTEGRATION_AUDIT. Fix is straightforward -- update PRODUCT_SPEC.

### 2. ATAK Integration Phase: PRODUCT_SPEC vs. BUSINESS_PLAN vs. ROADMAP
- **PRODUCT_SPEC.md:** ATAK integration is P3 (v3.0 / Defense-Grade)
- **BUSINESS_PLAN.md competitive table:** "ATAK integration: Planned (Phase 5)"
- **ROADMAP.md:** ATAK integration is in Phase 5

**The product spec says P3, the business plan says Phase 5, and the roadmap says Phase 5.** P3 maps to Phase 5 in the roadmap, so this is internally consistent within the roadmap/business plan, but the "P3" label in the product spec is confusing because someone might read "P3" as "Phase 3."

**Recommendation:** Clarify in the product spec that P3 (priority level 3) maps to Phase 5 (timeline). Or just add "(Phase 5)" next to P3 items.

### 3. Mesh Networking Phase: Moved Earlier but Inconsistently Referenced
- **PRODUCT_SPEC.md:** Mesh networking is P2 (v2.0)
- **ROADMAP.md:** Mesh networking begins in Phase 3, full in Phase 4
- **MESH_NETWORK_DESIGN.md:** Header says "Phase 3 feature"
- **HOME.md:** Says "Phase 3 mesh networking protocol"

**The product spec says P2 but the roadmap says Phase 3.** P2 maps to approximately Phase 4 in the roadmap (v2.0 = competitive advantage = Phase 4). But mesh was pulled forward to Phase 3 per the decision to address star topology scaling limits. The product spec priority labels do not perfectly map to roadmap phases.

**Recommendation:** Add a mapping table in the product spec: P0 = Phase 0-1, P1 = Phase 2-3, P2 = Phase 3-4, P3 = Phase 5-6.

### 4. endurance_min Default -- FIXED
- **swarm.py:** `endurance_min: float = 12.0` (matches HARDWARE_SPEC)
- **Integration Audit:** Flagged this as a FAIL, but the code now shows 12.0

**Status:** This appears to have been fixed. No action needed.

### 5. Battery Voltage Thresholds -- FIXED
- **firmware_flasher.py:** `BATT_LOW_VOLT = 14.8`, `BATT_CRT_VOLT = 14.0` (4S values)
- **Integration Audit:** Flagged original 3S values as a FAIL

**Status:** This appears to have been fixed. No action needed.

---

## Phase Assignment Issues

### Items That Should Be Earlier

#### Ground Station UI -- Currently Phase 1 Week 1, Needs to Be Phase 0 or Pre-Phase 1
The ground station UI is required for the demo video (Phase 1 Week 4). But it is listed as a Phase 1 Week 1 task alongside SITL configuration and MAVLink routing validation. Building a real-time map-based UI with WebSocket telemetry in parallel with SITL integration in a single week is extremely aggressive for a solo founder.

**Recommendation:** Start the ground station UI immediately, even before hardware arrives. A minimal map view connected to SITL via WebSocket can be built in parallel with orchestrator development. Consider this a Phase 0.5 deliverable.

#### MAVLink v2 Signing -- Currently Phase 5, Should Be Phase 1
The GAP_ANALYSIS correctly notes that MAVLink signing is trivial to enable (ArduPilot supports it natively) but the roadmap defers all encryption to Phase 5. MAVLink signing is not encryption -- it is message authentication. It prevents command injection, which is a safety concern even for a demo.

**Recommendation:** Enable MAVLink v2 signing in the firmware flasher as a Phase 1 task. The code is already structured to support it (signing key generation exists). This costs approximately 2 hours of work and eliminates a real safety risk.

#### Basic Operator Authentication -- Currently Phase 5, Should Be Phase 2
The API design document specifies JWT authentication, but the GAP_ANALYSIS notes zero auth code exists. For Phase 2 (operator-ready), having no authentication on the ground station means anyone on the local network can command the swarm.

**Recommendation:** Add basic API key or simple JWT auth in Phase 2. Full RBAC and CAC/PIV can wait for Phase 5.

### Items That Could Be Later

#### Battery Tracker and Maintenance Tracker -- Currently Phase 0 Code, Should Be Phase 2-3
Both have complete implementations but serve a fleet that does not exist yet. A 3-drone fleet in Phase 1 does not need automated battery cycle tracking or maintenance scheduling.

**Recommendation:** The code is written and works. No harm in keeping it. But do not invest more time in these until Phase 3 when the fleet exceeds 5 drones and manual tracking becomes tedious.

#### IFF Transponder -- Currently Phase 0 Code (Stub), Appropriate as Stub
The stub implementation is fine. The full implementation detail should be deferred to Phase 3-5 as designed.

#### Calibration Engine -- Currently Phase 0 Code, Should Be Phase 2+
Requires multiple real flights to be useful. Cannot be meaningfully tested until Phase 2.

### Items Correctly Assigned

- Phase 0 (Foundation): Core orchestrator, mission planner, firmware flasher, fleet registry, preflight -- all correct.
- Phase 1 (Demo MVP): 3-drone coordinated flight, demo video, SITL validation -- all correct.
- Phase 2 (Operator-Ready): Mission builder UI, telemetry dashboard, tablet mode, geofence editor -- all correct.
- Phase 3 (Field-Tested): 8-drone scale, mesh networking early integration, CI/CD, field test protocol -- all correct.
- Phase 4 (Mesh & Autonomy): Full mesh, collision avoidance, autonomous path planning, ground station disconnect resilience -- all correct.
- Phase 5 (Defense-Grade): Encrypted comms, ATAK, IFF, multi-operator, security audit -- all correct.
- Phase 6 (Scale): 50+ drones, hierarchical control, cloud platform, mobile app, IFF v2 CV -- all correct.

---

## Final Verdict

This project has an unusually strong foundation for a pre-hardware startup. The breadth of design documentation is impressive -- 15 design documents, 4 protocols, 15 source files, a thorough pressure test, an integration audit, a gap analysis, and a decision log. The self-critical review process (pressure test identifying its own architecture flaws, integration audit catching cost and voltage discrepancies) demonstrates the kind of intellectual honesty that defense customers value.

### What Works

The product vision is crisp and differentiated: "Kubernetes for drones" is the right elevator pitch. The hardware tier system (Class A-D) is the single most important design decision and it is done well. The open-core business model is sound. The roadmap is phased realistically with honest cost estimates. The competitive positioning is accurate and humble where appropriate.

The Python backend code is clean, well-documented, and addresses the architectural issues raised in the pressure test (asyncio rewrite, state machine, 4S battery thresholds). The supporting systems (flight logger, report generator, battery tracker, maintenance tracker) show forethought about the operational lifecycle that most drone projects ignore.

### What Needs Attention

**The critical path has a gap.** The demo video is the go-to-market catalyst, and it requires a ground station UI that does not exist. Everything else -- the orchestrator, the firmware flasher, the mission planner, the demo script -- feeds into this moment. The UI must be the top priority.

**There is a mild case of gold-plating.** The calibration engine, payload profiles with munitions, and elaborate loadout checker UI are quality work but they are not on the critical path. A solo founder has limited hours. Every hour spent on the calibration engine is an hour not spent on the ground station UI or SITL integration.

**The documentation-to-code ratio is high.** 15 design documents for 15 source files. This is appropriate for Phase 0 (design before build) but the ratio needs to shift heavily toward code in Phase 1. The roadmap's 4-week Phase 1 timeline is achievable only if the founder spends 80%+ of time writing code, not documents.

### The Path Forward

1. **Immediately:** Build a minimal ground station UI (map + drone markers + telemetry panel + mission controls). Even a single-page HTML app with Leaflet and WebSocket would work. Do not over-architect this -- the wireframes are ready, just implement them.

2. **Week 1:** Get SITL running with 3 simulated drones connected to the orchestrator. Validate the full pipeline: demo.py -> swarm.py -> SITL -> telemetry -> ground station UI.

3. **Week 2:** Run the full 3-drone demo in SITL with the ground station recording. If the simulated demo looks compelling, the hardware demo will be a refinement, not a reinvention.

4. **Week 3-4:** Hardware integration, field testing, demo video production.

5. **Remove munitions from payload_profiles.py** before any public release. They add zero value to the open-source core and create regulatory risk.

6. **Enable MAVLink v2 signing in Phase 1.** It is nearly free and eliminates a class of safety concerns.

The project is well-designed, honestly assessed, and ready to transition from planning to execution. The vision is coherent. The strategy is sound. The risk is execution speed -- specifically, building the ground station UI fast enough to produce the demo video that launches the go-to-market flywheel.

---

## Related Documents

- [[PRODUCT_SPEC]] -- Vision and feature requirements
- [[BUSINESS_PLAN]] -- Go-to-market strategy
- [[ROADMAP]] -- Development timeline
- [[PRESSURE_TEST]] -- Independent engineering review
- [[INTEGRATION_AUDIT]] -- Cross-document consistency check
- [[GAP_ANALYSIS]] -- Comprehensive gap analysis
