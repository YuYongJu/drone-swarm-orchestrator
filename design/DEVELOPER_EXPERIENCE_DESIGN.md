---
title: Developer Experience & Platform Design
type: design
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, dx, cli, jupyter, dashboard, design-system, branding, user-flows]
---

# Drone Swarm Orchestrator -- Complete Developer Experience & Platform Design

**Document Version:** 1.0
**Last Updated:** 2026-03-26
**Status:** Active

This document designs BOTH interfaces of the Drone Swarm Orchestrator platform from first principles: the Python SDK / CLI (code-first) and the cloud dashboard (visual). It builds on the existing PRODUCT_SPEC.md, API_DESIGN.md, and UI_DESIGN.md, filling the gaps those documents leave: the CLI tool, the Jupyter experience, the error philosophy, the design system rationale, branding, and end-to-end user flows.

---

## Table of Contents

1. [PART 1: Developer Experience (DX) -- CLI + Code](#part-1-developer-experience)
   - 1.1 [First 5 Minutes](#11-first-5-minutes)
   - 1.2 [CLI Tool Design: `dso`](#12-cli-tool-design)
   - 1.3 [Jupyter / Notebook Experience](#13-jupyter--notebook-experience)
   - 1.4 [Error Messages & Debugging Philosophy](#14-error-messages--debugging-philosophy)
2. [PART 2: Cloud Dashboard UI](#part-2-cloud-dashboard-ui)
   - 2.1 [Dashboard Home](#21-dashboard-home)
   - 2.2 [Live Mission View](#22-live-mission-view)
   - 2.3 [Mission Planner](#23-mission-planner)
   - 2.4 [Fleet Management](#24-fleet-management)
   - 2.5 [Analytics / Post-Flight](#25-analytics--post-flight)
   - 2.6 [Mobile Experience](#26-mobile-experience)
3. [PART 3: Design System](#part-3-design-system)
   - 3.1 [Visual Language](#31-visual-language)
   - 3.2 [Branding](#32-branding)
   - 3.3 [Accessibility](#33-accessibility)
4. [PART 4: User Flows](#part-4-user-flows)
   - 4.1 [New Developer -> First Simulated Flight (Code)](#41-new-developer--first-simulated-flight-code-path)
   - 4.2 [New Developer -> First Simulated Flight (Dashboard)](#42-new-developer--first-simulated-flight-dashboard-path)
   - 4.3 [Developer -> Deploy to Real Hardware](#43-developer--deploy-to-real-hardware)
   - 4.4 [Operator -> Monitor Live Mission](#44-operator--monitor-live-mission-in-field)
   - 4.5 [Developer -> Debug Failed Mission](#45-developer--debug-a-failed-mission)
   - 4.6 [Team Lead -> Post-Flight Analytics](#46-team-lead--review-post-flight-analytics)
   - 4.7 [Enterprise Admin -> Multi-Site Fleet](#47-enterprise-admin--manage-fleet-across-multiple-sites)

---

# PART 1: Developer Experience

## 1.1 First 5 Minutes

The first 5 minutes determine whether a developer adopts the platform or closes the tab. Our benchmark: "faster time-to-flying-drones than any alternative." The developer should see virtual drones moving on a map within 3 minutes of `pip install`.

### The Install

```bash
pip install drone-swarm
```

What happens:

- Installs the `drone_swarm` Python package and the `dso` CLI tool.
- Zero native dependencies for simulation mode. pymavlink is the only hard dependency.
- Optional extras: `pip install drone-swarm[notebook]` adds Jupyter widgets, `pip install drone-swarm[all]` adds everything.
- The install completes with a single post-install message printed to stderr:

```
  drone-swarm 0.1.0 installed successfully.

  Quick start:
    dso quickstart        Interactive tutorial (recommended)
    dso sim --drones 3    Launch 3 simulated drones instantly
    python -c "from drone_swarm import Swarm; print('Ready')"

  Docs: https://docs.droneswarm.dev
```

This message is short, non-intrusive, and gives three clear paths forward. It does not require the developer to read a README.

### The "Hello World" Equivalent

The hello world for drone swarms is: **three drones take off, fly a V formation for 30 seconds, and land.** It is the simplest behavior that demonstrates multi-drone coordination rather than just single-drone control.

**Path A: One Command (Zero Code)**

```bash
dso quickstart
```

This launches an interactive guided experience:

```
 DSO Quickstart

 Welcome to Drone Swarm Orchestrator.
 This tutorial will launch 3 simulated drones and fly a V formation.

 No hardware required -- everything runs on your machine.

 Step 1/4: Starting SITL simulation...

   Launching drone alpha  ... ready (tcp:127.0.0.1:5760)
   Launching drone bravo  ... ready (tcp:127.0.0.1:5770)
   Launching drone charlie ... ready (tcp:127.0.0.1:5780)

 Step 2/4: Connecting swarm...

   alpha    CONNECTED   GPS: 10 sats   Battery: 100%
   bravo    CONNECTED   GPS: 10 sats   Battery: 100%
   charlie  CONNECTED   GPS: 10 sats   Battery: 100%

 Step 3/4: Flying V formation...

   Arming all drones...     done
   Taking off to 20m...     done
   Forming V shape (15m spacing)...

   Live status (updates every 2s, Ctrl+C to abort safely):

   alpha    ALT: 20.1m  SPD: 0.3 m/s  BAT: 99%  [FORMATION]
   bravo    ALT: 20.0m  SPD: 0.2 m/s  BAT: 99%  [FORMATION]
   charlie  ALT: 19.8m  SPD: 0.4 m/s  BAT: 99%  [FORMATION]

   Holding formation for 30 seconds... 18s remaining

 Step 4/4: Landing...

   Return to launch initiated.
   alpha    LANDED
   bravo    LANDED
   charlie  LANDED

 Mission complete! Here is what just happened:
   - 3 SITL drones were launched on your machine
   - They connected via MAVLink over TCP
   - They flew a V formation at 20m altitude
   - They returned to launch after 30 seconds

 Next steps:
   1. Open the code:  dso quickstart --show-code
   2. Try 10 drones:  dso sim --drones 10 --formation orbit
   3. Read the guide:  https://docs.droneswarm.dev/tutorials
   4. Open in Jupyter: dso quickstart --notebook
```

**Path B: 10 Lines of Python (Code-First)**

```python
import asyncio
from drone_swarm import Swarm

async def main():
    swarm = Swarm.simulation(drones=3)     # Launches SITL automatically
    await swarm.connect()
    await swarm.takeoff(altitude=20)
    await swarm.formation("v", spacing=15)
    await asyncio.sleep(30)
    await swarm.rtl()

asyncio.run(main())
```

The key insight: `Swarm.simulation(drones=3)` is a convenience constructor that starts SITL instances behind the scenes. The developer does not need to know what SITL is, what ports to use, or how MAVLink works. They just say "give me 3 drones" and get them.

**Path C: Jupyter Notebook**

```bash
dso quickstart --notebook
```

This generates and opens a Jupyter notebook (`dso_quickstart.ipynb`) with cells that walk through the same tutorial but with inline explanations, interactive widgets, and a live map showing drone positions. See Section 1.3 for the full notebook experience.

### What Makes This Better Than Alternatives

| Existing Tool | Time to First Flight | DSO Target |
|---|---|---|
| DroneKit-Python | ~2 hours (install SITL, configure, write code) | 3 minutes (`dso quickstart`) |
| MAVSDK-Python | ~1 hour (install server binary, learn async API) | 3 minutes |
| Skybrush | ~30 min (install server, client, configure) | 3 minutes |
| QGroundControl | 5 min (single drone only, no code, no swarm) | 3 min (multi-drone + code) |

The competitive advantage: **one command gives you multi-drone, not just single-drone.** Every existing tool starts with one drone. We start with three.

---

## 1.2 CLI Tool Design

The CLI is called `dso` (short, memorable, three characters -- like `git`, `npm`, `fly`). It is registered as a console script via pyproject.toml.

### pyproject.toml Entry

```toml
[project.scripts]
dso = "drone_swarm.cli:main"
```

### Design Principles (Inspired by Vercel, Fly.io, Railway)

1. **Progressive disclosure**: `dso` with no args shows a beautiful help page. Each command has `--help` with examples.
2. **Colorful but not noisy**: Use color to encode meaning (green=success, yellow=warn, red=error, blue=info, dim=secondary). Never use color as the only signal.
3. **Real-time feedback**: Long operations show progress spinners or live-updating tables. Never leave the user staring at a blank terminal.
4. **Scriptable**: All commands support `--json` output for piping. Human-readable output is the default.
5. **Safe by default**: Destructive commands require `--yes` to skip confirmation. Real-hardware commands warn before execution.

### Command Tree

```
dso
  quickstart              Interactive first-flight tutorial
  sim                     Simulation commands
    start                 Launch SITL drones
    stop                  Stop all SITL instances
    run                   Start SITL + run a script against it
    status                Show running simulation status
  fleet                   Fleet management
    list                  List registered drones
    add                   Register a new drone
    remove                Remove a drone from fleet
    scan                  Auto-discover drones on network
    health                Health check all drones
  preflight               Pre-flight checks
    run                   Run all checks
    check <drone>         Check a single drone
  mission                 Mission management
    plan                  Create/edit a mission plan
    validate              Validate a mission plan
    list                  List saved missions
    export                Export mission as JSON/KML
  fly                     Flight operations
    arm                   Arm all drones
    takeoff               Take off to altitude
    formation             Fly a formation
    sweep                 Execute area sweep
    rtl                   Return to launch
    land                  Land at current position
    estop                 Emergency stop
  status                  Live fleet status dashboard
  logs                    Log management
    tail                  Stream live logs
    download              Download flight logs
    replay                Replay a mission in terminal
  flash                   Firmware operations
    install               Flash swarm firmware to drone
    check                 Check current firmware version
  dev                     Developer tools
    new-behavior          Scaffold a new behavior module
    test                  Run tests against SITL
    publish               Publish behavior to marketplace
    docs                  Open API docs in browser
  config                  Configuration
    init                  Initialize project config file
    show                  Display current config
    set <key> <value>     Set a config value
  login                   Authenticate with DSO Cloud
  deploy                  Deploy mission to cloud
  version                 Show version
```

### Terminal Output Design

All CLI output follows these conventions:

**Symbols:**
- `+` (green) = success/added
- `-` (red) = removed/failed
- `!` (yellow) = warning
- `>` (blue) = info/action
- `?` (dim) = prompt

**Typography:**
- Bold white for headings and drone IDs
- Dim gray for timestamps and secondary info
- Monospace for values (coordinates, percentages, IDs)

### `dso sim start` -- Launching Simulation

```
$ dso sim start --drones 5

 DSO Simulation

> Starting 5 SITL instances...

  alpha    tcp:127.0.0.1:5760  starting...
  bravo    tcp:127.0.0.1:5770  starting...
  charlie  tcp:127.0.0.1:5780  starting...
  delta    tcp:127.0.0.1:5790  starting...
  echo     tcp:127.0.0.1:5800  starting...

  alpha    tcp:127.0.0.1:5760  + ready (2.1s)
  bravo    tcp:127.0.0.1:5770  + ready (2.3s)
  charlie  tcp:127.0.0.1:5780  + ready (2.4s)
  delta    tcp:127.0.0.1:5790  + ready (2.2s)
  echo     tcp:127.0.0.1:5800  + ready (2.5s)

+ 5/5 drones ready

  Connect in Python:
    swarm = Swarm.simulation(drones=5)

  Or use the CLI:
    dso fly takeoff --altitude 20
    dso fly formation v --spacing 15

  Stop simulation:
    dso sim stop
```

### `dso status` -- Live Fleet Dashboard in Terminal

This is the "killer CLI feature" -- a real-time, auto-refreshing terminal dashboard inspired by `htop` and `k9s`.

```
$ dso status

 DSO Fleet Status                                      Updated: 14:23:07
 Mission: Alpha Sweep  Status: ACTIVE  Duration: 00:04:23  Drones: 3/3

 ID        Role     Status     Alt    Speed   Bat    GPS    RSSI    WP
 --------  -------  ---------  -----  ------  -----  -----  ------  ------
 alpha     Recon    AIRBORNE   20.1m  8.3m/s  87%    12sat  -38dB   3/7
 bravo     Relay    AIRBORNE   20.0m  0.2m/s  92%    10sat  -42dB   relay
 charlie   Recon    AIRBORNE   19.8m  8.1m/s  28%!   11sat  -45dB   3/7

 Alerts:
 ! 14:24:02  charlie  Battery at 28% -- monitor closely

 Controls: [q]uit  [p]ause  [r]tl-all  [e]stop  [f]ilter  [1-9] select drone
```

Features:
- Updates every 1 second via live telemetry
- Color-coded values (battery turns yellow < 50%, red < 20%)
- Keyboard controls for basic operations
- Selecting a drone (number keys) shows expanded telemetry
- `--watch` mode stays open indefinitely
- `--json` emits newline-delimited JSON for piping

### `dso sim run` -- One-Shot Simulation

The most common developer workflow: start SITL, run a script, print results, shut down.

```
$ dso sim run --drones 5 --script my_mission.py

 DSO Simulation Run

> Launching 5 SITL drones...              + ready (3.2s)
> Running my_mission.py...

  [my_mission.py output here]

> Mission complete. Shutting down SITL...  + done

 Summary:
  Duration:    02:34
  Drones:      5/5 healthy
  Waypoints:   12/12 reached
  Incidents:   0
  Log saved:   ./logs/run-2026-03-26-142307.json
```

### `dso flash` -- Firmware Operations

```
$ dso flash install --port /dev/ttyUSB0

 DSO Firmware Flasher

> Detecting hardware...
  Flight controller:  Pixhawk 6C (STM32H743)
  Current firmware:   ArduCopter 4.5.1
  Target firmware:    ArduCopter 4.5.1 + DSO Swarm Module v0.1.0

? Flash swarm firmware to this device? (y/N) y

> Flashing...  [========================================] 100%  (42s)
> Rebooting flight controller...
> Verifying DSO swarm module...  + verified

+ Firmware flashed successfully.

  This drone is now swarm-ready. Next:
    dso fleet add --port /dev/ttyUSB0 --name delta
```

### `dso deploy` -- Push to Cloud

```
$ dso deploy

 DSO Deploy

> Validating mission plan...               + valid
> Uploading to DSO Cloud...                + uploaded
> Syncing fleet configuration...           + synced

+ Deployed to https://app.droneswarm.dev/missions/M-2026-0042

  Open dashboard:  dso open
  View status:     dso status --cloud
```

---

## 1.3 Jupyter / Notebook Experience

The Jupyter experience is the "killer DX" that no drone tool has. It turns swarm development into a visual, iterative, exploratory workflow -- the same paradigm that made Jupyter essential for data science.

### Installation

```bash
pip install drone-swarm[notebook]
```

This adds: `ipywidgets`, `ipyleaflet`, `ipywidgets-bokeh` (for real-time charts), and `drone_swarm.notebook` (custom widgets).

### The Quickstart Notebook

`dso quickstart --notebook` generates and opens a notebook with these cells:

**Cell 1: Setup**
```python
from drone_swarm import Swarm
from drone_swarm.notebook import SwarmMap, TelemetryPanel, MissionTimeline

# Launch 3 simulated drones
swarm = await Swarm.simulation(drones=3)
await swarm.connect()
print(f"Connected: {swarm.summary()}")
```

Output:
```
Connected: 3 drones (alpha, bravo, charlie) | SITL mode | all IDLE
```

**Cell 2: Live Map Widget**
```python
# Display interactive map with live drone positions
map_widget = SwarmMap(swarm, height=500)
map_widget
```

This renders an interactive Leaflet map directly in the notebook cell showing:
- Drone markers (same rich markers as the dashboard: role color, battery arc, heading arrow)
- Real-time position updates (1Hz in notebook to avoid overwhelming the kernel)
- Click-to-select a drone (shows info popup)
- Draggable waypoint placement (shift-click to add waypoints)
- Dark satellite-hybrid tiles matching the dashboard aesthetic

**Cell 3: Takeoff and Watch**
```python
# Take off -- watch the map above update in real-time
await swarm.takeoff(altitude=20)
```

The map widget above automatically shows drones climbing. No re-rendering needed -- the widget subscribes to telemetry events via an asyncio background task.

**Cell 4: Formation Flight**
```python
# Fly V formation -- watch drones rearrange on the map
await swarm.formation("v", spacing=15)
```

The map shows drones moving into V shape. Formation target positions appear as ghost markers (translucent) so the developer can see target vs. actual.

**Cell 5: Telemetry Panel**
```python
# Live telemetry charts
telemetry = TelemetryPanel(swarm, metrics=["battery", "altitude", "speed"])
telemetry
```

This renders a panel of live-updating Bokeh charts (battery over time, altitude over time, speed over time) with one line per drone, color-coded by role. Charts update every second.

**Cell 6: Experiment**
```python
# Try different formations
await swarm.formation("orbit", radius=30)
await asyncio.sleep(10)
await swarm.formation("line", spacing=20)
await asyncio.sleep(10)
await swarm.rtl()
```

**Cell 7: Mission Timeline**
```python
# Review what happened
timeline = MissionTimeline(swarm)
timeline
```

This renders an interactive timeline widget showing all events: takeoff, formation changes, waypoint arrivals, landing. Clicking an event on the timeline scrubs the map to that moment (replay mode).

### Custom Widgets API

```python
from drone_swarm.notebook import SwarmMap, TelemetryPanel, MissionTimeline, DroneTable

# SwarmMap: Interactive Leaflet map
map_widget = SwarmMap(
    swarm,
    height=500,
    tile_style="dark",          # "dark", "satellite", "street"
    show_trails=True,           # Show breadcrumb trails
    show_geofence=True,         # Show geofence boundary
    show_waypoints=True,        # Show mission waypoints
    show_formations=True,       # Show formation ghost markers
    auto_fit=True,              # Auto-zoom to fit all drones
)

# TelemetryPanel: Live charts
telemetry = TelemetryPanel(
    swarm,
    metrics=["battery", "altitude", "speed", "satellites", "rssi"],
    time_window=300,            # Show last 5 minutes
    update_interval=1.0,        # Update every 1 second
)

# DroneTable: Live status table (like dso status but in notebook)
table = DroneTable(swarm, columns=["id", "role", "status", "alt", "bat", "gps"])

# MissionTimeline: Event timeline with scrubbing
timeline = MissionTimeline(swarm, show_events=True, show_telemetry=False)
```

### Why This Is a Killer Feature

1. **No other drone tool has this.** QGroundControl is a desktop app. Mission Planner is a desktop app. Skybrush has a separate client. None integrate with the developer's existing workflow.
2. **Iterative development.** Change one parameter, re-run the cell, watch drones respond. The feedback loop is seconds, not minutes.
3. **Visual debugging.** See exactly where drones went wrong on a map, in the same environment where you write code.
4. **Sharable.** Notebooks are documentation, tutorials, and reproducible experiments. Push to GitHub, colleagues can run the same swarm mission.
5. **Educational.** Universities can teach swarm algorithms with interactive notebooks. Students see immediate visual results.

---

## 1.4 Error Messages & Debugging Philosophy

### Design Principles

We follow the Elm/Rust school of error message design:

1. **Say what went wrong in plain English.** No jargon, no error codes as the primary message.
2. **Say why.** Explain the root cause, not just the symptom.
3. **Say how to fix it.** Give a concrete action the developer can take right now.
4. **Show context.** Point to the relevant code, configuration, or hardware state.
5. **Be a teacher, not a gatekeeper.** Errors are learning opportunities.

### Error Message Format

Every error in DSO follows this structure:

```
ERROR: [short summary of what went wrong]

[explanation of why]

[what to do about it]

[optional: link to docs]
```

### Examples

**GPS Lock Failure (Hardware)**

```
ERROR: Drone 'alpha' cannot arm -- GPS not locked.

  Current GPS status:
    Satellites:  3 (need at least 6 for 3D fix)
    Fix type:    No fix
    HDOP:        99.9 (need < 2.0)

  This usually means the drone cannot see enough satellites.

  Try:
    1. Move the drone to open sky (away from buildings, trees, metal structures).
    2. Wait 30-60 seconds for GPS to acquire satellites.
    3. Check that the GPS module antenna is facing upward and unobstructed.
    4. Run: dso preflight check alpha --verbose  to monitor GPS acquisition.

  Docs: https://docs.droneswarm.dev/troubleshooting/gps
```

Compare this to what MAVLink gives you: `PreArm: GPS: need 3D fix`. Our message explains what "3D fix" means, what the current state is, and what to physically do about it.

**Formation Impossible (Logic)**

```
ERROR: Cannot fly 'v' formation with 1 drone.

  V formation requires at least 2 drones. You have 1 drone connected:
    - alpha (Recon, IDLE)

  The other 2 registered drones are not connected:
    - bravo  -- last seen 5 minutes ago (connection timeout)
    - charlie -- never connected in this session

  Try:
    1. Check that bravo and charlie are powered on and within radio range.
    2. Run: dso fleet health  to diagnose connection issues.
    3. For simulation: Swarm.simulation(drones=3) to get 3 virtual drones.

  Docs: https://docs.droneswarm.dev/formations
```

**Battery Too Low for Mission (Safety)**

```
WARNING: Drone 'charlie' may not complete this mission.

  Current battery:  23% (estimated 4 min remaining)
  Mission requires: ~8 min at current consumption rate

  Breakdown:
    Remaining waypoints:  4 (total distance: 1.2 km)
    Estimated flight time: 7.8 min
    Safety margin (20%):   1.6 min
    Total needed:          9.4 min
    Battery provides:      ~4.0 min

  Options:
    1. Replace charlie's battery before the mission.
    2. Reduce the mission scope: remove waypoints 5-7.
    3. Reassign charlie's waypoints to another drone:
       swarm.reassign("charlie", to="bravo")
    4. Proceed anyway (not recommended -- charlie will auto-RTL at 20%).

  Docs: https://docs.droneswarm.dev/safety/battery
```

**Connection Failure (Network)**

```
ERROR: Cannot connect to drone 'bravo' at tcp:127.0.0.1:5770

  Connection attempt timed out after 10 seconds.

  Possible causes:
    1. SITL is not running on port 5770.
       Check: dso sim status
       Fix:   dso sim start --drones 3

    2. The port is blocked by a firewall or another process.
       Check: lsof -i :5770  (Linux/Mac) or netstat -ano | findstr 5770  (Windows)

    3. The drone is powered off or out of radio range.
       Check: Is the drone's LED showing solid green (armed) or blinking blue (waiting)?

    4. The connection string is wrong.
       You provided:  tcp:127.0.0.1:5770
       For USB:       /dev/ttyUSB0  (Linux) or COM3 (Windows)
       For radio:     udp:0.0.0.0:14550

  Docs: https://docs.droneswarm.dev/troubleshooting/connection
```

**Type Error (SDK Misuse)**

```
ERROR: Invalid altitude value: "twenty"

  swarm.takeoff() expects altitude as a number (meters), but you passed a string.

  Your code:
    await swarm.takeoff(altitude="twenty")
                                  ^^^^^^^^
  Fix:
    await swarm.takeoff(altitude=20)

  Valid range: 1 to 400 meters. Default: 10 meters.

  Docs: https://docs.droneswarm.dev/api/swarm#takeoff
```

### Error Severity Levels

| Level | Color | Behavior | Example |
|---|---|---|---|
| `ERROR` | Red | Operation fails. Must fix before proceeding. | Cannot arm, connection failed |
| `WARNING` | Yellow | Operation proceeds but something is concerning. | Low battery, weak signal |
| `HINT` | Blue | Suggestion that is not a problem. | "Tip: use --verbose to see telemetry during flight" |
| `DEPRECATION` | Dim yellow | API will change in a future version. | "formation('v') is deprecated, use formation(Formation.V_SHAPE)" |

### Debug Mode

```bash
# Normal output: clean, human-readable
dso fly takeoff --altitude 20

# Verbose: shows MAVLink messages and internal state transitions
dso fly takeoff --altitude 20 --verbose

# Debug: full MAVLink packet dump, timing information, internal queues
dso fly takeoff --altitude 20 --debug

# JSON: machine-readable output for scripts and CI
dso fly takeoff --altitude 20 --json
```

### Python SDK Debugging

```python
import logging

# Set DSO to verbose logging
logging.getLogger("drone_swarm").setLevel(logging.DEBUG)

# Or use the built-in helper
from drone_swarm import enable_debug
enable_debug()  # Sets up pretty logging with timestamps, drone IDs, MAVLink decoding

# Structured error handling
from drone_swarm.errors import ArmingError, ConnectionError, FormationError

try:
    await swarm.takeoff(altitude=20)
except ArmingError as e:
    print(e.drone_id)        # "alpha"
    print(e.reason)          # "GPS not locked"
    print(e.suggestion)      # "Move to open sky, wait 30s"
    print(e.telemetry)       # {"gps_sats": 3, "fix_type": "none", "hdop": 99.9}
```

Every exception in DSO carries structured data (`drone_id`, `reason`, `suggestion`, `telemetry`) so developers can build their own error handling UIs on top.

---

# PART 2: Cloud Dashboard UI

The dashboard builds on the existing UI_DESIGN.md (which specifies the mission control, planner, fleet manager, pre-flight, telemetry, and replay screens in detail). This section focuses on the **cloud-specific features** that the existing doc does not cover: the dashboard home, team collaboration, analytics, and the bridge between code and visual interfaces.

## 2.1 Dashboard Home

### First Screen After Login

The dashboard home is not a generic "welcome" page. It answers the question every operator asks: **"What is the state of my fleet right now?"**

Layout:

```
+------------------------------------------------------------------------+
| DSO Cloud                    [Project: Farm Survey]  [Team v]  [User] |
+------------------------------------------------------------------------+
|                                                                        |
|  FLEET HEALTH STRIP (full width, 80px)                                 |
|  [5 drones]  [3 online]  [0 in flight]  [2 offline]  [0 alerts]      |
|                                                                        |
+----------------------------------+-------------------------------------+
|                                  |                                     |
|  RECENT MISSIONS (left, 60%)     |  FLEET QUICK VIEW (right, 40%)     |
|                                  |                                     |
|  Alpha Sweep       03/25 14:20   |  alpha    IDLE   87%  12sat       |
|  +++ 3 drones  12:34  COMPLETE   |  bravo    IDLE   92%  10sat       |
|                                  |  charlie  IDLE   28%! 11sat       |
|  Perimeter Check   03/24 09:15   |  delta    OFFLINE  --   --        |
|  +++ 5 drones  08:22  COMPLETE   |  echo     OFFLINE  --   --        |
|                                  |                                     |
|  Test Flight       03/23 16:45   |  [Start Pre-Flight]               |
|  +++ 1 drone   03:11  ABORTED   |  [Open Mission Planner]            |
|                                  |                                     |
+----------------------------------+-------------------------------------+
|                                                                        |
|  QUICK ACTIONS                                                         |
|  [+ New Mission]  [Launch Quickstart]  [View Logs]  [Fleet Health]    |
|                                                                        |
+------------------------------------------------------------------------+
```

### Fleet Health Strip

A persistent, always-visible strip at the top of every dashboard page (like Datadog's alert bar). It shows:
- Total drones registered
- How many are online/connected
- How many are currently flying
- How many are offline
- Active alerts count (red badge if > 0, links to alert feed)

Clicking any number drills into the relevant Fleet Manager view, pre-filtered.

### Recent Missions Panel

Shows the last 10 missions as cards, each showing:
- Mission name
- Date/time
- Drone count
- Duration
- Status badge (COMPLETE green, ABORTED red, IN PROGRESS blue pulse)
- Click to open Mission Replay

The top card (most recent) is expanded to show a thumbnail of the flight path on a map.

### Fleet Quick View

A compact version of the Fleet Manager showing only the essentials: drone ID, status, battery, GPS. Links to the full Fleet Manager.

### Design Reference

Inspired by:
- **Vercel Dashboard**: Project list with status badges, recent deployments, clean hierarchy
- **Grafana Home**: Health overview panels, recent dashboards, quick actions
- **Datadog**: Persistent alert strip, fleet-wide health at a glance

---

## 2.2 Live Mission View

This is fully specified in UI_DESIGN.md (Screen 1: Mission Control). The existing spec covers:
- 3-column layout (Fleet Panel, Map, Mission Feed)
- Rich drone markers with battery arcs, heading arrows, status halos
- Notification overlay (streak alerts)
- Emergency stop button (E-LAND + KILL MOTORS)
- Live camera feeds (tap-to-view, PiP, multi-feed grid)
- Role execution animations

**Additions for the cloud version:**

### Multi-User Presence

When multiple team members are viewing the same mission:
- Avatar bubbles in the top bar showing who is watching (like Google Docs)
- A colored cursor on the map when someone hovers over a specific drone
- Chat/annotation sidebar for real-time communication (optional, collapsible)

### Audit Trail

Every operator command is logged with:
- Who issued it (user ID)
- What was issued (command + parameters)
- When (timestamp)
- Result (success/failure + drone response)

Visible in the Mission Feed as a distinct entry type:

```
14:23:06  > jake.o   arm all           + ACK (3 drones)
14:25:17  > maria.r  rtl charlie       + ACK (charlie returning)
```

### Cloud Recording

If the mission is running via the cloud dashboard (not purely local SDK), all telemetry is automatically streamed to cloud storage for post-flight analytics. No manual "download logs" step needed.

---

## 2.3 Mission Planner

This is fully specified in UI_DESIGN.md (Screen 2). The existing spec covers waypoint editing, formation preview, drone assignment, geofencing, and validation.

**Additions for cloud:**

### Code Export -- The Bridge Between Visual and Code-First

The most important cloud-specific feature. After planning a mission visually, the developer can export it as Python code:

```
[Export as Python] button -> generates:
```

```python
from drone_swarm import Swarm, Mission, Formation, Waypoint, Geofence

mission = Mission(
    name="Alpha Sweep",
    formation=Formation.V_SHAPE(angle=60, spacing=15),
    waypoints=[
        Waypoint(lat=34.0522, lon=-118.2437, alt=50),
        Waypoint(lat=34.0530, lon=-118.2420, alt=50),
        Waypoint(lat=34.0540, lon=-118.2400, alt=50, loiter=10),
    ],
    geofence=Geofence.polygon([
        (34.0510, -118.2450),
        (34.0550, -118.2450),
        (34.0550, -118.2380),
        (34.0510, -118.2380),
    ], max_altitude=100, breach_action="rtl"),
    defaults={"altitude": 50, "speed": 8.0, "rtl_altitude": 60},
)

async def run():
    swarm = Swarm.connect(["tcp:..."])  # Replace with your fleet
    await swarm.execute(mission)
```

This means developers can:
1. Prototype visually in the dashboard
2. Export as code
3. Modify the code (add custom logic, conditionals, sensor reactions)
4. Run via CLI or SDK
5. Re-import modified missions back to the dashboard

The dashboard also supports **Import from Python**: paste a Mission object definition and the planner renders it visually.

### Simulation Preview

Before deploying to real hardware, a "Run in Simulation" button launches the mission against SITL on the cloud:
- Virtual drones execute the exact mission plan
- A mini Mission Control view shows the simulation playing out
- Estimated duration, battery consumption, and coverage area are calculated
- Any issues (impossible waypoints, geofence violations, battery insufficiency) are caught

---

## 2.4 Fleet Management

This is fully specified in UI_DESIGN.md (Screen 3: Fleet Manager). The existing spec covers drone registration (QR scan), configuration, firmware flash, and preflight.

**Additions for cloud:**

### Maintenance Tracker

A new section in each drone's detail view:

```
MAINTENANCE LOG

Total flight time:     42h 17m (286 flights)
Battery cycles:        87 (replace at 300)
Last maintenance:      2026-03-20 (6 days ago)
Next scheduled:        2026-04-01 (motor inspection)

RECENT INCIDENTS
  03/24  Hard landing on RTL -- vibration check recommended
  03/18  GPS glitch at WP-3 -- self-corrected

MAINTENANCE SCHEDULE
  [ ] 50-hour motor inspection (due at 50h, currently 42h)
  [x] 25-hour propeller check (completed 03/20)
  [x] Battery cycle 75 capacity test (completed 03/15)
```

### OTA Firmware Management

Fleet-wide firmware operations:
- View firmware versions across all drones in a matrix view
- "Update All" button with rollout strategy (sequential, not parallel -- update one drone, verify, proceed)
- Firmware changelog displayed before update
- Rollback capability (keep previous firmware image)

### Fleet Map

A dedicated view showing all registered drones on a map:
- Last known position (for offline drones)
- Current position (for online drones)
- Color-coded by status
- Clustering for large fleets (50+ drones)

---

## 2.5 Analytics / Post-Flight

### Flight Replay

Specified in UI_DESIGN.md (Screen 6: Mission Replay). The existing spec covers the map replay, telemetry charts, timeline scrubber, and transport controls.

**Additions for cloud analytics:**

### Anomaly Detection

The cloud backend analyzes flight logs and flags anomalies:

```
ANOMALY REPORT -- Mission "Alpha Sweep" (03/25)

DETECTED ANOMALIES:

  1. GPS Drift on charlie at 14:24:32
     Position jumped 3.2m in 100ms (expected <0.5m).
     Possible cause: GPS multipath interference.
     Affected waypoints: WP-3 to WP-4.
     [View on map] [View telemetry]

  2. Battery Consumption Spike on alpha at 14:23:15
     Draw increased from 12A to 28A for 8 seconds.
     Possible cause: Wind gust, aggressive maneuver, or motor issue.
     [View on map] [View telemetry]

  3. Vibration Anomaly on bravo at 14:25:01
     Z-axis vibration increased 40% above baseline.
     Possible cause: Loose propeller, damaged motor bearing.
     Recommendation: Physical inspection before next flight.
     [View on map] [View telemetry]
```

### Coverage Maps

For agriculture and inspection use cases:
- Heatmap overlay showing which areas were covered by drone cameras/sensors
- Gap analysis: areas within the mission boundary that were not covered
- Overlap analysis: areas covered by multiple passes (useful for photogrammetry)
- Export as GeoTIFF for use in GIS tools

### Report Generation

One-click PDF report generation for clients:

```
MISSION REPORT
  Project:     Solar Farm Inspection -- Site B
  Date:        March 25, 2026
  Duration:    12 minutes 34 seconds
  Drones:      3 (alpha, bravo, charlie)
  Area:        4.2 hectares
  Coverage:    98.7%
  Anomalies:   2 (1 GPS drift, 1 vibration)
  Images:      847 captured
  Status:      COMPLETE

  [Map of flight paths]
  [Coverage heatmap]
  [Anomaly locations]
  [Telemetry summary charts]
  [Recommendations]
```

Exportable as PDF, with customizable branding (client logo, company header).

### Comparative Analytics

Compare missions over time:
- Same area, different dates: track changes (crop growth, construction progress)
- Same fleet, different missions: track fleet performance degradation
- Trend graphs: average mission duration, average battery consumption, anomaly frequency

---

## 2.6 Mobile Experience

### Strategy: Responsive Web, Not Native App

Building a native iOS/Android app is a maintenance burden for an open-source project. Instead, the cloud dashboard is a responsive Progressive Web App (PWA) that works well on mobile browsers and can be "installed" to the home screen.

### What You Need in the Field vs. at Desk

| Capability | Field (Mobile/Tablet) | Desk (Desktop) |
|---|---|---|
| Mission Control (live map, feed) | Essential | Essential |
| Pre-Flight Checks | Essential | Essential |
| Mission Planner (create/edit) | Not practical | Essential |
| Fleet Manager (register, configure) | Limited | Essential |
| Telemetry Dashboard (charts) | Secondary | Essential |
| Mission Replay | Not needed | Essential |
| Analytics / Reports | Not needed | Essential |
| Alerts / Notifications | Essential | Essential |

### Mobile-Specific Features

**Push Notifications (via PWA Service Worker)**

Critical alerts push to the operator's phone even when the dashboard is backgrounded:
- Drone lost
- Battery critical
- Geofence breach
- Mission complete
- Connection lost to ground station

Each notification includes:
- Alert type and severity icon
- Drone ID and brief description
- Tap to open the relevant Mission Control view

**Field Mode Toggle**

A dedicated "Field Mode" accessible from the mobile hamburger menu that:
- Locks the screen to Mission Control + Feed only (removes navigation overhead)
- Enables maximum brightness on supported devices
- Activates high-contrast mode automatically
- Enables audio alerts (vibration + alarm tones)
- Shows a persistent connection quality indicator (latency to ground station)

**Offline Capability**

The PWA caches:
- The application shell (all UI code)
- Pre-downloaded map tiles for the mission area
- The current mission plan
- Fleet configuration

If the cloud connection drops, the dashboard continues to work with local telemetry (if the operator's device is directly connected to the ground station via local network). Cloud sync resumes when connectivity returns.

---

# PART 3: Design System

## 3.1 Visual Language

### Dark Mode by Default

The platform uses dark mode as the primary (and initially only) theme. Rationale:

1. **Field operators work at dawn, dusk, and night.** Bright UIs cause eye strain and destroy night vision adaptation (which takes 20-30 minutes to regain once lost). A dark UI preserves night vision.
2. **Outdoor glare.** Counterintuitively, dark mode with high-contrast accents is more readable than light mode in direct sunlight on modern OLED/AMOLED screens. The dark pixels produce no light, so accents pop.
3. **Developer preference.** 80%+ of developers use dark mode in their IDEs. Matching the dashboard to their development environment reduces context-switching friction.
4. **Battery life.** OLED screens consume less power rendering dark pixels. Field operators using tablets care about battery life.

The existing UI_DESIGN.md specifies the full color palette. Summary of the philosophy:

- **Off-black backgrounds** (`#0F1117`, not pure `#000000`) to reduce halation and provide visual depth via layered surface colors.
- **High-contrast text** (`#F1F3F9` on `#0F1117` = 15.4:1 contrast ratio, exceeding WCAG AAA 7:1).
- **Saturated accent colors** for drone roles (blue, green, red, yellow) because these must be distinguishable at a glance on a map. Desaturated slightly from pure primaries to reduce eye strain on dark backgrounds.
- **Pure red reserved for danger.** `--danger` (#DC2626) is used only for emergency stop, critical alerts, and errors. It is never used for decorative purposes.

### Map Style

- **Default**: Dark satellite-hybrid (Mapbox `satellite-streets-v12` with custom dark overlay at 40% opacity for non-satellite areas). Gives operators real terrain imagery with readable road/feature labels.
- **High Contrast mode**: Pure dark vector map with white labels. For conditions where satellite imagery is too busy.
- **Offline fallback**: Dark gray canvas with coordinate grid lines. Functional, not pretty, but usable.

### Status Color System

Inspired by traffic lights and military status boards -- universally understood:

| Status | Color | Hex | Shape Indicator | Text Label |
|---|---|---|---|---|
| Healthy / Connected / Ready | Green | `#22C55E` | Filled circle | "READY" |
| Caution / Armed / Low Battery | Amber | `#F59E0B` | Filled triangle | "CAUTION" |
| Critical / Lost / Error | Red | `#EF4444` | Filled square | "CRITICAL" |
| In Flight / Active | Blue | `#3B82F6` | Pulsing circle | "ACTIVE" |
| Returning / RTL | Purple | `#A855F7` | Arrow icon | "RETURNING" |
| Idle / Offline | Gray | `#5C6178` | Empty circle | "IDLE" |

Every status is communicated via **three independent channels**: color + shape + text label. This ensures accessibility for color-blind users (see Section 3.3).

### Typography

| Context | Font | Rationale |
|---|---|---|
| UI text, headings, buttons | Geist Sans | Clean, modern, legible at small sizes. Same family as Vercel -- signals "developer tool" aesthetics. |
| Telemetry values, coordinates, IDs, code | Geist Mono | Monospace for tabular alignment. Numbers line up. Coordinates are scannable. |
| CLI output | System monospace | Respects terminal font configuration. |

Minimum font size: 14px across the entire application (except 12px for badges, which compensate with bold weight and high contrast).

---

## 3.2 Branding

### Brand Name

**drone-swarm** (lowercase, hyphenated) for the package name and documentation.
**DSO** (Drone Swarm Orchestrator) for shorthand.
**dso** for the CLI command.

The hyphenated lowercase follows Python/npm convention (like `create-react-app`, `vue-cli`). The three-letter acronym is easy to type and say.

### Brand Personality

**Technical but approachable. Serious but not military. Open-source hacker ethos with professional polish.**

We are not:
- ArduPilot (utilitarian, raw, no design attention -- functional but intimidating to newcomers)
- DJI (consumer-focused, locked ecosystem, proprietary everything)
- Skydio (enterprise premium, polished but closed, no developer community)

We are:
- **Vercel for drones**: Developer-sleek, great DX, opinionated but extensible
- **Arduino for swarms**: Accessible to beginners, deep enough for experts, community-driven
- **Docker for flight**: Containerized complexity, simple surface, powerful internals

### Logo Concepts

The logo should work at 16x16 favicon size and on a 3" sticker.

**Concept A: Hex Mesh (Recommended)**

A hexagonal mesh pattern (3-4 hexagons) that suggests:
- Drone swarm formations (hexagonal packing is optimal for area coverage)
- Open-source community (mesh = network = collaboration)
- Technical precision (geometric, not organic)

The hexagons are rendered as outlines (not filled) to suggest openness and connectivity. One hexagon is highlighted (filled or accented) to suggest a "leader" or "focus node." The overall shape forms a subtle upward-pointing arrow, suggesting flight.

Color: The logo works in single-color (white on dark, dark on light). The accent hexagon uses `--drone-recon` blue (`#3B82F6`) in the color version.

**Concept B: Murmuration**

An abstract pattern of 5-7 small dots arranged in a flowing, organic formation that evokes a bird murmuration or drone swarm. The dots are connected by thin lines showing communication links. The pattern is asymmetric (not a rigid grid) to suggest intelligence and adaptability.

**Concept C: Stacked Chevrons**

Two overlapping chevron (V) shapes -- the universal symbol for formation flight. The front chevron is solid, the rear is an outline, creating a sense of depth and movement. Simple, instantly recognizable, scales well to small sizes.

### Brand Colors

| Token | Hex | Usage |
|---|---|---|
| Primary | `#3B82F6` | Logo accent, links, primary actions, brand blue |
| Background | `#0F1117` | App background, marketing site background |
| Text | `#F1F3F9` | Primary text on dark backgrounds |
| Accent | `#22C55E` | Success, CTAs, "get started" buttons |

### Voice and Tone

| Context | Tone | Example |
|---|---|---|
| Documentation | Clear, direct, educational | "The Swarm class is your entry point. It manages connections to all drones in your fleet." |
| Error messages | Empathetic, helpful, specific | "Drone 'alpha' cannot arm -- GPS not locked. Move to open sky and wait 30 seconds." |
| CLI output | Concise, informative | "+ 5/5 drones ready" |
| Marketing | Confident, aspirational | "Build drone swarm applications in Python. From pip install to formation flight in 3 minutes." |
| Release notes | Factual, celebratory for big features | "v0.2.0 adds orbit formation, 10-drone simulation, and Jupyter widgets." |

---

## 3.3 Accessibility

### Color-Blind Safe Status Indicators

Following Carbon Design System and WCAG 2.1 guidelines, every status is communicated via **three independent channels**:

1. **Color**: Standard status colors (green, amber, red, blue, purple, gray).
2. **Shape**: Each status has a unique shape icon:
   - Ready: filled circle
   - Caution: filled triangle (points up)
   - Critical: filled square
   - Active: pulsing circle (animation adds a fourth channel)
   - Returning: left-pointing arrow
   - Idle: empty circle (outline only)
3. **Text label**: Every status badge includes a text label ("READY", "CAUTION", "CRITICAL").

This ensures that a user who cannot distinguish red from green can still differentiate "filled triangle with CAUTION label" from "filled circle with READY label."

**On the map**: Drone markers use role colors (blue, green, red, yellow) which are challenging for the most common color vision deficiency (red-green). To mitigate:
- Each drone has a unique letter (A, B, C...) inside the marker
- Role is indicated by shape as well as color (Recon: radar cone animation, Relay: connection lines, etc.)
- A "color-blind mode" toggle in settings replaces the role colors with a high-contrast palette: blue (`#3B82F6`), orange (`#F97316`), purple (`#A855F7`), white (`#FFFFFF`) -- these four colors are distinguishable under all common types of color vision deficiency (protanopia, deuteranopia, tritanopia)

**In charts**: Lines and bars use:
- Distinct colors from the color-blind-safe palette
- Different dash patterns (solid, dashed, dotted, dash-dot)
- Data point markers (circle, square, triangle, diamond)
- A legend with both color swatch and text label

### Screen Reader Support

- All interactive elements have `aria-label` attributes
- Map is described via a live `aria-live` region that announces drone status changes: "Alpha is now airborne at 20 meters"
- Drone list in Fleet Panel is a proper `<table>` with column headers
- Mission Feed entries use `role="log"` with `aria-live="polite"` (critical alerts use `aria-live="assertive"`)
- All modal dialogs trap focus and are announced
- Emergency Stop button has `aria-label="Emergency Land. Opens confirmation dialog."`

### Keyboard Navigation

Full keyboard navigation is specified in UI_DESIGN.md (keyboard shortcuts section). Summary:
- `Tab` / `Shift+Tab` moves between major regions (fleet panel, map, feed, action bar)
- Arrow keys navigate within regions (drone list, feed entries, map controls)
- Number keys `1-9` select drones
- `[` and `]` toggle fleet panel and feed panel
- `Space` on action buttons triggers them
- `Escape` closes modals and deselects
- `/` opens the command palette (similar to VS Code Ctrl+K)

### Command Palette

A universal keyboard shortcut (`/` or `Ctrl+K`) opens a command palette overlay (like VS Code, Raycast, or Linear):

```
+-----------------------------------------------+
| > Search commands, drones, missions...         |
|-----------------------------------------------|
| Recent:                                        |
|   RTL All                                      |
|   Select alpha                                 |
|   Open Mission Planner                         |
| Drones:                                        |
|   alpha (Recon, Airborne)                      |
|   bravo (Relay, Airborne)                      |
| Commands:                                      |
|   Takeoff All                                  |
|   Pause Mission                                |
|   Export Logs                                   |
+-----------------------------------------------+
```

This makes every function reachable via keyboard, which is critical for accessibility and power users.

---

# PART 4: User Flows

## 4.1 New Developer -> First Simulated Flight (Code Path)

**Goal:** Go from zero to seeing drones fly in simulation, entirely via code.

### Step 1: Install (Terminal)

```bash
pip install drone-swarm
```

**Time:** 30 seconds
**Emotion:** Neutral -- standard pip install, nothing special yet.
**Where they get stuck:** pip version conflicts, missing Python 3.11+. Mitigated by clear error message: "drone-swarm requires Python 3.11+. You have 3.9. Install Python 3.11+ from python.org."

### Step 2: Quickstart (Terminal)

```bash
dso quickstart
```

**Time:** 2 minutes (mostly SITL startup)
**Emotion:** Delight -- they see drones launching, connecting, flying formation. The live-updating terminal is visually engaging.
**What they see:** The full quickstart output shown in Section 1.1.
**Where they get stuck:** SITL not installed. `dso quickstart` detects this and offers to install it: "ArduPilot SITL not found. Install it? [Y/n]". On Linux/Mac, it runs the install automatically. On Windows, it provides the Docker alternative: "dso sim start --docker --drones 3".

### Step 3: Explore (Editor)

```bash
dso quickstart --show-code
```

**Time:** 5 minutes
**Emotion:** "Oh, that is surprisingly simple." The generated code is 15 lines.
**What they see:** The quickstart Python script with comments explaining each line. Opened in their default editor or printed to terminal.
**What they modify:** Change drone count to 5, change formation to "line", change altitude to 30. Re-run. See it work.

### Step 4: Build Their Own (Editor)

They copy the quickstart code into their own file and start modifying it. The SDK's type hints and docstrings guide them in their IDE (VS Code autocomplete shows all formation options, all mission types).

**Time:** 15-30 minutes
**Emotion:** Empowerment -- "I am building a drone swarm application."
**Where they get stuck:** Async Python. Some developers are unfamiliar with `asyncio`. The SDK documentation includes a "Python async primer" page. The CLI provides synchronous wrappers for common operations (`dso fly takeoff` does not require async code).

### Step 5: Share (GitHub)

They push their script to GitHub. The README includes a badge: "Built with drone-swarm" and a `dso sim run --script` command so others can reproduce.

**Where they get stuck:** Dependencies. Mitigated by generating a `requirements.txt` or `pyproject.toml` dependency.

---

## 4.2 New Developer -> First Simulated Flight (Dashboard Path)

**Goal:** Go from zero to seeing drones fly in simulation, entirely via the cloud dashboard.

### Step 1: Sign Up (Browser)

Visit `https://app.droneswarm.dev`. Sign up with GitHub OAuth (one click, no email verification needed for the free tier).

**Time:** 30 seconds
**Emotion:** Smooth -- no friction.

### Step 2: Onboarding Wizard (Dashboard)

After sign-up, a 3-step wizard:

```
Step 1 of 3: Create Your Fleet

  For this tutorial, we will create 3 virtual drones.

  [Create 3 Virtual Drones]   (or: Connect Real Hardware)
```

Click the button. Three virtual drones appear in the Fleet Manager with status "SIMULATION."

```
Step 2 of 3: Plan a Mission

  Draw a flight path on the map by clicking to place waypoints.
  Or, use a template:

  [V Formation Demo]  [Area Sweep Demo]  [Orbit Demo]
```

Click "V Formation Demo." The Mission Planner opens with pre-loaded waypoints.

```
Step 3 of 3: Fly!

  Your mission is ready. Run it in simulation to see it in action.

  [Run Simulation]
```

Click "Run Simulation." The Mission Control view opens showing virtual drones taking off, forming a V, flying the waypoints, and landing.

**Time:** 3 minutes total
**Emotion:** Amazement -- "I just flew a drone swarm without installing anything."

### Step 3: Modify (Dashboard)

The developer goes back to the Mission Planner, changes the formation to "Orbit", adjusts the radius, re-runs simulation.

**Time:** 5 minutes
**Emotion:** Exploration -- trying different configurations, seeing immediate results.

### Step 4: Export to Code (Dashboard)

The developer clicks "Export as Python" and gets a script they can run locally.

**Time:** 1 minute
**Emotion:** "Now I can take this further with code."
**Where they get stuck:** They need to install the SDK locally to run the exported code. The export includes installation instructions at the top of the file as a comment.

---

## 4.3 Developer -> Deploy to Real Hardware

**Goal:** Transition from simulation to flying real physical drones.

### Step 1: Flash Firmware (Workshop)

```bash
dso flash install --port /dev/ttyUSB0
```

**Time:** 5 minutes per drone
**Emotion:** Nervous -- this is real hardware. The CLI is reassuring with clear progress and verification.
**What they see:** The firmware flash output shown in Section 1.2.
**Where they get stuck:** Wrong USB port. `dso flash install --scan` auto-detects connected flight controllers. Wrong firmware. `dso flash` auto-detects the flight controller model and selects the right firmware.

### Step 2: Register Drones (Workshop)

```bash
dso fleet add --port /dev/ttyUSB0 --name alpha
dso fleet add --port /dev/ttyUSB1 --name bravo
dso fleet add --port /dev/ttyUSB2 --name charlie
```

Or scan QR labels:
```bash
dso fleet add --scan  # Opens camera for QR scanning
```

**Time:** 2 minutes per drone
**Emotion:** Building something real.

### Step 3: Pre-Flight Check (Field)

```bash
dso preflight run
```

**What they see:**

```
 DSO Pre-Flight Check

  alpha    COMMS [+] GPS [+] BAT [+] COMPASS [+] FAILSAFE [+] ARM [+]  PASSED
  bravo    COMMS [+] GPS [!] BAT [+] COMPASS [+] FAILSAFE [+] ARM [+]  PASSED (warnings)
  charlie  COMMS [+] GPS [+] BAT [+] COMPASS [+] FAILSAFE [+] ARM [+]  PASSED

! bravo: GPS has 5 satellites (6+ recommended). Flight will proceed but precision may be reduced.

+ 3/3 drones ready for flight.
```

**Time:** 2 minutes
**Where they get stuck:** Compass calibration needed. The error message walks them through it: "Rotate the drone slowly in all three axes. Run `dso preflight check bravo --verbose` to see calibration progress."

### Step 4: First Real Flight (Field)

```bash
dso fly takeoff --altitude 10

# Start conservatively -- low altitude, short distance
dso fly formation v --spacing 10
dso status  # Watch live telemetry

# After 30 seconds, bring them home
dso fly rtl
```

**Time:** 5 minutes
**Emotion:** Exhilaration and anxiety simultaneously. Real drones are moving.
**Where they get stuck:** Wind. The CLI shows wind speed estimates from accelerometer data. "Drone alpha is drifting -- estimated wind 15 km/h from NW. Consider reducing altitude or aborting."

### Step 5: Iterate (Workshop + Field)

They modify their Python script, re-run in simulation to verify, then deploy to hardware again.

**Where they get stuck:** Behavioral differences between SITL and real hardware (GPS accuracy, wind, latency). The documentation has a "SITL vs Real Hardware" guide explaining common differences and how to account for them.

---

## 4.4 Operator -> Monitor Live Mission in Field

**Goal:** A non-technical operator (Sergeant Maria Reyes persona) monitors an active mission from a tablet in the field.

### Step 1: Power Up (Field, 0:00)

Operator powers on 5 pre-configured drones. Each drone's LED sequence indicates boot status. Operator opens the dashboard on their iPad.

### Step 2: Fleet Check (Dashboard, 0:30)

The Dashboard Home shows 5 drones detected. The Fleet Health Strip: "5 drones online, 0 alerts."

**Emotion:** Confidence -- everything is green.

### Step 3: Pre-Flight (Dashboard, 1:00)

Operator taps "Start Pre-Flight." The Pre-Flight Check screen runs checks automatically. All drones pass (green bars animate across).

**Where they get stuck:** One drone fails compass check. The screen shows a clear "COMPASS: Needs Cal" with a red bar and a "Recheck" button. They recalibrate (physical rotation), tap Recheck, it passes.

### Step 4: Launch (Dashboard, 2:00)

Operator navigates to Mission Control. The mission plan is pre-loaded (planned by the developer the night before). Operator taps "Takeoff All." Confirmation dialog: "Takeoff 5 drones to 20m?" They confirm.

**Emotion:** Focus intensifies. They are now monitoring.

### Step 5: Monitor (Dashboard, 2:00 - 14:00)

This is where the Mission Feed shines. The operator's primary attention is on:
1. The map -- are drones where they should be?
2. The Mission Feed -- is anything going wrong?

At 8:00, a critical alert fires: "CRITICAL BATTERY: charlie at 15% -- auto-RTL initiated." The streak alert slides across the map. The alarm sounds. The Mission Feed shows the event.

**What the operator does:** Nothing. The system handles it. Charlie auto-returns. The fleet replans around the gap. The operator watches to confirm charlie lands safely.

**Where they get stuck:** Wanting to intervene. The dashboard makes it easy to override (tap charlie, tap "Hold Position") but the default autonomous behavior is usually correct. The Mission Feed confirms: "SWARM: charlie removed from formation. 4 drones continuing."

### Step 6: Mission Complete (Dashboard, 14:00)

All waypoints reached. "RTL All" auto-triggers (end of mission plan). Drones land. Status: "MISSION COMPLETE."

**Emotion:** Relief and satisfaction.

### Step 7: Post-Flight (Dashboard, 15:00)

Operator taps "Mission Summary" -- sees a brief summary of duration, coverage, incidents. Shares the summary link with the team lead for detailed review.

---

## 4.5 Developer -> Debug a Failed Mission

**Goal:** A mission failed mid-flight. The developer needs to find out why.

### Step 1: Notice the Failure (Dashboard or Terminal)

The mission ended with status "ABORTED" due to emergency land triggered by the operator (or auto-triggered by the system).

### Step 2: Open Mission Replay (Dashboard)

Navigate to Replay tab. Select the failed mission. The replay loads.

### Step 3: Scrub to the Failure (Dashboard)

The timeline shows event markers. The red `!` marker at 08:23 indicates where the anomaly was first detected. Click it -- the map jumps to that moment, showing drone positions.

**What they see:** At 08:23, drone charlie's battery dropped from 22% to 8% in 15 seconds (abnormal -- likely a bad cell). The anomaly detector flagged it: "Battery consumption spike: 14% drop in 15s (expected <2% per minute)."

### Step 4: Examine Telemetry (Dashboard)

The Battery chart shows a steep cliff on charlie's line. The altitude chart shows charlie beginning RTL simultaneously. The vibration chart (accessible via "Add Chart" dropdown in replay mode) shows a vibration spike 30 seconds before the battery cliff.

### Step 5: Diagnose (Dashboard + CLI)

The anomaly report suggests: "Vibration spike followed by battery cliff may indicate a motor failure causing increased current draw on remaining motors."

```bash
# Download the raw logs for deeper analysis
dso logs download --mission M-2026-0042 --drone charlie

# Inspect motor outputs
dso logs analyze charlie --focus motors

  Motor 1: 1480us avg (normal)
  Motor 2: 1900us avg (OVERWORKED -- compensating)
  Motor 3: 1510us avg (normal)
  Motor 4: 980us avg (UNDERPERFORMING -- likely the fault)

  Diagnosis: Motor 4 appears to have failed or lost a propeller.
  The flight controller compensated by increasing Motor 2.
  This drew excess current, draining the battery rapidly.

  Recommendation: Inspect Motor 4 and its propeller physically.
```

### Step 6: Fix and Verify (Workshop)

Developer inspects charlie. Finds a cracked propeller on Motor 4. Replaces it. Runs bench test:

```bash
dso preflight check charlie --verbose --include-motors
```

Motor test passes. Developer schedules a re-run of the mission.

**Where they get stuck:** Correlating timeline events with telemetry data. Mitigated by the synced timeline cursor across all charts and the map.

---

## 4.6 Team Lead -> Review Post-Flight Analytics

**Goal:** Review the overall performance of a series of missions for a client report.

### Step 1: Open Analytics (Dashboard)

Navigate to Analytics tab. Select the project ("Solar Farm Inspection -- Site B") and date range (March 15-25).

### Step 2: View Summary Metrics

```
PERIOD SUMMARY: March 15-25, 2026

  Missions:        12
  Total flight time: 4h 23m
  Area covered:     48.7 hectares
  Coverage quality:  97.3% (target: 95%)
  Anomalies:        7 (3 GPS drift, 2 battery, 1 vibration, 1 wind)
  Mean drone uptime: 94.2%

  Fleet utilization:
    alpha    98.1%  (12/12 missions)
    bravo    91.7%  (11/12 missions, 1 maintenance)
    charlie  83.3%  (10/12 missions, 2 battery issues)
```

### Step 3: Trend Analysis

Charts show:
- Mission duration trending downward (improving efficiency)
- Battery consumption per hectare: stable
- Anomaly frequency: decreasing (fleet is becoming more reliable)
- Coverage quality: increasing (mission plans are improving)

### Step 4: Generate Report

Click "Generate Report." Customize:
- Include client branding (upload logo)
- Select sections: executive summary, flight paths, coverage maps, anomaly report, recommendations
- Format: PDF

The PDF is generated and downloadable. It includes all charts, maps, and narrative text.

### Step 5: Share

Share the PDF with the client. Or share a read-only dashboard link so the client can explore interactively.

**Where they get stuck:** Interpreting anomalies. The dashboard provides plain-English explanations for every detected anomaly, not just raw data.

---

## 4.7 Enterprise Admin -> Manage Fleet Across Multiple Sites

**Goal:** An enterprise customer manages 50+ drones across 4 geographic sites.

### Step 1: Organization View (Dashboard)

The enterprise tier adds an "Organization" view accessible from the top-level navigation:

```
+----------------------------------------------------------------+
| DSO Cloud       [Org: SolarTech Inc.]                  [Admin] |
+----------------------------------------------------------------+
|                                                                 |
| SITES                                                           |
|                                                                 |
| +-------------------+  +-------------------+                   |
| | Phoenix, AZ       |  | El Paso, TX       |                  |
| | 15 drones         |  | 12 drones         |                  |
| | 2 active missions |  | 0 active          |                  |
| | 0 alerts          |  | 1 alert (offline) |                  |
| +-------------------+  +-------------------+                   |
|                                                                 |
| +-------------------+  +-------------------+                   |
| | Sacramento, CA    |  | Denver, CO        |                  |
| | 18 drones         |  | 8 drones          |                  |
| | 1 active mission  |  | 0 active          |                  |
| | 0 alerts          |  | 0 alerts          |                  |
| +-------------------+  +-------------------+                   |
|                                                                 |
+----------------------------------------------------------------+
| ORGANIZATION SUMMARY                                            |
| 53 drones | 3 active missions | 1 alert | 14 missions this week |
+----------------------------------------------------------------+
```

### Step 2: Site Drill-Down

Click a site card to see that site's full dashboard (Fleet Manager, Mission Control, Analytics) scoped to only drones at that site.

### Step 3: Fleet Transfers

Move drones between sites:

```
TRANSFER DRONE

  Drone:  charlie (Class B, currently at Phoenix)
  To:     El Paso

  This will:
  - Remove charlie from Phoenix fleet
  - Add charlie to El Paso fleet
  - Transfer maintenance history and flight logs

  [Cancel]  [Transfer]
```

### Step 4: Organization-Wide Analytics

The analytics view supports cross-site comparisons:
- Which site has the highest anomaly rate?
- Which drones need maintenance across all sites?
- Total organizational flight hours this quarter

### Step 5: Access Control

Role-based access:
- **Admin**: Full access to all sites, can transfer drones, manage users
- **Site Manager**: Full access to one site, can create missions and manage fleet
- **Operator**: Can run missions and monitor, cannot modify fleet or create missions
- **Viewer**: Read-only access to analytics and replays

### Step 6: OTA Firmware Rollout

Push a firmware update across all 53 drones:

```
FIRMWARE ROLLOUT

  Target:  All 53 drones across 4 sites
  From:    DSO Swarm Module v0.1.0
  To:      DSO Swarm Module v0.2.0

  Rollout strategy:
    Phase 1: 5 drones at Phoenix (canary)
    Phase 2: All Phoenix drones (if canary succeeds)
    Phase 3: El Paso
    Phase 4: Sacramento
    Phase 5: Denver

  [Start Rollout]
```

The rollout proceeds sequentially with automatic health checks after each phase. If a phase fails (drones report issues post-update), the rollout pauses and alerts the admin.

**Where they get stuck:** Understanding which drones are which across sites. Mitigated by consistent callsign naming conventions and the fleet transfer audit trail.

---

## Appendix: Research Sources

This design was informed by analysis of the following existing tools and platforms:

- [QGroundControl UI Design Guide](https://docs.qgroundcontrol.com/master/en/qgc-dev-guide/user_interface_design/index.html) -- tablet-first design, QML architecture, multi-device patterns
- [DroneDeploy UX-Led Dashboards](https://www.dronedeploy.com/blog/ux-led-dashboards) -- clean flight planning, reusable flight templates
- [Skydio Developer Tools](https://www.skydio.com/developer-tools) -- Remote Flight Deck HUD, Quick Actions, controller-centric UI
- [Skybrush Open-Source Suite](https://skybrush.io/) -- multi-UAV GCS, FlockWave protocol, 5000-drone tested
- [Carbon Design System Status Indicators](https://carbondesignsystem.com/patterns/status-indicator-pattern/) -- color + shape + text triple-encoding for accessibility
- [Elm Compiler Error Messages](https://discourse.elm-lang.org/t/error-messages-style/7828) -- first-person voice, educational approach
- [Rust Error Message Design (RFC 1644)](https://rust-lang.github.io/rfcs/1644-default-and-expanded-rustc-errors.html) -- code-centric presentation, progressive detail
- [ipyleaflet for Jupyter](https://blog.jupyter.org/interactive-gis-in-jupyter-with-ipyleaflet-52f9657fa7a) -- interactive GIS in notebooks
- [Railway vs Fly.io vs Vercel comparison](https://www.jasonsy.dev/blog/comparing-deployment-platforms-2025) -- CLI DX philosophy differences
- [Color-blind accessible dashboards (Courtney Jordan)](https://medium.com/@courtneyjordan/designing-color-blind-accessible-dashboards-ba3e0084be82) -- practical color-blind design patterns
- [Dark Mode UI Best Practices (Atmos)](https://atmos.style/blog/dark-mode-ui-best-practices) -- off-black backgrounds, desaturated colors
