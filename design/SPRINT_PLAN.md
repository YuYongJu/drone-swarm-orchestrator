---
title: Sprint Plan
type: project-management
status: active
created: 2026-03-27
updated: 2026-03-27
tags: [drone-swarm, sprints, timeline, milestones]
---

# DSO Sprint Plan

**Sprint cadence:** 2 weeks
**Start date:** 2026-03-31 (Monday)
**Team size:** 1 (solo founder)
**Hours/week:** ~40 focused hours (student schedule)

---

## Timeline Overview

```
         MAR    APR         MAY         JUN         JUL         AUG
2026     ┃      ┃           ┃           ┃           ┃           ┃
         ┃  S1──S2──S3──S4──┃──S5──S6───┃──S7──S8───┃──S9──S10──┃
         ┃  ▲       ▲       ▲     ▲     ▲           ▲           ▲
         ┃  │       │       │     │     │           │           │
     NOW─┘  │       │       │     │     │           │           │
            │       │       │     │     │           │           │
         M0:Setup   │    M2:PyPI  │  M4:Real     M5:Cloud   M6:Launch
                 M1:SITL      M3:Hardware  Drones    Beta     v0.5
                   Demo        Arrives     Fly
```

| Milestone | Target Date | Sprint | Gate |
|-----------|-------------|--------|------|
| **M0: Project Setup** | Apr 4 | S1 | Repo public-ready, CI green |
| **M1: SITL Demo** | Apr 18 | S2 | `dso quickstart` works, demo script passes |
| **M2: PyPI + Docs** | May 2 | S3 | `pip install drone-swarm` works, docs site live |
| **M3: Hardware Arrives** | ~May 9 | S4 | 3 drones assembled and bench-tested |
| **M4: Real Drones Fly** | May 30 | S5-S6 | SDK controls 3 real drones, demo video filmed |
| **M5: Cloud Beta** | Jul 11 | S7-S8 | Telemetry dashboard live, first paid user |
| **M6: Launch v0.5** | Aug 8 | S9-S10 | HN launch, PX4 support, collision avoidance |

---

## Pre-Sprint (Now → Mar 30)

**Goal:** Close out current session work, order hardware, set up for Sprint 1.

- [ ] Order hardware from GetFPV + Amazon (~$700-800)
- [ ] Register for Part 107 test (schedule exam date)
- [ ] Create GitHub repo (private for now, public at M2)
- [ ] Set up GitHub Project board with columns: Backlog | Sprint | In Progress | Review | Done

---

## Sprint 1: Foundation (Mar 31 → Apr 11)

**Goal:** Repo is clean, CI is green, `drone_swarm/` package imports correctly.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 1.1 | Clean up `drone_swarm/` package — fix all imports, ensure each module loads | 4h | [ ] |
| 1.2 | Write `pyproject.toml` tests — `pip install -e .` works in clean venv | 2h | [ ] |
| 1.3 | Set up GitHub Actions CI: lint (ruff) + type check (mypy) + test (pytest) | 4h | [ ] |
| 1.4 | Write 20 unit tests for core modules (drone.py, config.py, missions.py math) | 8h | [ ] |
| 1.5 | Create AGPL-3.0 LICENSE file | 0.5h | [ ] |
| 1.6 | Create CONTRIBUTING.md with dev setup instructions | 2h | [ ] |
| 1.7 | Create CODE_OF_CONDUCT.md | 0.5h | [ ] |
| 1.8 | Create issue templates (bug report, feature request) | 1h | [ ] |
| 1.9 | Create PR template with checklist | 0.5h | [ ] |
| 1.10 | Set up MkDocs Material site skeleton with getting-started page | 4h | [ ] |
| 1.11 | Study for Part 107 (ongoing, 1hr/day) | 7h | [ ] |

**Sprint total:** ~34h
**Deliverable:** `pip install -e .` works, CI green, docs skeleton deployed to GitHub Pages.
**Gate for S2:** All CI checks pass on `main` branch.

---

## Sprint 2: SITL Demo (Apr 14 → Apr 25)

**Goal:** `dso quickstart` launches SITL and flies 3 simulated drones through formation demo.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 2.1 | Build `simulation.py` — spawn 3 ArduCopter SITL instances programmatically | 8h | [ ] |
| 2.2 | Build `dso` CLI entry point with `quickstart` and `simulate` commands | 6h | [ ] |
| 2.3 | Integration test: full arm → takeoff → formation → land cycle in SITL CI | 8h | [ ] |
| 2.4 | Fix swarm.py bugs from SITL testing (heartbeat, battery, GPS wait — build on fixes from this session) | 6h | [ ] |
| 2.5 | Write getting-started tutorial for docs ("Your First Swarm in 5 Minutes") | 4h | [ ] |
| 2.6 | Record `asciinema` terminal GIF of `dso quickstart` for README | 2h | [ ] |
| 2.7 | Study for Part 107 (ongoing) | 7h | [ ] |

