---
title: Community Launch Plan
type: plan
status: draft
created: 2026-03-29
tags: [community, launch, marketing, discord]
---

# Community Launch Plan

## Discord Server Structure

### Server Name
**DSO — Drone Swarm Orchestrator**

### Channels

```
📢 INFORMATION
├── #welcome          — Auto-message: what DSO is, quickstart link, rules
├── #announcements    — Releases, breaking changes, events (admin-only post)
├── #rules            — Code of conduct + community guidelines
└── #roadmap          — Link to public roadmap, milestone updates

💬 COMMUNITY
├── #general          — Open discussion, introductions
├── #show-and-tell    — Share what you've built with DSO
├── #ideas            — Feature requests, use case brainstorms
└── #jobs             — Drone-related job postings (community)

🔧 SUPPORT
├── #help-sdk         — SDK usage questions, troubleshooting
├── #help-sitl        — SITL setup, WSL, ArduPilot issues
├── #help-hardware    — Hardware build, radio, ESC, flight controller
└── #bug-reports      — Link to GitHub Issues (direct reports there)

🚁 VERTICALS
├── #agriculture      — Precision ag, crop survey, spraying
├── #search-rescue    — SAR patterns, missing person operations
├── #inspection       — Infrastructure, pipeline, powerline
├── #drone-shows      — Light shows, choreography, entertainment
└── #defense          — ATAK, mesh networking, IFF (gated — verified only)

🛠️ DEVELOPMENT
├── #contributing     — Open issues, PR reviews, contributor onboarding
├── #architecture     — SDK design discussions, RFC proposals
└── #ci-cd            — Build notifications, test results (bot feed)
```

### Roles
- `@Maintainer` — Core team (you + Addison)
- `@Contributor` — Anyone with a merged PR
- `@Pilot` — Verified hardware testers
- `@Defense` — Gated access to #defense channel (verified affiliates)

### Bot: DSO-Bot
- Auto-role assignment on join
- Welcome DM with quickstart tutorial link
- GitHub webhook feed to #ci-cd
- Release announcements auto-posted from GitHub tags

---

## Community Guidelines (for #rules)

```
DSO Community Guidelines

1. Be respectful. No harassment, discrimination, or personal attacks.
2. Stay on topic. Use the right channel for your question.
3. No spam or self-promotion. One link to your project in #show-and-tell is fine.
4. Search before asking. Check docs, GitHub Issues, and channel history first.
5. Report bugs on GitHub. Use #bug-reports only to link your issue for discussion.
6. No ITAR/export-controlled content. Do not share classified or controlled information.
7. Safety first. Never fly without preflight checks. Never disable failsafes for demos.
8. Be patient. This is an open-source community. Responses may take time.

Violation of these guidelines may result in warnings, muting, or banning.
```

---

## Launch Blog Post (Draft)

### Title: "Introducing Drone Swarm: Stripe for Drones"

### Hook (First Paragraph)
What if coordinating a fleet of drones was as simple as calling an API?
Today we're open-sourcing **drone-swarm**, a Python SDK that turns
ArduPilot drones into a coordinated swarm with 10 lines of code.

### Body Outline

**The Problem:**
- Multi-drone coordination today requires 1000s of lines of MAVLink boilerplate
- No standard abstraction layer — every team reinvents the wheel
- Testing requires hardware or painful SITL setup
- Safety (geofencing, collision avoidance, failsafes) is afterthought code

**The Solution:**
- `pip install drone-swarm` → connected swarm in 5 minutes
- High-level API: `swarm.formation("v")`, `swarm.sweep(bounds)`
- Built-in SITL: `Swarm.simulate(n_drones=5)` — zero hardware needed
- Safety-first: preflight checks, geofencing, ORCA collision avoidance, emergency kill
- Extensible: behavior plugin system for custom swarm logic

