---
title: Compelling Product Plan
type: strategy
status: active
created: 2026-03-27
updated: 2026-03-27
tags: [drone-swarm, product, execution]
---

# From "Clean Foundation" to "People Actually Want This"

## The Problem

We have 193 tests, clean code, and a proper SDK structure. But nobody would look at
this and think "I NEED this." It's a pymavlink wrapper with nice packaging. That's
not enough.

## What Makes Developers Try a New SDK

Developers adopt tools for one reason: **it solves a painful problem in an embarrassingly
simple way.** The "wow" comes from the gap between the complexity of the problem and
the simplicity of the solution.

| Problem Complexity | Solution Simplicity | Result |
|---|---|---|
| "Coordinating 5 drones is a 6-month project" | `pip install drone-swarm` + 10 lines | "Holy shit, I need this" |
| "SITL multi-drone setup takes hours" | `dso simulate --drones 5` → drones flying | "Where has this been?" |
| "My drones crash into each other" | `swarm.enable_collision_avoidance()` | "This just saved me $1000 in parts" |

## The Three Things That Make This Compelling

### 1. One-Command Simulation (THE killer feature)

**Today:** To test a 5-drone swarm, a developer must:
1. Install ArduPilot SITL (30 min - 2 hours)
2. Start 5 separate SITL instances with unique ports/sysids
3. Configure MAVProxy or write pymavlink code for each
4. Write their own coordination logic
5. Debug race conditions for hours

**Target:**
```bash
pip install drone-swarm
dso simulate --drones 5 --visualize
```

A browser window opens showing 5 dots on a map. They're connected and hovering.
The developer writes 3 lines of Python and watches them fly a V-formation.

**Why this is novel:** NOBODY has this. CrazySwarm has it for $30 toy drones.
MAVSDK doesn't. DroneKit didn't. ArduPilot's SITL requires manual setup per drone.
This would be the first `pip install → flying swarm in 60 seconds` experience for
real autopilot-grade drones.

**What's needed:**
- [ ] SimulationHarness end-to-end test (DONE — passes but telemetry not flowing)
- [ ] Fix telemetry loop auto-start on connect
- [ ] Built-in MAVProxy map visualization OR simple web-based map viewer
- [ ] `--visualize` flag on `dso simulate` that opens a browser map
- [ ] Test on a clean machine (fresh Python venv, no prior ArduPilot setup)

### 2. Collision Avoidance (THE safety feature nobody has)

**Today:** If you send two ArduPilot drones to the same GPS coordinate, they collide.
There is ZERO open-source inter-drone collision avoidance for ArduPilot.

**Target:**
```python
swarm.enable_collision_avoidance(min_distance_m=5)
# Now drones automatically maintain 5m separation
# If two drones approach each other, the SDK intervenes
```

**Why this is novel:** Shield AI charges millions for this. Skydio's obstacle avoidance
is single-drone only. There is NO open-source multi-drone deconfliction layer.
This single feature would get us cited in academic papers.

**What's needed:**
- [ ] Implement velocity obstacle (VO) method for 2D deconfliction
- [ ] All-pairs distance check every telemetry cycle (100ms)
- [ ] When pair < min_distance: compute avoidance vector, send adjusted goto
- [ ] Test with 2 drones commanded to swap positions (head-on scenario)
- [ ] Test with 5 drones in tight formation
- [ ] Emit COLLISION_RISK event when intervention occurs

### 3. The Demo Video (THE marketing asset)

Nothing else matters if nobody sees it. The demo video is the product.

**The 60-second video that gets 500 GitHub stars:**

Three real drones. An open field. Split screen: code on left, drones on right.

```python
# This is the entire script shown in the video
from drone_swarm import Swarm

swarm = Swarm(["alpha", "bravo", "charlie"])
swarm.connect()
swarm.takeoff(alt=15)
swarm.formation("triangle", spacing=10)
swarm.rotate(360, duration=30)  # triangle rotates in the sky
swarm.land()
```

The viewer thinks: "12 lines of code controls 3 real drones in formation.
And it's open source. And it's free."

**What's needed:**
- [ ] Hardware purchased and assembled
- [ ] Part 107 passed
- [ ] 5 successful test flights
- [ ] Film day at Class G location
- [ ] Video editing (3 cuts: 30s, 60s, 3min)