**Sprint total:** ~41h (stretch sprint — core product work)
**Deliverable:** `dso quickstart` works end-to-end on a fresh machine with ArduPilot SITL.
**Gate for S3:** Demo script completes 5 consecutive runs without error.

---

## Sprint 3: PyPI + Docs + Pre-Launch (Apr 28 → May 9)

**Goal:** Published on PyPI, docs site live, README polished, repo goes public.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 3.1 | Publish v0.1.0 to PyPI (test on TestPyPI first) | 3h | [ ] |
| 3.2 | Write API reference docs (auto-generated from docstrings via mkdocstrings) | 6h | [ ] |
| 3.3 | Write 3 tutorial pages: quickstart, formations, custom missions | 6h | [ ] |
| 3.4 | Deploy docs to GitHub Pages via `mkdocs gh-deploy` | 2h | [ ] |
| 3.5 | Polish README: add GIF, badges (PyPI, downloads, license, CI), quickstart code | 4h | [ ] |
| 3.6 | Create 10 "Good First Issues" with clear descriptions | 3h | [ ] |
| 3.7 | Set up Discord server (6 channels: general, help, showcase, dev, announcements, off-topic) | 2h | [ ] |
| 3.8 | Enable GitHub Discussions | 0.5h | [ ] |
| 3.9 | Make repo PUBLIC | 0.5h | [ ] |
| 3.10 | Write "The State of Drone Swarm Software in 2026" blog post | 6h | [ ] |
| 3.11 | Submit to awesome-drones, awesome-drone lists | 1h | [ ] |
| 3.12 | Part 107 test (take exam if ready, otherwise continue studying) | 4h | [ ] |

**Sprint total:** ~38h
**Deliverable:** `pip install drone-swarm` works from PyPI. Docs live. Repo public. Blog post published.
**Gate for S4:** 3 people outside of you successfully `pip install drone-swarm` and run the demo.

---

## Sprint 4: Hardware Build (May 12 → May 23)

**Goal:** 3 drones assembled, bench-tested, firmware flashed, connected to SDK.

### Dependencies
- Hardware must have arrived by May 9 (order ASAP, allow 2 weeks shipping)
- Part 107 passed (or TRUST certificate as fallback)
- Book Northeastern EXP makerspace time (Saturdays)

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 4.1 | Unbox and inventory all parts — verify nothing missing | 2h | [ ] |
| 4.2 | Assemble Drone 1 (alpha) at makerspace: frame → motors → ESCs → PDB → FC → GPS → radio | 6h | [ ] |
| 4.3 | Flash ArduCopter firmware to Drone 1, configure params | 3h | [ ] |
| 4.4 | Bench test Drone 1: motor spin test, compass calibration, accel calibration | 2h | [ ] |
| 4.5 | Connect SDK to Drone 1 via telemetry radio — verify telemetry stream | 3h | [ ] |
| 4.6 | Assemble Drone 2 (bravo) | 5h | [ ] |
| 4.7 | Assemble Drone 3 (charlie) | 5h | [ ] |
| 4.8 | Flash + configure + bench test Drones 2 & 3 | 4h | [ ] |
| 4.9 | Connect all 3 drones to SDK simultaneously — verify swarm telemetry | 3h | [ ] |
| 4.10 | Update `demo.py` CONNECTION_STRINGS for real serial ports | 1h | [ ] |
| 4.11 | Install Remote ID modules on all 3 drones | 1h | [ ] |
| 4.12 | Pre-flight checklist dry run (no motors) | 1h | [ ] |

**Sprint total:** ~36h
**Deliverable:** 3 assembled drones, firmware flashed, connected to SDK, bench-tested.
**Gate for S5:** All 3 drones show CONNECTED status in `dso status` with valid GPS/battery telemetry.

---

## Sprint 5: First Flight (May 26 → Jun 6)

**Goal:** SDK controls 3 real drones in formation. Demo video filmed.

### Dependencies
- Part 107 certificate in hand (or TRUST certificate + recreational rules)
- Identified and scouted filming location (Class G airspace)
- Weather window (wind < 10 mph)
- Charged batteries (all 4)

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 5.1 | Scout filming location — drive to 2-3 candidate fields, check airspace on B4UFLY | 4h | [ ] |
| 5.2 | Flight Session 1 (REHEARSAL): Single drone hover test at 3m altitude | 3h | [ ] |
| 5.3 | Flight Session 2: Single drone full mission (takeoff → goto → RTL) via SDK | 3h | [ ] |
| 5.4 | Flight Session 3: 2-drone simultaneous takeoff and hover | 3h | [ ] |
| 5.5 | Flight Session 4: 3-drone formation flight (the full demo) | 4h | [ ] |
| 5.6 | Fix bugs discovered during real flights (expect 8-12h of debugging) | 10h | [ ] |
| 5.7 | Flight Session 5 (BACKUP): Re-fly any failed sessions | 3h | [ ] |
| 5.8 | Film demo video — Session 2 or 3 with camera setup | 4h | [ ] |
| 5.9 | Post-flight report: document what worked, what broke, calibration data | 2h | [ ] |

