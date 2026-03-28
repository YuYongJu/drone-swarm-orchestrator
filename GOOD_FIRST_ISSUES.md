# Good First Issues

Ready-to-post GitHub issues for new contributors. Each includes a clear scope, the files to modify, and the expected outcome.

---

## 1. Add diamond formation pattern

**Labels:** `good first issue`, `help wanted`

**Description:**
The missions module currently supports V-formation, line formation, area sweep, and orbit patterns. Add a `diamond_formation()` function that arranges drones in a diamond (rhombus) shape around a center point.

**Files to modify:**
- `drone_swarm/missions.py` -- add the `diamond_formation()` function
- `tests/test_missions.py` -- add unit tests for the new formation

**Expected outcome:**
- `diamond_formation(center_lat, center_lon, alt, n_drones, spacing_m)` returns a `list[list[Waypoint]]` where each sub-list is the waypoint sequence for one drone
- The formation places the leader at the front point, splits remaining drones evenly along the left and right diagonals, and places the last drone at the rear point
- Works correctly for 4+ drones; raises `ValueError` for fewer than 4
- Includes a docstring with the same style as existing functions (see `v_formation` for reference)
- All existing tests still pass

**Hints:**
- Use the existing `_offset_gps()` helper to convert meter offsets to GPS coordinates
- Look at `v_formation()` for the pattern to follow -- diamond is similar but with a rear vertex

---

## 2. Add `swarm.hover()` method

**Labels:** `good first issue`, `help wanted`

**Description:**
There is no explicit "hover in place" command on the `SwarmOrchestrator`. Add a `hover()` async method that commands all airborne drones to hold their current position using MAVLink's `MAV_CMD_NAV_LOITER_UNLIM`.

**Files to modify:**
- `drone_swarm/swarm.py` -- add the `hover()` method to `SwarmOrchestrator`
- `tests/test_swarm.py` -- add a unit test

**Expected outcome:**
- `await swarm.hover()` sends a loiter-unlimited command to every drone whose status is `AIRBORNE`
- Drones that are not airborne are skipped with a log warning
- The method is async and uses the existing `_send_command_long()` pattern found in the class
- Docstring follows the existing style

---

## 3. Add RTK GPS support documentation

**Labels:** `good first issue`, `help wanted`

**Description:**
Many precision agriculture and survey use cases require RTK GPS for centimeter-level accuracy. Add a documentation page explaining how to use RTK GPS base stations with the drone-swarm SDK.

**Files to modify:**
- `docs/tutorials/rtk-gps.md` -- new tutorial page
- `mkdocs.yml` -- add the page to the `Tutorials` nav section

**Expected outcome:**
- The page covers: what RTK GPS is (brief), supported base station hardware (u-blox F9P, Emlid Reach), how to configure MAVLink GPS injection, how to verify fix type in telemetry
- Includes a code example showing how to check `drone.gps_fix_type` after connecting
- Written in the same style as the existing tutorials in `docs/tutorials/`
- The page renders correctly with `mkdocs serve`

---

## 4. Improve error message when pymavlink is not installed

**Labels:** `good first issue`, `help wanted`

**Description:**
Several modules do a `try: from pymavlink import mavutil / except ImportError: mavutil = None` guard, but the user only sees a confusing `AttributeError: 'NoneType' object has no attribute ...` at runtime. Replace these silent fallbacks with a clear error message.

**Files to modify:**
- `drone_swarm/__init__.py` -- add an import-time check with a helpful message
- `drone_swarm/swarm.py` -- update the `mavutil` guard
- `drone_swarm/safety.py` -- update the `mavutil` guard

**Expected outcome:**
- When `pymavlink` is not installed and the user tries to call any function that needs it (e.g., `swarm.connect()`), they get an `ImportError` with the message: `"pymavlink is required but not installed. Install it with: pip install pymavlink"`
- The SDK can still be imported without pymavlink (for documentation builds, type checking, etc.) -- the error only fires when a MAVLink function is actually called
- Add a test that verifies the error message appears when mavutil is None

---

## 5. Add `dso doctor` CLI command

**Labels:** `good first issue`, `help wanted`

**Description:**
Add a `dso doctor` subcommand to the CLI that checks whether the system has everything needed to run drone-swarm: Python version, pymavlink, optional dependencies, SITL binary, and MAVProxy.

**Files to modify:**
- `drone_swarm/cli.py` -- add the `doctor` subcommand

**Expected outcome:**
- `dso doctor` prints a checklist to stdout, for example:
  ```
  [PASS] Python 3.12.1 (>=3.11 required)
  [PASS] pymavlink 2.4.41
  [FAIL] scipy not installed (needed for drone-swarm[allocation])
  [PASS] pyyaml 6.0.1
  [FAIL] arducopter SITL binary not found on PATH
  [PASS] mavproxy.py found
  ```
- Uses green/red ANSI colors when stdout is a TTY (reuse the existing `_green` / `_red` helpers in cli.py)
- Returns exit code 0 if all required checks pass, 1 otherwise
- Optional dependencies (scipy, pyyaml) show as warnings, not failures