**Code Example:**
```python
from drone_swarm import Swarm
import asyncio

async def main():
    swarm = Swarm()
    swarm.add("alpha", "udp:127.0.0.1:14550")
    swarm.add("bravo", "udp:127.0.0.1:14560")
    await swarm.connect()
    await swarm.takeoff(altitude=10)
    await swarm.formation("v", spacing=15)
    await swarm.sweep(bounds=[(35.36, -117.67), (35.37, -117.66)])
    await swarm.rtl()

asyncio.run(main())
```

**What's in the SDK (v0.2.0):**
- 25 modules, 532 tests, 0 lint errors
- Formation flying (V, line, circle, orbit, grid)
- Area sweep (Boustrophedon decomposition for arbitrary polygons)
- ORCA collision avoidance (not just repulsive — proper velocity obstacles)
- A* path planning with geofence constraints
- Wind estimation from tilt angles
- Battery prediction with Peukert correction
- Anomaly detection (compare-to-neighbors pattern)
- WebSocket telemetry server for external dashboards
- Flight logging with JSON export/replay
- Behavior plugin system (Brooks' subsumption-inspired lifecycle hooks)

**Who is this for:**
- Developers building drone applications
- Researchers studying swarm robotics
- Agriculture/inspection/SAR companies
- Defense integrators needing an open, auditable swarm layer
- Students learning autonomous systems

**What's Next:**
- Cloud dashboard with real-time fleet monitoring (Phase 2)
- Mission Builder API for composable flight plans
- Encrypted mesh networking (ESP32 + LoRa)
- Behavior marketplace for the community
- ATAK integration for defense use cases

**Call to Action:**
- `pip install drone-swarm`
- GitHub: github.com/YuYongJu/drone-swarm-orchestrator
- Docs: yuyongju.github.io/drone-swarm-orchestrator
- Discord: [link]
- Star the repo if this is useful

---

## Social Media Posts

### Hacker News (Show HN)

**Title:** Show HN: drone-swarm — Python SDK for multi-drone coordination

**Text:**
We built an open-source Python SDK that turns ArduPilot drones into a
coordinated swarm. Formation flying, area sweeps, collision avoidance,
and SITL simulation — all from pip install.

The idea is "Stripe for drones" — a clean API that hides the MAVLink
complexity. 10 lines of Python to get 3 drones flying in V-formation.

We're two college students at Northeastern building this as a startup.
The SDK is live on PyPI (v0.2.0, 532 tests). Cloud dashboard coming next.

Feedback welcome — especially from anyone working with ArduPilot or
drone fleets.

GitHub: [link]
Docs: [link]

### Reddit (r/ArduPilot, r/drones, r/Python, r/robotics)

**r/ArduPilot:**
"We built a Python SDK for multi-ArduPilot swarm coordination — would love
feedback from the community"

[Same content as HN, tailored: emphasize SITL testing, MAVLink internals,
ArduPilot compatibility]

**r/Python:**
"drone-swarm: async Python SDK for coordinating drone swarms (with ORCA
collision avoidance and A* path planning)"

[Emphasize the Python API design, async patterns, plugin architecture]

**r/robotics:**
"Open-source swarm orchestration SDK — formation control, collision
avoidance, and path planning for ArduPilot drones"

[Emphasize the algorithms: ORCA, Boustrophedon, consensus-based formation
control, anomaly detection]

---

## Launch Checklist

- [ ] Discord server created with channel structure above
- [ ] Community guidelines posted in #rules
- [ ] GitHub README links to Discord
- [ ] Blog post published (GitHub Pages or Medium)
- [ ] Demo video produced (SITL or hardware)
- [ ] HN post goes live (best time: Tuesday-Thursday, 10am EST)
- [ ] Reddit posts (stagger by 1 day: r/ArduPilot → r/Python → r/drones → r/robotics)
- [ ] Twitter/X announcement with GIF/video
- [ ] Monitor feedback for 48 hours, respond to all comments
- [ ] Triage any filed issues within 24 hours