**Sprint total:** ~36h
**Deliverable:** 3 drones flying coordinated formation via SDK. Raw demo video footage.
**Gate for S6:** 3 consecutive successful formation flights. Raw video captured.

---

## Sprint 6: Video + Soft Launch (Jun 9 → Jun 20)

**Goal:** Demo video edited and published. Soft launch on ArduPilot community.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 6.1 | Edit demo video — 3 cuts (30s short, 60s main, 2-3min extended) | 8h | [ ] |
| 6.2 | Create terminal GIF from real demo (not SITL) for README | 2h | [ ] |
| 6.3 | Update README with real demo video/GIF | 2h | [ ] |
| 6.4 | Upload to YouTube (SEO title, description, tags) | 1h | [ ] |
| 6.5 | Soft launch: post on ArduPilot Discourse with technical write-up | 3h | [ ] |
| 6.6 | Soft launch: post on PX4 Discourse | 1h | [ ] |
| 6.7 | Soft launch: r/ArduPilot, r/diydrones | 1h | [ ] |
| 6.8 | Collect feedback, fix bugs, ship v0.1.1 patch | 8h | [ ] |
| 6.9 | Email 10 university robotics labs | 3h | [ ] |
| 6.10 | Email 3 drone media outlets (DroneDJ, The Drone Girl, sUAS News) | 2h | [ ] |
| 6.11 | Start v0.2 development: real hardware connection improvements based on flight testing | 6h | [ ] |

**Sprint total:** ~37h
**Deliverable:** Demo video live on YouTube. SDK in ArduPilot community's awareness.
**Gate for S7:** 50+ GitHub stars. 5+ external issues/PRs filed.

---

## Sprint 7: v0.2 + Cloud Foundation (Jun 23 → Jul 4)

**Goal:** Ship v0.2 (production-ready for real hardware). Start cloud backend.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 7.1 | Implement async API (`drone_swarm.aio`) | 8h | [ ] |
| 7.2 | Implement preflight safety checks (GPS, battery, compass, EKF) | 6h | [ ] |
| 7.3 | Implement emergency_stop + emergency_land with Ctrl+C handling | 4h | [ ] |
| 7.4 | Implement heartbeat failsafe with configurable behavior | 4h | [ ] |
| 7.5 | Test all of above on real hardware (3 flight sessions) | 8h | [ ] |
| 7.6 | Ship v0.2.0 to PyPI | 2h | [ ] |
| 7.7 | Set up cloud backend skeleton: FastAPI + PostgreSQL + auth | 6h | [ ] |
| 7.8 | Implement telemetry upload endpoint (opt-in from SDK) | 4h | [ ] |

**Sprint total:** ~42h (heavy sprint)
**Deliverable:** v0.2.0 on PyPI with real hardware support. Cloud backend skeleton.
**Gate for S8:** v0.2 passes 5 consecutive real hardware flight tests.

---

## Sprint 8: Cloud Dashboard MVP (Jul 7 → Jul 18)

**Goal:** Basic cloud dashboard showing live fleet telemetry.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 8.1 | Build dashboard frontend: Next.js + shadcn/ui + dark mode | 8h | [ ] |
| 8.2 | Live map with drone positions (Mapbox or Leaflet) | 6h | [ ] |
| 8.3 | Telemetry sidebar (battery, altitude, speed per drone) | 4h | [ ] |
| 8.4 | Fleet status overview page | 4h | [ ] |
| 8.5 | Deploy dashboard to Vercel | 2h | [ ] |
| 8.6 | Deploy backend API to Vercel/Railway | 2h | [ ] |
| 8.7 | Stripe integration for billing | 4h | [ ] |
| 8.8 | Write cloud docs: setup, pricing, API reference | 4h | [ ] |
| 8.9 | Beta test with 3-5 users from community | 6h | [ ] |

**Sprint total:** ~40h
**Deliverable:** Cloud dashboard live at app.dso.dev. First beta users.
**Gate for S9:** 3 beta users actively using dashboard with real or simulated drones.

---

## Sprint 9: v0.5 Features (Jul 21 → Aug 1)