---

## 6. Add formation switching with Hungarian reassignment

**Labels:** `good first issue`, `help wanted`

**Description:**
When switching from one formation to another (e.g., V to line), drones currently fly to whichever slot matches their index. This can cause unnecessary crossing paths. Use the Hungarian algorithm (already available in `allocation.py`) to optimally reassign drones to new formation slots, minimizing total travel distance.

**Files to modify:**
- `drone_swarm/formation_control.py` -- add a `reassign_slots()` function
- `drone_swarm/swarm.py` -- call `reassign_slots()` inside the `formation()` method before sending waypoints
- `tests/test_formation_control.py` -- add tests

**Expected outcome:**
- `reassign_slots(drones: list[Drone], targets: list[Waypoint]) -> list[tuple[Drone, Waypoint]]` returns the optimal drone-to-slot pairing using `scipy.optimize.linear_sum_assignment`
- The `formation()` method on `SwarmOrchestrator` uses this function when drones are already airborne (i.e., it is a formation switch, not the initial formation)
- A unit test with 4 drones and known positions verifies the assignment minimizes total distance
- Falls back to index-based assignment if scipy is not installed, with a log warning

---

## 7. Add JSON export for flight logs

**Labels:** `good first issue`, `help wanted`

**Description:**
The SDK currently logs telemetry to the Python logger but has no structured export. Add a `FlightLogger` class that records telemetry snapshots and can export them to a JSON file for post-flight analysis.

**Files to modify:**
- `drone_swarm/flight_log.py` -- new module with `FlightLogger` class
- `drone_swarm/__init__.py` -- add to public exports
- `tests/test_flight_log.py` -- unit tests

**Expected outcome:**
- `FlightLogger` has methods: `record(drone_id, lat, lon, alt, heading, battery_pct, timestamp)` and `export_json(path: Path)`
- The exported JSON structure is:
  ```json
  {
    "version": 1,
    "drones": {
      "alpha": [
        {"t": 1700000000.0, "lat": 42.0, "lon": -71.0, "alt": 10.0, "hdg": 90.0, "batt": 95.0}
      ]
    }
  }
  ```
- Includes at least 3 tests: record and export, empty log export, and roundtrip (export then load and verify)

---

## 8. Add battery-aware mission planning

**Labels:** `good first issue`, `help wanted`

**Description:**
The allocation module assigns drones to targets by distance only. Extend it to factor in remaining battery, so a drone with 30% battery is not assigned a far-away target while a drone with 90% sits idle nearby.

**Files to modify:**
- `drone_swarm/allocation.py` -- modify the cost matrix to incorporate battery
- `tests/test_allocation.py` -- add tests for battery-weighted allocation

**Expected outcome:**
- The `allocate_targets()` function accepts an optional `battery_weight: float = 0.3` parameter
- The cost for assigning drone *i* to target *j* becomes: `distance_ij * (1 + battery_weight * (1 - battery_pct_i / 100))`
- A drone at 100% battery has no penalty; a drone at 0% has a `battery_weight` multiplier penalty
- A test with two drones (one close but low battery, one far but full battery) verifies the full-battery drone gets the far target
- Default behavior (battery_weight=0) matches the existing behavior exactly

---

## 9. Create a quickstart video script

**Labels:** `good first issue`, `help wanted`

**Description:**
Write a script/outline for a 3-5 minute quickstart screencast that walks a new user through installing the SDK, launching a simulation, and running their first formation flight.

**Files to modify:**
- `docs/tutorials/quickstart-video-script.md` -- new file with the script
- `mkdocs.yml` -- add to the Tutorials nav section

**Expected outcome:**
- The script is organized into timed sections (e.g., "0:00-0:30 -- Introduction")
- Covers: install via pip, `dso version`, `dso simulate --drones 3`, connect with Python, takeoff, V-formation, RTL, shutdown
- Includes the exact terminal commands and Python code snippets to show on screen
- Notes which parts should show the terminal vs. a diagram/slide
- Written in markdown, renders cleanly with MkDocs Material

---

## 10. Add PX4 autopilot detection in simulation harness

**Labels:** `good first issue`, `help wanted`

**Description:**
The `SimulationHarness` currently only supports ArduPilot SITL (`arducopter`). Add detection for the PX4 SITL binary (`px4`) so the harness can report which autopilot stack is available, even if full PX4 support comes later.

**Files to modify:**
- `drone_swarm/simulation.py` -- add PX4 detection logic
- `tests/test_simulation.py` -- add tests

**Expected outcome:**
- Add a `detect_autopilot() -> str` module-level function that returns `"arducopter"`, `"px4"`, or `"none"` based on what is found on `PATH` (use `shutil.which()`)
- Add an `autopilot` property to `SimulationHarness` that calls `detect_autopilot()` and caches the result
- If the user tries to start the harness and neither binary is found, the error message now lists both options: "Neither `arducopter` nor `px4` found on PATH. Install ArduPilot SITL or PX4 SITL."
- A test mocks `shutil.which` to verify all three detection outcomes
- No actual PX4 launch logic needed yet -- just detection and messaging
