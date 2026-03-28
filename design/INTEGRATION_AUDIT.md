---
title: Integration Audit Report
type: review
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, audit, quality]
---

# Integration Audit Report

**Date:** 2026-03-26
**Scope:** All design documents, protocol specs, source code, and requirements
**Auditor:** Final pre-hardware integration check
**Verdict:** Multiple inconsistencies found. 8 FAIL items, 9 WARNING items, 14 PASS items. Must resolve FAILs before ordering hardware.

---

## 1. NUMBER CONSISTENCY

### BOM Cost per Drone (Class A)

- HARDWARE_SPEC.md: ~$195-220 per Class A drone
- ROADMAP.md: "~$200 each" (Phase 1 line item), "$585-$660" for 3x Class A
- PRODUCT_SPEC.md: "$120-140" per Class A drone
- PRESSURE_TEST.md: flags the $120 figure as unrealistic, says "$155-225"

FAIL: PRODUCT_SPEC.md says $120-140 per Class A drone. HARDWARE_SPEC.md says ~$195-220. ROADMAP.md says ~$200.

**Files in conflict:** `design/PRODUCT_SPEC.md` (lines 196, 203, 205, 685) vs `protocols/HARDWARE_SPEC.md` (line 45) vs `design/ROADMAP.md` (line 162)
**Fix:** Update PRODUCT_SPEC.md Class A cost to ~$195-220 to match HARDWARE_SPEC.md. The hardware spec was updated after the pressure test to include PDB, wiring, mounting hardware, vibration damping, and Remote ID -- PRODUCT_SPEC.md was not updated to reflect this.

---

### 3-Drone Fleet Total Cost

- HARDWARE_SPEC.md: ~$735-810 total (3x drones + shared equipment), "under $1000"
- ROADMAP.md: $915-$1,160 (includes extra batteries, spare parts, site access), "under $1000 total" as success metric
- BUSINESS_PLAN.md: "3 drones under $1000 total hardware cost" (GTM section)