**Goal:** Collision avoidance, PX4 support, events API.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 9.1 | Implement collision avoidance (velocity obstacle method) | 10h | [ ] |
| 9.2 | Implement PX4 SITL support via MAVLink abstraction | 8h | [ ] |
| 9.3 | Implement events/callback API (on_drone_lost, on_low_battery, etc.) | 6h | [ ] |
| 9.4 | Implement geofence enforcement in orchestrator | 4h | [ ] |
| 9.5 | Write tests for all new features (SITL integration tests) | 6h | [ ] |
| 9.6 | Update docs for v0.5 features | 4h | [ ] |
| 9.7 | Ship v0.5.0 to PyPI | 2h | [ ] |

**Sprint total:** ~40h
**Deliverable:** v0.5.0 with collision avoidance + PX4 + events.
**Gate for S10:** v0.5 passes 10-drone SITL test with collision avoidance active.

---

## Sprint 10: HN Launch (Aug 4 → Aug 15)

**Goal:** Full public launch. Hacker News front page. Maximum visibility.

### Tasks

| # | Task | Est. Hours | Done |
|---|------|-----------|------|
| 10.1 | Final repo polish — README, badges, GIFs all perfect | 4h | [ ] |
| 10.2 | Write all social media posts in advance (HN, Reddit x5, Twitter thread, LinkedIn) | 4h | [ ] |
| 10.3 | Prepare press emails to 5 drone media outlets | 2h | [ ] |
| 10.4 | **LAUNCH DAY (Tuesday 11 AM ET):** HN Show HN → Twitter → Reddit → LinkedIn | 4h | [ ] |
| 10.5 | Respond to every comment/issue for 48 hours straight | 16h | [ ] |
| 10.6 | Ship v0.5.1 hotfix based on launch feedback | 4h | [ ] |
| 10.7 | Product Hunt launch (1 week after HN) | 3h | [ ] |
| 10.8 | Write launch retrospective blog post | 3h | [ ] |

**Sprint total:** ~40h
**Deliverable:** Front page HN (goal). 500+ GitHub stars. 1,000+ PyPI downloads.
**Gate:** Community exists and is growing week-over-week.

---

## Post-Launch Sprints (Aug 18+)

| Sprint | Focus | Key Deliverable |
|--------|-------|----------------|
| S11-S12 | v0.6 — Plugin system + Jupyter widgets | Extensible SDK, notebook DX |
| S13-S14 | v0.7 — Cloud mission planner + analytics | Visual mission builder |
| S15-S16 | v0.8 — SBIR applications (AFWERX, NSF) | Grant submissions |
| S17-S18 | v0.9 — Enterprise features (RBAC, audit logging) | First enterprise pilot |
| S19-S20 | v1.0 — API freeze, stability, comprehensive testing | Stable release |

---

## Velocity Tracking

Update this table at the end of each sprint:

| Sprint | Planned Hrs | Actual Hrs | Tasks Done | Tasks Slipped | Notes |
|--------|-------------|------------|------------|---------------|-------|
| S1 | 34h | — | —/11 | — | |
| S2 | 41h | — | —/7 | — | |
| S3 | 38h | — | —/12 | — | |
| S4 | 36h | — | —/12 | — | |
| S5 | 36h | — | —/9 | — | |
| S6 | 37h | — | —/11 | — | |
| S7 | 42h | — | —/8 | — | |
| S8 | 40h | — | —/9 | — | |
| S9 | 40h | — | —/7 | — | |
| S10 | 40h | — | —/8 | — | |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Hardware delayed > 3 weeks | Shifts S4-S6 by 2 weeks | Medium | Order ASAP, have backup Amazon Prime items |
| Part 107 exam failed | Can't fly legally | Low | Study 1hr/day, use TRUST cert as fallback for recreational |
| Drone crash destroys hardware | $200 per drone to replace | High | Buy spare props, spare frame arm, fly low (3m) initially |
| SITL CI flaky in GitHub Actions | Slows all development | Medium | Docker-based SITL, retry logic, local testing as backup |
| No community traction at launch | Delayed revenue, motivation hit | Medium | Soft launch to ArduPilot community first for validation |
| Weather prevents filming | Delays demo video by weeks | Medium | Plan 3 session windows, have indoor SITL demo as backup |
| Burnout (solo founder + student) | Everything stalls | Medium | Protect weekends, skip sprints if needed, this is a marathon |

---

## Key Dates (External)

| Date | Event | Action |
|------|-------|--------|
| May 13-19 | PyCon US (Long Beach) | Attend if possible, network |
| Sep 22-24 | ROSCon (Toronto) | Submit lightning talk by CFP deadline |
| October | ArduPilot Dev Conf (Ottawa) | Demo SDK to core team |
| Rolling | AFWERX Open Topic SBIR | Submit when v0.2 is proven on hardware |

---

*Update this document at the start of each sprint (Monday) and end of each sprint (Friday).
Move slipped tasks to the next sprint. Celebrate completed milestones.*
