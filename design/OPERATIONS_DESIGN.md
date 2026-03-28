---
title: Operations Design
type: design
status: active
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, operations, maintenance, logistics, batteries, training]
---

# Drone Swarm Orchestrator -- Operations Design

**Version:** 1.0
**Last Updated:** 2026-03-26
**Status:** Technical Blueprint

> Covers the full operational lifecycle: battery management, maintenance scheduling, spare parts logistics, field deployment, operator training, weather integration, fleet analytics, and firmware update management.

## Related Documents

- [[SYSTEM_ARCHITECTURE]] -- Module breakdown and data flow
- [[PRODUCT_SPEC]] -- Feature prioritization (P0-P3)
- [[ROADMAP]] -- Phased development plan
- [[HARDWARE_SPEC]] -- Bill of materials and assembly
- [[COMMS_PROTOCOL]] -- MAVLink communication and radio configuration
- [[TESTING_STRATEGY]] -- SITL and field testing approach
- [[GAP_ANALYSIS]] -- Comprehensive gap analysis identifying these operational needs
- [[INTEGRATION_AUDIT]] -- Cross-document consistency audit

---

## Table of Contents

1. [Battery Management System](#a-battery-management-system)
2. [Maintenance Scheduling](#b-maintenance-scheduling)
3. [Spare Parts Kit](#c-spare-parts-kit)
4. [Drone Transport & Field Setup](#d-drone-transport--field-setup)
5. [Training & Simulation Mode](#e-training--simulation-mode)
6. [Weather Integration](#f-weather-integration)
7. [Fleet Analytics Dashboard](#g-fleet-analytics-dashboard)
8. [Firmware Update Management](#h-firmware-update-management)

---

## A. Battery Management System

LiPo batteries are the highest-maintenance, highest-risk component in any drone fleet. Mismanaged batteries cause fires, mid-air failures, and degraded flight times. This system tracks every battery from purchase to retirement.

### Per-Battery Tracking

Each battery gets a **unique ID** (e.g., `B001`, `B002`), physically labeled with a sticker or engraving. The system tracks:

| Metric | Description | Update Trigger |
|--------|-------------|----------------|
| `cycle_count` | Total charge/discharge cycles | After each flight |
| `total_mah_discharged` | Cumulative mAh discharged across all flights | After each flight |
| `last_internal_resistance_mohm` | Internal resistance trend (measured periodically) | Manual entry or charger data |
| `max_temp_c` | Highest temperature ever recorded during flight | After each flight |
| `health_pct` | Estimated remaining capacity vs. rated | Calculated from cycle count |
| `storage_voltage_compliance` | Whether battery was stored at correct voltage | Periodic check |
| `status` | `active`, `storage`, or `retired` | Manual or automatic |

### Battery Registry

Each battery is stored as `batteries/{battery_id}.json`:

```json
{
  "battery_id": "B001",
  "manufacturer": "Tattu",
  "model": "4S3000",
  "cells": 4,
  "capacity_mah": 3000,
  "purchase_date": "2026-03-15",
  "cycle_count": 47,
  "total_mah_discharged": 112800,
  "max_temp_c": 44.2,
  "last_internal_resistance_mohm": 12.3,
  "health_pct": 92.1,
  "status": "active",
  "notes": ["2026-03-20: Passed visual inspection"]
}
```

### Flight Integration

After each flight, `flight_report.py` updates the battery record:
1. Increment `cycle_count` by 1.
2. Add mAh used to `total_mah_discharged`.
3. Update `max_temp_c` if this flight's max exceeded the record.
4. Recalculate `health_pct` using the degradation model.

### Degradation Model

LiPo capacity loss follows an approximately linear curve for the first 200-300 cycles:

```
estimated_health_pct = max(0, 100 - (cycle_count / 300) * 20)
```

This gives ~80% health at 300 cycles. The model is conservative; real degradation depends on discharge rate, temperature, and storage practices.

**Alert thresholds:**
- **Warning** at 85% health: "Battery B001 showing wear -- plan replacement"
- **Alert** at 80% health: "Battery B001 should be retired"
- **Critical** at 75% health or 300+ cycles: "Battery B001 MUST be retired"

### Safety Alerts

**Voltage sag detection (puffing indicator):**
If voltage sag under load increases >30% from the battery's baseline, the battery may be swelling internally. This is a fire risk.

```
baseline_sag = (max_voltage - min_voltage) from first 10 flights
current_sag = (max_voltage - min_voltage) from latest flight
if current_sag > baseline_sag * 1.3:
    ALERT: "Battery {id} shows increased voltage sag -- inspect for puffing"
```

**High temperature events:**
- Warning at 50 degrees C.
- Alert at 60 degrees C: "Battery {id} overheating -- land immediately."
- Any event above 60 degrees C flags the battery for physical inspection.

### Retirement Criteria

A battery is automatically flagged for retirement if **any** of:
- Cycle count exceeds 300.
- Estimated health drops below 80%.
- Any puffing event detected (voltage sag increase >30%).
- Physical inspection reveals swelling, damage, or deformation.

### Storage Protocol

- **Storage voltage:** 3.8V per cell (storage charge mode on charger).
- **Never** leave fully charged (4.2V/cell) for more than 24 hours.
- **Never** leave fully discharged (<3.3V/cell) -- causes irreversible damage.
- **Temperature:** Store between 15-25 degrees C, away from flammable materials.
- **Fireproof bag:** Always store in LiPo-safe bags.

### Implementation

See `src/battery_tracker.py` for the `BatteryTracker` class and CLI.

---

## B. Maintenance Scheduling

### Per-Drone Tracking

Each drone's maintenance state is stored in `maintenance/{drone_id}.json`:

| Metric | Description |
|--------|-------------|
| `total_flight_hours` | Cumulative flight time |
| `motor_hours` | Per-motor hours (4 motors for a quad) |
| `prop_hours` | Hours on current props (reset on replacement) |
| `flights_since_inspection` | Counter reset after visual inspection |
| `hard_landings` | Count of hard landings / crashes |
| `last_compass_cal` | Date of last compass calibration |
| `last_accel_cal` | Date of last accelerometer calibration |
| `last_firmware_update` | Date and version of last firmware flash |
| `maintenance_log` | Timestamped list of all maintenance actions |

### Maintenance Intervals

| Interval | Action | Details |
|----------|--------|---------|
| Every 5 flights | Visual inspection | Frame cracks, loose screws, prop damage, wiring |
| Every 10 hours | Prop replacement | Props are consumable; replace every 10-20 hours depending on material |
| Every 10 hours | Motor bearing check | Listen for grinding, feel for play in shaft |
| Every 25 hours | ESC inspection | Check for burn marks, loose solder joints, capacitor swelling |
| Every 25 hours | Wiring check | Inspect all connectors, especially XT60 and signal wires |
| Every 50 hours | Motor replacement consideration | Measure motor temperature under load; replace if running hot |
| After any crash | Full inspection | Complete teardown inspection before next flight |
| Every 30 days | Compass calibration | Even without flights, magnetic environment can shift |
| Every 30 days | Accelerometer calibration | Drift correction |

### Preflight Integration

The preflight check queries `MaintenanceTracker.check_flight_readiness()` and warns the operator:

```
[PREFLIGHT] ALPHA: 12.3 hours on props -- replacement recommended (limit: 10h)
[PREFLIGHT] BRAVO: 7 flights since last visual inspection -- inspect before flight
[PREFLIGHT] CHARLIE: Compass calibration overdue (last: 2026-02-15)
```

Warnings do not block flight (operator override) but are logged. Critical items (post-crash inspection incomplete) block flight.

### Implementation

See `src/maintenance_tracker.py` for the `MaintenanceTracker` class and CLI.

---

## C. Spare Parts Kit

### 3-Drone Fleet Kit (~$80)

| Item | Qty | Rationale |
|------|-----|-----------|
| Props (full set = 4 CW + 4 CCW) | 2 sets (16 props) | Most frequent replacement; carry 2 full sets minimum |
| Motors (matched to frame) | 2 | Most common mechanical failure; one spare plus one buffer |
| ESC (matched to motor rating) | 1 | Less common failure but catastrophic when it happens |
| Batteries (matched to fleet spec) | 2 | One charging while one flies; spare for hot-swap |
| XT60 connectors + 14AWG wire (1m) | 4 connectors + wire | Field repair of power connections |
| Zip ties (assorted) | 20+ | Universal field fix |
| Foam tape (3M VHB) | 1 roll | Vibration dampening, securing components |
| Screws (M3 assorted lengths) | 20+ | Frame assembly, motor mounting |
| Prop balancer | 1 | Balanced props reduce vibration and extend motor life |
| Multimeter | 1 | Voltage checks, continuity testing, ESC debugging |
| Small screwdriver set (hex + Phillips) | 1 | Frame and motor screws |
| Threadlocker (blue, medium strength) | 1 | Prevents motor screws from vibrating loose |
| Electrical tape | 1 roll | Insulation, temporary wire management |
| Spare prop nuts / prop adapters | 4 | Easy to lose in the field |

**Estimated total cost:** ~$80 (excludes batteries, which are fleet-specific).

### 10-Drone Field Deployment Kit

Everything in the 3-drone kit, scaled up, plus:

| Item | Qty | Rationale |
|------|-----|-----------|
| Props | 5 full sets | Higher replacement rate with more drones |
| Motors | 5 | ~1 per 2 drones |
| ESCs | 3 | Higher probability of failure with larger fleet |
| Batteries | 6 extra | Hot-swap rotation across 10 drones |
| Field soldering kit | 1 | Soldering iron (TS100 or similar), solder, flux, helping hands |
| Heat shrink tubing (assorted) | 1 pack | Proper solder joint protection |
| Laptop with all software pre-installed | 1 | Ground station, firmware flasher, fleet tools, SITL |
| Spare SiK radio | 2 | Radio failure means total loss of comms |
| Spare GPS module | 1 | GPS failures are uncommon but unrecoverable in field |
| Carrying case for spares | 1 | Organized compartments, clearly labeled |
| Battery charger (multi-port) | 1 | Charge 4+ batteries simultaneously |
| Generator or large power bank | 1 | Field power for charger and laptop |

**Estimated total cost:** ~$400-600 (excludes batteries and laptop).

---

## D. Drone Transport & Field Setup

### Transport Case Design (3 Drones)

**Option A: Hard case (Pelican 1600 or equivalent)**
- Foam cutouts for 3 drone frames (props removed).
- Separate foam compartment for batteries (never stored attached to drones during transport).
- Compartment for radios, antennas, and ground station laptop.
- Side pocket or tray for tools and spare parts kit.
- Checklist laminated and affixed inside the case lid.

**Option B: Padded backpack (for foot-mobile operations)**
- Internal dividers for 2-3 drones.
- Battery pouch (fireproof lining).
- External attachment points for antenna mast.
- Weight target: <15 kg fully loaded.

### Transport Rules

1. **Props always removed** during transport -- prevents damage and accidental spin-up.
2. **Batteries stored separately** in fireproof LiPo bags, at storage voltage (3.8V/cell).
3. **Radios powered off** to prevent interference.
4. **Checklist verified** before closing case: all items present, batteries at storage voltage, props removed.

### Field Setup Procedure

| Step | Action | Time (3 drones) |
|------|--------|-----------------|
| 1 | Unpack and visual inspect all drones | 5 min |
| 2 | Attach props (verify CW/CCW, check torque) | 3 min/drone = 9 min |
| 3 | Install batteries (verify connector, secure with strap) | 1 min/drone = 3 min |
| 4 | Power on + wait for boot sequence and GPS lock | 2 min/drone = 6 min (parallel) |
| 5 | Connect ground station to all drones | 1 min |
| 6 | Run preflight checks (`python preflight.py`) | 3 min |
| **Total** | **Case-open to flight-ready** | **~20 min** |

### Field Teardown Procedure

| Step | Action | Time |
|------|--------|------|
| 1 | Land all drones, disarm | 2 min |
| 2 | Run post-flight report (`python flight_report.py`) | 1 min |
| 3 | Remove batteries, place in LiPo bags | 2 min |
| 4 | Remove props, inspect for damage | 5 min |
| 5 | Visual inspection of frames and motors | 3 min |
| 6 | Pack into case using foam cutouts | 5 min |
| 7 | Verify checklist on case lid | 1 min |
| **Total** | **Flight-end to packed** | **~20 min** |

---

## E. Training & Simulation Mode

### Simulation Architecture

The simulation mode uses ArduPilot SITL (Software In The Loop) to create virtual drones that behave identically to real hardware from the ground station's perspective.

```
                    ┌──────────────┐
                    │  Ground      │
                    │  Station UI  │
                    └──────┬───────┘
                           │ Same WebSocket / MAVLink
                    ┌──────┴───────┐
                    │  swarm.py    │
                    │  (orchestr.) │
                    └──────┬───────┘
                           │ MAVLink (TCP/UDP localhost)
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴──────┐ ┌──┴───────┐
        │ SITL #1   │ │ SITL #2  │ │ SITL #3  │
        │ (alpha)   │ │ (bravo)  │ │ (charlie)│
        └───────────┘ └──────────┘ └──────────┘
```

- Same ground station UI, same commands, same Mission Feed.
- Operator practices mission planning, monitoring, and emergency procedures.
- No drones, radios, or batteries needed -- runs entirely on a laptop.
- SITL instances communicate via localhost TCP/UDP ports.

### Launching Simulation

```bash
# Start 3 SITL instances (ArduCopter)
sim_vehicle.py -v ArduCopter --instance 0 -I 0 --sysid 1 &
sim_vehicle.py -v ArduCopter --instance 1 -I 1 --sysid 2 &
sim_vehicle.py -v ArduCopter --instance 2 -I 2 --sysid 3 &

# Connect ground station to all three
python swarm.py --sim
```

### Training Program Levels

| Level | Name | Environment | Skills Practiced |
|-------|------|-------------|------------------|
| 1 | Simulator Basics | SITL | Start SITL, connect ground station, explore UI, read telemetry |
| 2 | Single Drone | SITL | Takeoff, waypoint navigation, loiter, RTL, land |
| 3 | Multi-Drone | SITL | 3-drone formation, spacing, coordinated waypoints |
| 4 | Emergency Procedures | SITL | Simulated failures: GPS loss, battery critical, comms loss, motor failure |
| 5 | Real Hardware: Single | 1 real drone | Single drone hover test, manual override, RTL |
| 6 | Real Multi-Drone | 3 real drones | 3-drone formation with real hardware |
| 7 | Mission Execution | 3 real drones | Full mission cycle: setup, preflight, mission, post-flight, teardown |

### Certification Checklist

An operator must demonstrate competency at each level before proceeding. The checklist is stored per-operator and verified by a qualified supervisor.

- [ ] Level 1: Can start SITL, connect, and read telemetry values correctly
- [ ] Level 2: Can execute a 5-waypoint mission with clean takeoff and landing
- [ ] Level 3: Can maintain formation spacing within 2m tolerance for 5 minutes
- [ ] Level 4: Can correctly respond to all 4 emergency scenarios within 30 seconds
- [ ] Level 5: Can hover a real drone for 2 minutes with stable altitude (+/- 1m)
- [ ] Level 6: Can fly 3-drone formation for 5 minutes without spacing violations
- [ ] Level 7: Can complete full mission cycle (setup through teardown) under 90 minutes

**Requirement:** All levels must be completed before unsupervised field deployment.

---

## F. Weather Integration

### Weather Parameters and Limits

| Parameter | GO Limit | NO-GO Limit | Data Source |
|-----------|----------|-------------|-------------|
| Wind speed (sustained) | < 20 km/h | >= 25 km/h | API or anemometer |
| Wind gusts | < 25 km/h | >= 30 km/h | API or anemometer |
| Precipitation | None | Any rain, snow, hail | API or visual |
| Temperature | 10-40 degrees C | < 5 degrees C or > 45 degrees C | API or thermometer |
| Visibility | > 1 km | < 500 m | API or visual |
| Cloud ceiling | > 120 m AGL | < mission altitude | API or visual |
| Lightning | None within 30 km | Any within 10 km | API |

**Notes:**
- F450-class drones are rated for ~15 m/s (54 km/h) max speed; flying in 25 km/h wind leaves minimal control authority.
- LiPo performance degrades significantly below 10 degrees C (increased internal resistance, reduced capacity).
- LiPo thermal runaway risk increases above 45 degrees C.
- Part 107 requires visual line of sight (VLOS) -- visibility must be sufficient.

### Data Sources

**Primary: OpenWeatherMap API (free tier)**
- 1,000 API calls/day free.
- Current weather + 5-day forecast.
- Wind, temperature, precipitation, visibility, cloud cover.

```python
# weather check integrated into preflight
import requests

def get_weather(lat, lon, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    return {
        "wind_speed_kmh": data["wind"]["speed"] * 3.6,
        "wind_gust_kmh": data["wind"].get("gust", 0) * 3.6,
        "temp_c": data["main"]["temp"],
        "visibility_m": data.get("visibility", 10000),
        "precipitation": data["weather"][0]["main"],
        "description": data["weather"][0]["description"],
    }
```

**Fallback: Manual operator input**
- For field conditions where API data is unavailable or unreliable.
- Operator enters wind speed (handheld anemometer), temperature, and visual conditions.

### Preflight Integration

The preflight check includes weather as a GO/NO-GO gate:

```
[PREFLIGHT] Weather: 12 km/h wind NW, 22°C, clear -- GO
[PREFLIGHT] Weather: 30 km/h gusts expected -- NO-GO (wind exceeds 25 km/h limit)
[PREFLIGHT] Weather: Rain forecasted in 45 min -- WARNING (plan short mission)
```

Weather data is also passed to `loadout_checker.py`'s `predict_with_conditions()` for accurate endurance estimates under wind load.

---

## G. Fleet Analytics Dashboard (Design Only -- Phase 2 Build)

This section describes the analytics dashboard that will be built in Phase 2. During Phase 0-1, the underlying data is collected by `battery_tracker.py`, `maintenance_tracker.py`, and `flight_report.py`.

### Dashboard Panels

**1. Fleet Overview**
- Total fleet flight hours (cumulative, this week, this month).
- Drones available vs. in maintenance vs. retired.
- Active alerts and warnings.

**2. Battery Health Curves**
- Per-battery capacity trend over cycle count.
- Fleet-wide average battery health.
- Batteries approaching retirement threshold.
- Cost per flight-hour (battery depreciation).

**3. Failure Analysis**
- Failure rate by component type (motor, ESC, prop, GPS, radio).
- Mean time between failures (MTBF) per component.
- Failure correlation with environmental conditions.

**4. Per-Drone Reliability Score**

```
reliability_score = weighted_average(
    0.3 * (1 - failure_rate),
    0.2 * maintenance_compliance,
    0.2 * calibration_freshness,
    0.15 * battery_health_avg,
    0.15 * (1 - hard_landing_rate),
)
```

**5. Cost Tracking**
- Battery replacement cost per drone per month.
- Prop replacement cost per flight hour.
- Total repair cost per drone.
- Cost per mission.

**6. Mission Analytics**
- Mission success rate (completed vs. aborted).
- Abort reasons breakdown (weather, battery, mechanical, operator).
- Average mission duration trend.
- Utilization rate: flight-ready drones / total drones.

### Data Sources

All data is already collected by the operational systems built in Phase 0-1:
- `batteries/{battery_id}.json` -- battery health over time.
- `maintenance/{drone_id}.json` -- maintenance history and compliance.
- `logs/` -- flight logs with telemetry and anomaly data.
- `fleet/` -- drone registry and configuration.

### Technology

- **Backend:** Python + FastAPI (already used for ground station API).
- **Frontend:** Lightweight charts (Chart.js or similar) embedded in ground station UI.
- **Storage:** JSON files for Phase 2; migrate to SQLite or PostgreSQL for Phase 3+.

---

## H. Firmware Update Management

### Version Tracking

Each drone's `fleet/{drone_id}.json` includes firmware metadata:

```json
{
  "drone_id": "alpha",
  "firmware_version": "4.5.1",
  "firmware_date": "2026-03-10",
  "firmware_hash": "sha256:abc123...",
  "last_update": "2026-03-10"
}
```

### Fleet-Wide Update Workflow

```
┌─────────────────┐
│ 1. Download new  │
│    firmware      │
└────────┬────────┘
         │
┌────────▼────────┐
│ 2. Flash canary  │ (one drone, typically the most expendable)
│    drone         │
└────────┬────────┘
         │
┌────────▼────────┐
│ 3. Run preflight │
│    + test flight │
└────────┬────────┘
         │
    ┌────▼────┐
    │  PASS?  │
    └────┬────┘
     yes │     no
    ┌────▼──┐ ┌──▼─────────┐
    │4. Flash│ │4. Rollback │
    │ rest   │ │   canary,  │
    │of fleet│ │   report   │
    └────────┘ └────────────┘
```

**Step-by-step:**

1. **Download:** Get new ArduPilot firmware from official repository. Verify checksum.
2. **Flash canary:** Use `firmware_flasher.py` to update one drone. Record old firmware version for rollback.
3. **Test:**
   - Run full preflight check suite.
   - Conduct a 5-minute test flight: hover, waypoint navigation, RTL.
   - Compare telemetry quality against previous firmware (vibration levels, GPS accuracy, battery drain rate).
4. **Decision:**
   - **Pass:** Flash remaining fleet one at a time. Run preflight on each after flashing.
   - **Fail:** Reflash canary with previous firmware version. Document the issue. Do not update fleet.
5. **Record:** Update `fleet/{drone_id}.json` with new firmware version, date, and hash for each updated drone.

### Rollback Procedure

The `firmware_flasher.py` keeps the previous firmware binary in `firmware/previous/`. Rollback is:

```bash
python firmware_flasher.py flash alpha --firmware firmware/previous/arducopter_4.5.0.apj
```

### Update Cadence

- Check for ArduPilot stable releases monthly.
- Only update to **stable** releases, never beta or dev.
- Skip releases that do not include relevant bug fixes or features.
- Always update all drones to the same firmware version -- mixed fleets cause unpredictable behavior.

---

## Appendix: Directory Structure

```
drone-swarm-orchestrator/
├── batteries/          # Battery health records (per-battery JSON)
│   ├── B001.json
│   ├── B002.json
│   └── ...
├── maintenance/        # Maintenance records (per-drone JSON)
│   ├── alpha.json
│   ├── bravo.json
│   └── ...
├── fleet/              # Drone registry (existing)
├── logs/               # Flight logs (existing)
├── firmware/           # Firmware binaries
│   ├── current/
│   └── previous/
├── src/
│   ├── battery_tracker.py
│   ├── maintenance_tracker.py
│   └── ... (existing modules)
└── design/
    └── OPERATIONS_DESIGN.md  # This document
```

---

#drone-swarm #operations #maintenance #batteries #training