WARNING: The numbers are technically consistent -- HARDWARE_SPEC's $735-810 is for drones + shared equipment only, while ROADMAP's $915-$1,160 includes spares and extras. However, ROADMAP says "Success metric: 3 drones, coordinated formation, filmed, under $1000 total" on line 170 while the same table (lines 161-168) totals $915-$1,160. The $1000 target is only achievable at the low end with careful sourcing.
**Fix:** Clarify in ROADMAP that the "$1000" success metric refers to core drone hardware + shared equipment (matching HARDWARE_SPEC's $735-810), not the fully loaded cost including spares.

---

### Flight Time

- HARDWARE_SPEC.md: "12-15 min usable flight time" (with 4S 3000mAh battery)
- swarm.py: `endurance_min: float = 10.0` (DroneCapabilities default)
- PRESSURE_TEST.md: References "8-12 min" for 3S 2200mAh (this was the OLD spec, now superseded)

FAIL: swarm.py defaults `endurance_min` to 10.0 minutes, but HARDWARE_SPEC.md says 12-15 min with the recommended 4S 3000mAh battery.

**Files in conflict:** `src/swarm.py` (line 66) vs `protocols/HARDWARE_SPEC.md` (line 16)
**Fix:** Update `swarm.py` DroneCapabilities default to `endurance_min: float = 12.0` to match the hardware spec's lower bound.

---

### Battery Spec

- HARDWARE_SPEC.md: "4S 3000mAh" (recommended)
- firmware_flasher.py: `BATT_LOW_VOLT = 11.1` (3S voltage: 3.7V/cell x 3), `BATT_CRT_VOLT = 10.5` (3S voltage: 3.5V/cell x 3)
- HARDWARE_SPEC.md weight budget: "Battery 4S 3000mAh: ~250g"

FAIL: firmware_flasher.py battery voltage thresholds are configured for 3S LiPo (11.1V/10.5V), but HARDWARE_SPEC.md recommends 4S 3000mAh. A 4S battery has nominal voltage of 14.8V. The correct thresholds for 4S would be: low ~14.8V (3.7V/cell x 4), critical ~14.0V (3.5V/cell x 4).

**Files in conflict:** `src/firmware_flasher.py` (lines 44-45) vs `protocols/HARDWARE_SPEC.md` (line 16)
**Fix:** Update firmware_flasher.py to use 4S voltage thresholds:
- `BATT_LOW_VOLT`: 14.8 (3.7V/cell x 4)
- `BATT_CRT_VOLT`: 14.0 (3.5V/cell x 4)
Add a comment noting these are for 4S. Consider making this configurable by battery cell count.

---

### Phase 3 Drone Target

- ROADMAP.md: "scale to 8 drones" (Phase 3 goal, line 284)
- ROADMAP.md: "8 drones complete a 15-minute coordinated mission" (success criteria, line 357)
- PRESSURE_TEST.md: References "Phase 3 targets 10 drones" (line 104)

WARNING: PRESSURE_TEST.md (line 104) says "Phase 3 targets 10 drones" but the actual ROADMAP.md says 8 drones. The pressure test was likely written against an earlier draft. The current ROADMAP consistently says 8 drones throughout Phase 3.
**Fix:** No action needed on ROADMAP (it is internally consistent at 8 drones). PRESSURE_TEST.md references are advisory and were written against a prior draft -- note this discrepancy but no code/spec fix required.

---

### Revenue Year 5

- BUSINESS_PLAN.md: "$8M - $15M" (line 140 and line 470)

PASS: Year 5 revenue of $8-15M is consistent across both mentions in BUSINESS_PLAN.md.

---

## 2. CODE-TO-SPEC ALIGNMENT

### swarm.py Uses asyncio

- SYSTEM_ARCHITECTURE.md section 2.1 describes swarm.py evolution and the PRESSURE_TEST.md recommended asyncio
- swarm.py: Uses `asyncio` throughout -- all public methods are `async`, uses `asyncio.Lock`, `asyncio.Task`, `asyncio.create_task`

PASS: swarm.py has been rewritten to use asyncio as recommended. The state machine uses per-drone asyncio locks. The threading concerns from the pressure test have been addressed.

---

### firmware_flasher.py Parameters

- `AVD_ENABLE = 1`: Present (line 60)
- `DID_ENABLE = 1`: Present (line 66)
- Battery voltages: 11.1V / 10.5V -- configured for 3S (see FAIL above under Battery Spec)

PASS (partial): AVD_ENABLE and DID_ENABLE are both present and correctly set to 1. Battery voltages are a FAIL (covered above).

---

### preflight.py Checks

The spec (COMMS_PROTOCOL.md, PRODUCT_SPEC.md P0.5) and pressure test fixes call for 7 checks. preflight.py implements:

1. COMMS (check_comms) -- line 48
2. GPS (check_gps) -- line 59
3. BATTERY (check_battery) -- line 73
4. COMPASS (check_compass) -- line 87
5. FAILSAFE (check_failsafes) -- line 140
6. REMOTE_ID (check_remote_id) -- line 102
7. VIBRATION (check_vibration) -- line 118

PASS: All 7 checks are implemented. This matches the pressure test recommendations (Remote ID and Vibration were added as recommended).

---

### fleet_registry.py Hardware Capability Classes

- Classes defined: A (Basic), B (Sensor), C (Compute), D (Payload) -- lines 22-30
- Matches HARDWARE_SPEC.md class definitions
- swarm.py DroneCapabilities has `hw_class` field with values A/B/C/D

PASS: Hardware capability classes A/B/C/D are consistent between fleet_registry.py, swarm.py, and HARDWARE_SPEC.md.

---

### DroneStatus Enum Mismatch (Code vs API Spec)

- swarm.py DroneStatus: `DISCONNECTED`, `CONNECTED`, `ARMED`, `AIRBORNE`, `RETURNING`, `LANDED`, `LOST`
- API_DESIGN.md DroneStatus enum: `offline`, `idle`, `preflight`, `armed`, `taking_off`, `in_flight`, `returning`, `landing`, `landed`, `error`

FAIL: The DroneStatus values in the code and API spec are completely different. The code has 7 states; the API spec has 10 states. Key mismatches:
- Code `DISCONNECTED` vs API `offline`
- Code `CONNECTED` vs API `idle` (no equivalent)
- Code has no `preflight`, `taking_off`, or `landing` states
- Code `AIRBORNE` vs API `in_flight`
- Code `LOST` vs API `error`
- API has `taking_off` and `landing` as transient states that don't exist in code

**Files in conflict:** `src/swarm.py` (lines 26-33) vs `design/API_DESIGN.md` (line 343)
**Fix:** Either expand swarm.py's state machine to include the API's additional states (preflight, taking_off, landing), or simplify the API spec to match the code. Recommended: add the transient states to the code since they represent real operational phases.

---

### Formation Types Mismatch

- mission_planner.py: `line_formation`, `v_formation`, `area_sweep`, `orbit_point`
- API_DESIGN.md FormationType enum: `line`, `v_shape`, `diamond`, `grid`, `circle`, `custom`

WARNING: The code has `orbit_point` but API says `circle`; code has `area_sweep` but API says `grid`. The API includes `diamond` and `custom` formations not implemented in code. These are naming mismatches and missing implementations.
**Fix:** Align naming. Rename code functions or API enum values so they match. Add `diamond` and `custom` to the code as stubs or remove from the API spec for MVP.

---

## 3. DEMO.PY COMPATIBILITY

FAIL: demo.py was written before the asyncio rewrite and calls synchronous methods that are now async. Specific breakages:

1. **Line 49**: `swarm.connect_all()` -- now `async`, returns a coroutine. Calling it synchronously does nothing.
2. **Line 61**: `swarm.takeoff_all(FLIGHT_ALTITUDE)` -- now `async`, same problem.
3. **Line 73**: `swarm.assign_mission(drone_id, waypoints)` -- now `async`.
4. **Line 74**: `swarm.execute_missions()` -- now `async`.
5. **Lines 88-90**: Same pattern repeated for Phase 3.
6. **Line 96**: `swarm.rtl_all()` -- now `async`.
7. **Line 100**: `swarm.shutdown()` -- now `async`.
8. **Line 50**: `swarm.status_report()` -- this one is still sync (returns str), so it works.

**Files in conflict:** `src/demo.py` (entire main() function) vs `src/swarm.py` (all public methods now async)
**Fix:** Rewrite demo.py to use `asyncio.run()` with an async main function:
```python
import asyncio

async def main():
    swarm = SwarmOrchestrator()
    # ... all calls now use await ...
    await swarm.connect_all()
    await swarm.takeoff_all(FLIGHT_ALTITUDE)
    # etc.

if __name__ == "__main__":
    asyncio.run(main())
```
Also replace `time.sleep()` calls with `await asyncio.sleep()`.

---

## 4. API-TO-UI ALIGNMENT

### UI Actions vs API Endpoints

| UI Action (UI_DESIGN.md) | API Endpoint (API_DESIGN.md) | Status |
|---|---|---|
| Takeoff All (Bottom Bar) | `POST /fleets/{id}/swarm/takeoff` | PASS |
| RTL All (Bottom Bar) | `POST /fleets/{id}/swarm/rtl` | PASS |
| Land All (Bottom Bar) | `POST /fleets/{id}/swarm/land` | PASS |
| Pause Mission (Bottom Bar) | `POST /fleets/{id}/swarm/pause` | PASS |
| Resume Mission (Bottom Bar) | `POST /fleets/{id}/swarm/resume` | PASS |
| E-LAND (Emergency Land button) | **No dedicated endpoint** | FAIL |
| KILL MOTORS (Emergency Kill button) | `POST /fleets/{id}/swarm/emergency-stop` | PASS |
| Go To (per-drone action) | `POST /fleets/{id}/swarm/goto` | PASS |
| RTL (per-drone action) | `POST /fleets/{id}/swarm/rtl` (with drone_ids) | PASS |
| Hold Position (per-drone action) | **No dedicated endpoint** | WARNING |
| Set Role (per-drone dropdown) | Fleet management endpoints exist | PASS |
| Set Formation (Mission Planner) | `POST /fleets/{id}/swarm/formation` | PASS |
| Run Preflight (Pre-Flight screen) | `POST /fleets/{id}/preflight` | PASS |
| Add Drone (Fleet Manager) | Fleet management CRUD exists | PASS |
| Mission Replay (Replay screen) | `POST /fleets/{id}/recordings/{id}/replay` | PASS |
| Geofence Editor | `POST/GET/PATCH/DELETE /fleets/{id}/geofences` | PASS |

FAIL: The UI defines two emergency modes -- "E-LAND" (controlled descent via `emergency_land()`) and "KILL MOTORS" (force disarm via `emergency_stop()`). The API only has `POST /fleets/{id}/swarm/emergency-stop` which maps to the motor kill. There is no `emergency-land` API endpoint.

**Files in conflict:** `design/UI_DESIGN.md` (lines 228-236) vs `design/API_DESIGN.md` (section 7.1.5)
**Fix:** Add a `POST /api/v1/fleets/{fleet_id}/swarm/emergency-land` endpoint that commands all drones to LAND mode (controlled descent). Keep the existing `emergency-stop` as the motor kill. Both should bypass the command lock.

WARNING: "Hold Position" is shown as a per-drone action button in the UI (line 398 of UI_DESIGN.md) but there is no explicit "hold position" or "loiter" API endpoint.
**Fix:** Add a `POST /api/v1/fleets/{fleet_id}/drones/{drone_id}/hold` endpoint or document that "hold position" is implemented via `goto` with the drone's current position.

---

## 5. FEATURE COVERAGE -- P0 Features in PRODUCT_SPEC.md

| P0 Feature | Designed In | Implemented In Code | Status |
|---|---|---|---|
| P0.1 Multi-Drone Connection & Telemetry | SYSTEM_ARCHITECTURE, COMMS_PROTOCOL | swarm.py | PASS |
| P0.2 Formation Flight | SYSTEM_ARCHITECTURE (Formation Controller) | mission_planner.py | PASS |
| P0.3 Firmware Flasher | HARDWARE_SPEC | firmware_flasher.py | PASS |
| P0.4 Fleet Registry with QR | HARDWARE_SPEC | fleet_registry.py, firmware_flasher.py | PASS |
| P0.5 Pre-Flight Checks | TESTING_STRATEGY | preflight.py | PASS |
| P0.6 Failsafe: Auto-RTL | COMMS_PROTOCOL, HARDWARE_SPEC | swarm.py, firmware_flasher.py | PASS |
| P0.7 Dynamic Replanning | SYSTEM_ARCHITECTURE | swarm.py (replan_on_loss) | PASS |
| P0.8 Ground Station Map UI | UI_DESIGN, SYSTEM_ARCHITECTURE | Not yet built (design only) | PASS (design exists) |
| P0.9 Mission Logging & Replay | API_DESIGN, UI_DESIGN | Not yet built (design only) | PASS (design exists) |

PASS: Every P0 feature in PRODUCT_SPEC.md is designed in at least one other document and either implemented in code or has a complete design specification.

---

## 6. MISSING CROSS-REFERENCES

### SYSTEM_ARCHITECTURE.md References Threaded Model but Code is Async

WARNING: SYSTEM_ARCHITECTURE.md section 2.1 (line 143) still describes swarm.py as having "Background telemetry loop (10Hz, threaded)" and "Mission execution (threaded, one thread per drone)". The actual code has been rewritten to use asyncio. The TelemetryAggregator code sketch in SYSTEM_ARCHITECTURE.md (line 218) still uses `threading.Thread`.

**Files affected:** `design/SYSTEM_ARCHITECTURE.md` (lines 143-144, 215-235)
**Fix:** Update SYSTEM_ARCHITECTURE.md to reflect the asyncio rewrite. Replace threading references with asyncio equivalents.

---

### PRESSURE_TEST.md Battery Voltages Are Outdated

WARNING: PRESSURE_TEST.md section 3.4 (lines 188-189) says the firmware flasher sets `BATT_LOW_VOLT = 10.5` and `BATT_CRT_VOLT = 9.6`. The actual firmware_flasher.py now has `BATT_LOW_VOLT = 11.1` and `BATT_CRT_VOLT = 10.5`. The pressure test findings have been partially addressed (voltages raised) but the pressure test document itself was not updated to note this.

**Fix:** PRESSURE_TEST.md is a review document and does not need to be kept in sync -- but add a note at the top of the pressure test indicating which items have been addressed. Consider adding a "Resolution" column to the issues table.

---

### RTL Altitude Staggering

- PRESSURE_TEST.md (section 3.3) flagged that firmware_flasher.py sets the same RTL_ALT for all drones
- swarm.py now implements RTL altitude staggering in `return_to_launch()` (lines 293-313): base 15m + 5m per drone index
- firmware_flasher.py still sets a uniform `RTL_ALT = 1500` (15m) for all drones

PASS: The staggering concern has been addressed at the orchestrator level (swarm.py dynamically sets per-drone RTL_ALT before switching to RTL mode). The firmware default of 15m is a reasonable base that gets overridden at runtime.

---

## 7. REQUIREMENTS.TXT COMPLETENESS

Current contents of `requirements.txt`:
```
pymavlink>=2.4.41
dronekit>=2.9.2
asyncio-dgram>=2.2.0
```

FAIL: requirements.txt has issues:

1. **`dronekit` is listed but never imported.** No source file in `src/` imports dronekit. It is a dead dependency. dronekit is also largely incompatible with asyncio and has been superseded by direct pymavlink usage (which the code already uses).

2. **Missing optional dependencies used in code:**
   - `qrcode` -- imported in firmware_flasher.py (line 165) for QR code generation
   - `opencv-python` (`cv2`) -- imported in fleet_registry.py (line 87) for QR scanning
   - `pyzbar` -- imported in fleet_registry.py (line 88) for QR decoding

3. **`asyncio-dgram` is listed but never imported.** No source file imports this package.

4. **Missing dependencies for the API server** described in SYSTEM_ARCHITECTURE.md:
   - `fastapi` -- the system architecture specifies FastAPI as the REST API framework
   - `uvicorn` -- the ASGI server for FastAPI
   - `websockets` or equivalent -- for WebSocket support

**Fix:** Update requirements.txt:
```
pymavlink>=2.4.41
# Optional (QR code features):
# qrcode[pil]>=7.0
# opencv-python>=4.8.0
# pyzbar>=0.1.9
```
Remove `dronekit` and `asyncio-dgram` (unused). Add `fastapi`, `uvicorn`, and `websockets` when the API server is built. Add optional deps as comments or in a `requirements-optional.txt`.

---

## 8. SHOPPING LIST COMPLETENESS (HARDWARE_SPEC.md)

Can someone read HARDWARE_SPEC.md and know EXACTLY what to buy for a 3-drone fleet?

### Required Components Table (line 9-22)

| Component | Listed? | Quantity Clear? | Price Listed? |
|---|---|---|---|
| Flight controller (SpeedyBee F405 V4) | Yes | Per drone (implicit) | ~$35 |
| GPS (BN-880) | Yes | Per drone | ~$12 |
| Telemetry radio (SiK pair) | Yes | Per pair | ~$15 |
| Frame (F450 clone) | Yes | Per drone | ~$15 |
| Motors + ESCs (2212 920KV + 30A) | Yes | "4x" stated | ~$50-60 total |
| Battery (4S 3000mAh) | Yes | Per drone | ~$22 |
| Propellers (1045) | Yes | Per drone | ~$5/5pairs |
| PDB | Yes | Per drone | ~$8 |
| XT60 connectors + wires + solder | Yes | Per drone | ~$8 |
| Mounting hardware | Yes | Per drone | ~$5 |
| Vibration damping | Yes | Per drone | ~$3 |
| Remote ID | Yes | Per drone | ~$35 (standalone) or $0 (built-in) |

### Shared Equipment Table (line 122-131)

| Item | Listed? | Price? |
|---|---|---|
| LiPo charger | Yes | ~$40 |
| RC transmitter | Yes | ~$60 |
| Powered USB hub | Yes | ~$15 |
| Soldering iron + supplies | Yes | ~$25 |
| Prop balancer | Yes | ~$10 |

### Total System Cost Table (line 133-141)

- 3x Class A: ~$585-660
- Shared equipment: ~$150
- Total: ~$735-810

PASS: HARDWARE_SPEC.md is comprehensive. Every component needed to build a 3-drone fleet is listed with approximate price and purpose. The shared equipment section covers one-time costs. The total is clearly stated. Someone could take this document and create a shopping cart.

WARNING: Quantities for a 3-drone fleet are not explicitly stated as "buy 3x of each per-drone item." The table says "per drone" implicitly but a literal shopping list with "buy X of these" for a 3-drone fleet would be clearer.
**Fix:** Add a "3-Drone Shopping List" section with exact quantities (e.g., "3x SpeedyBee F405 V4, 3x BN-880 GPS, 3x SiK radio pairs (6 radios total)...").

---

## Summary

### FAIL Items (Must Fix Before Hardware Order)

| # | Issue | Severity | Files |
|---|---|---|---|
| 1 | PRODUCT_SPEC.md Class A cost ($120-140) contradicts HARDWARE_SPEC.md (~$195-220) | HIGH | PRODUCT_SPEC.md, HARDWARE_SPEC.md |
| 2 | firmware_flasher.py battery voltages are for 3S but hardware spec says 4S | CRITICAL | firmware_flasher.py, HARDWARE_SPEC.md |
| 3 | swarm.py endurance_min default (10 min) does not match spec (12-15 min) | LOW | swarm.py, HARDWARE_SPEC.md |
| 4 | DroneStatus enum in code vs API spec are completely different | HIGH | swarm.py, API_DESIGN.md |
| 5 | demo.py calls sync methods on async SwarmOrchestrator -- will not run | CRITICAL | demo.py, swarm.py |
| 6 | No emergency-land API endpoint despite UI requiring it | HIGH | API_DESIGN.md, UI_DESIGN.md |
| 7 | requirements.txt lists unused deps (dronekit, asyncio-dgram), missing actual deps | MEDIUM | requirements.txt |
| 8 | SYSTEM_ARCHITECTURE.md still describes threaded model, code is asyncio | MEDIUM | SYSTEM_ARCHITECTURE.md, swarm.py |

### WARNING Items (Should Fix, Not Blocking)

| # | Issue | Files |
|---|---|---|
| 1 | ROADMAP "$1000 success metric" is ambiguous vs actual $915-1160 budget | ROADMAP.md |
| 2 | PRESSURE_TEST.md references "10 drones" for Phase 3, ROADMAP says 8 | PRESSURE_TEST.md, ROADMAP.md |
| 3 | Formation type names mismatch between code and API spec | mission_planner.py, API_DESIGN.md |
| 4 | "Hold Position" UI action has no dedicated API endpoint | UI_DESIGN.md, API_DESIGN.md |
| 5 | PRESSURE_TEST.md battery voltage findings are outdated (partially fixed) | PRESSURE_TEST.md |
| 6 | HARDWARE_SPEC.md lacks explicit 3-drone shopping list with quantities | HARDWARE_SPEC.md |
| 7 | SYSTEM_ARCHITECTURE.md TelemetryAggregator code sketch uses threading | SYSTEM_ARCHITECTURE.md |
| 8 | swarm.py DroneCapabilities default max_speed_ms is 5.0 but firmware sets WPNAV_SPEED=500 (5 m/s) -- consistent but very conservative | swarm.py, firmware_flasher.py |
| 9 | firmware_flasher.py comments say "3S" on voltage lines but if battery is 4S per spec, comments are misleading | firmware_flasher.py |

### PASS Items

| # | Item |
|---|---|
| 1 | swarm.py correctly uses asyncio with per-drone locks and proper state machine |
| 2 | firmware_flasher.py has AVD_ENABLE=1 and DID_ENABLE=1 |
| 3 | preflight.py has all 7 checks (COMMS, GPS, BATTERY, COMPASS, FAILSAFE, REMOTE_ID, VIBRATION) |
| 4 | fleet_registry.py has hardware classes A/B/C/D matching specs |
| 5 | Year 5 revenue ($8-15M) is consistent across BUSINESS_PLAN.md |
| 6 | Phase 3 target (8 drones) is consistent within ROADMAP.md |
| 7 | All P0 features from PRODUCT_SPEC.md are designed in at least one other document |
| 8 | Every major UI action has a corresponding API endpoint (except emergency-land and hold) |
| 9 | RTL altitude staggering is implemented in swarm.py (addresses pressure test finding) |
| 10 | Emergency stop has two-mode design (E-LAND + KILL MOTORS) in UI, addressing pressure test |
| 11 | HARDWARE_SPEC.md includes all components needed for a 3-drone fleet with prices |
| 12 | Remote ID is in hardware BOM, firmware params, and preflight checks |
| 13 | Vibration damping is in hardware BOM and preflight checks |
| 14 | COMMS_PROTOCOL.md and swarm.py state machines match |

---

## Priority Fix Order (Pre-Hardware)

1. **firmware_flasher.py battery voltages** -- CRITICAL. Wrong cell count = LiPo damage or fires. Fix voltages for 4S.
2. **demo.py async compatibility** -- CRITICAL. The demo script will crash on launch. Rewrite with asyncio.run().
3. **API_DESIGN.md emergency-land endpoint** -- HIGH. Safety-critical gap. Add the endpoint.
4. **DroneStatus enum alignment** -- HIGH. API and code must agree on states before UI development begins.
5. **PRODUCT_SPEC.md cost figures** -- HIGH. Update to match HARDWARE_SPEC.md before anyone budgets from it.
6. **requirements.txt cleanup** -- MEDIUM. Remove dead deps, document real ones.
7. **SYSTEM_ARCHITECTURE.md threading references** -- MEDIUM. Update to reflect asyncio reality.
8. **swarm.py endurance_min default** -- LOW. Cosmetic but should match spec.

---

## Related Documents

- [[PRODUCT_SPEC]] -- Spec audited for cost consistency
- [[SYSTEM_ARCHITECTURE]] -- Architecture audited for code alignment
- [[API_DESIGN]] -- API audited against UI actions
- [[UI_DESIGN]] -- UI audited against API endpoints
- [[HARDWARE_SPEC]] -- Hardware spec audited for BOM completeness
- [[COMMS_PROTOCOL]] -- Protocol audited against code state machine
- [[PRESSURE_TEST]] -- Earlier review whose fixes were verified here
- [[DECISION_LOG]] -- Decisions referenced in audit findings