---

## Execution Plan: 4 Tracks

### Track A: Make Simulation Flawless (1 week)

Goal: `pip install drone-swarm && dso simulate --drones 3` works on a clean machine.

| Day | Task | Hours |
|-----|------|-------|
| 1 | Fix telemetry loop auto-start on connect (it works in old src/ but not new SDK) | 3h |
| 1 | Run SITL integration test with 3 drones (not just 1) and verify telemetry flows | 3h |
| 2 | Build simple web-based map viewer (single HTML file, Leaflet.js, WebSocket from SDK) | 6h |
| 3 | Add `--visualize` flag to `dso simulate` that serves the map and opens browser | 4h |
| 3 | Test full flow on a clean Windows machine with WSL | 3h |
| 4 | Record asciinema GIF of the simulation for README | 2h |
| 4 | Fix any bugs from clean-machine testing | 3h |

**Exit criteria:** Someone with Python + WSL + ArduPilot SITL can run `dso simulate --drones 3 --visualize` and see 3 dots moving on a map in their browser within 5 minutes of install.

### Track B: Collision Avoidance (1 week)

Goal: `swarm.enable_collision_avoidance(min_distance_m=5)` prevents drones from hitting each other.

| Day | Task | Hours |
|-----|------|-------|
| 1 | Research velocity obstacle (VO) method — pick simplest variant | 2h |
| 1 | Implement `CollisionAvoidance` class with all-pairs distance check | 4h |
| 2 | Implement avoidance vector computation (repulsive force model) | 4h |
| 2 | Integrate with telemetry loop (check distances every cycle) | 3h |
| 3 | Write SITL test: 2 drones swap positions without collision | 4h |
| 3 | Write SITL test: 5 drones in tight formation maintain spacing | 4h |
| 4 | Add COLLISION_RISK event emission | 2h |
| 4 | Write unit tests (20+) for avoidance math | 4h |

**Exit criteria:** Two drones commanded to fly to each other's positions reroute automatically in SITL. Logged and verified.

### Track C: API Polish for Demo (3 days)

Goal: The API shown in the demo video works exactly as written.

| Day | Task | Hours |
|-----|------|-------|
| 1 | Add `swarm.formation("triangle")` convenience method (not just v_formation function) | 3h |
| 1 | Add `swarm.rotate(degrees, duration)` for formation rotation (the wow moment) | 4h |
| 2 | Add `swarm.takeoff(alt=N)` that takes off ALL drones with staggered timing | 2h |
| 2 | Add `swarm.land()` convenience (alias for rtl) | 1h |
| 2 | Verify the exact 12-line demo script works end-to-end in SITL | 3h |
| 3 | Update README with the verified demo script | 1h |
| 3 | Update examples/ with polished versions | 2h |

**Exit criteria:** The 12-line script shown in the video storyboard runs in SITL without modification.

### Track D: Hardware (parallel, your track)

| Task | When |
|------|------|
| Order parts from GetFPV + Amazon | THIS WEEK |
| Study Part 107 (1hr/day) | Ongoing |
| Schedule Part 107 exam | Within 2 weeks |
| Book makerspace Saturday | When parts arrive |
| Assemble + bench test 3 drones | 1 Saturday |
| First hover test | Following week |

---

## Priority Order

If time is limited, this is the order that matters:

1. **Fix telemetry auto-start** — without this, the SDK is broken (positions don't update)
2. **3-drone SITL integration test** — proves the core value proposition works
3. **Map visualization** — makes "dso simulate" jaw-dropping instead of boring
4. **Collision avoidance** — the feature that makes this genuinely novel
5. **API polish for demo script** — makes the video script work
6. **Demo video** — makes the world notice

Items 1-3 are what I can do right now. Item 4 is 1 week of focused work.
Items 5-6 depend on hardware arriving.

---

## Success Criteria

The product is "compelling" when someone can:

1. `pip install drone-swarm` (< 30 seconds)
2. `dso simulate --drones 5 --visualize` (< 2 minutes)
3. See 5 drones on a map in their browser
4. Write 10 lines of Python
5. Watch the drones fly a formation on the map
6. Think "I could build [my use case] on this"

That's the moment. Everything we build serves that 5-minute experience.
