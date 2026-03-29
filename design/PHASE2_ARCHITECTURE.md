---
title: Phase 2 Implementation Architecture
type: design
status: draft
created: 2026-03-29
tags: [phase-2, cloud-dashboard, api, architecture]
---

# Phase 2: Cloud Dashboard + SDK v1.0 — Implementation Architecture

**Goal:** Launch the paid cloud platform with fleet dashboard, telemetry
analytics, REST/WebSocket API, and Mission Builder API.

**Builds on:** SYSTEM_ARCHITECTURE.md, UI_DESIGN.md, ROADMAP.md Phase 2

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js 16 (App Router) | SSR, React Server Components, Vercel deploy |
| UI Framework | shadcn/ui + Tailwind CSS | Matches UI_DESIGN.md dark theme, Geist fonts |
| Map | Mapbox GL JS | 3D terrain, real-time markers, drawing tools |
| State | Zustand + React Query | Lightweight, works with SSR and WebSocket |
| Backend API | FastAPI (Python) | Same language as SDK, async-native, auto OpenAPI |
| WebSocket | FastAPI WebSocket + SDK TelemetryServer | Real-time telemetry bridge |
| Database | Neon Postgres (via Vercel Marketplace) | Serverless, branching, familiar SQL |
| Cache | Upstash Redis (via Vercel Marketplace) | Session cache, rate limiting, pub/sub |
| Auth | Clerk (via Vercel Marketplace) | Pre-built UI, middleware, team/org support |
| Payments | Stripe | Subscriptions, usage metering, invoices |
| Hosting | Vercel (frontend) + Fly.io or Railway (backend) | Frontend on Vercel, Python backend needs long-running WebSockets |
| CI/CD | GitHub Actions | Already configured for SDK |

### Why Split Frontend/Backend?

The SDK is Python. The cloud dashboard needs persistent WebSocket connections
to ground stations running the SDK. A Python backend (FastAPI) acts as the
bridge between the SDK's telemetry stream and the web frontend. The Next.js
frontend connects to the FastAPI backend via REST + WebSocket.

```
Browser (Next.js)  ←── REST/WS ───→  FastAPI Backend  ←── WS ───→  SDK (field)
                                          │
                                     Neon Postgres
                                     Upstash Redis
```

---

## Project Structure

```
drone-swarm-cloud/               # New repo (or monorepo with SDK)
├── apps/
│   ├── web/                     # Next.js 16 frontend
│   │   ├── app/
│   │   │   ├── (auth)/          # Clerk auth pages
│   │   │   │   ├── sign-in/
│   │   │   │   └── sign-up/
│   │   │   ├── (dashboard)/     # Authenticated dashboard routes
│   │   │   │   ├── fleet/       # Fleet overview — list + map
│   │   │   │   ├── missions/    # Mission planner + history
│   │   │   │   ├── telemetry/   # Live telemetry dashboard
│   │   │   │   ├── analytics/   # Battery curves, flight trends
│   │   │   │   ├── alerts/      # Alert configuration + history
│   │   │   │   └── settings/    # Team, billing, API keys
│   │   │   ├── api/             # Next.js route handlers (auth proxy)
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx         # Landing / marketing page
│   │   ├── components/
│   │   │   ├── map/             # MapView, DroneMarker, GeofenceOverlay
│   │   │   ├── telemetry/       # TelemetryCard, HealthGauge, BatteryChart
│   │   │   ├── mission/         # MissionTimeline, WaypointList, MissionFeed
│   │   │   └── ui/              # shadcn/ui components
│   │   ├── lib/
│   │   │   ├── api.ts           # REST client (typed, generated from OpenAPI)
│   │   │   ├── ws.ts            # WebSocket client for real-time telemetry
│   │   │   └── stores/          # Zustand stores (fleet, telemetry, mission)
│   │   └── proxy.ts             # Clerk middleware (Next.js 16)
│   │
│   └── api/                     # FastAPI backend
│       ├── main.py              # FastAPI app, CORS, lifespan
│       ├── routers/
│       │   ├── fleet.py         # /fleet — CRUD drones, status
│       │   ├── missions.py      # /missions — create, list, replay
│       │   ├── telemetry.py     # /telemetry — history queries
│       │   ├── alerts.py        # /alerts — config, history
│       │   ├── auth.py          # /auth — Clerk JWT verification
│       │   └── billing.py       # /billing — Stripe webhooks, usage
│       ├── ws/
│       │   ├── telemetry_hub.py # WebSocket hub: SDK → browser fanout
│       │   └── ground_link.py   # Inbound WS from field ground stations
│       ├── models/              # SQLAlchemy / Pydantic models
│       │   ├── drone.py
│       │   ├── mission.py
│       │   ├── telemetry.py
│       │   └── alert.py
│       ├── services/
│       │   ├── telemetry_ingest.py  # Buffer, downsample, persist
│       │   ├── alert_engine.py      # Evaluate rules, dispatch
│       │   └── usage_meter.py       # Track drone-minutes for billing
│       └── db.py                # Neon Postgres connection
│
├── packages/
│   └── shared/                  # Shared types (TypeScript ↔ Python)
│       ├── telemetry.ts         # TelemetryMessage type
│       └── telemetry.py         # Matching Pydantic model
│
├── turbo.json                   # Turborepo config
├── package.json                 # Workspace root
└── docker-compose.yml           # Local dev: Postgres + Redis
```

---

## REST API Design

Base URL: `https://api.droneswarm.dev/v1`

### Fleet

| Method | Path | Description |
|--------|------|-------------|
| GET | `/fleet` | List all drones for the team |
| POST | `/fleet` | Register a new drone |
| GET | `/fleet/{drone_id}` | Get drone details + latest telemetry |
| PATCH | `/fleet/{drone_id}` | Update drone config (name, role, etc.) |
| DELETE | `/fleet/{drone_id}` | Remove drone from fleet |
| GET | `/fleet/{drone_id}/telemetry` | Historical telemetry (paginated) |
| GET | `/fleet/{drone_id}/health` | Health score history |

### Missions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/missions` | List missions (filter by status, date) |
| POST | `/missions` | Create a new mission |
| GET | `/missions/{id}` | Get mission details + waypoints |
| POST | `/missions/{id}/start` | Dispatch mission to ground station |
| POST | `/missions/{id}/abort` | Abort running mission |
| GET | `/missions/{id}/replay` | Get telemetry replay data |
| GET | `/missions/templates` | List saved mission templates |
| POST | `/missions/templates` | Save a mission as a template |

### Alerts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/alerts` | List alert history |
| GET | `/alerts/rules` | List configured alert rules |
| POST | `/alerts/rules` | Create alert rule |
| PATCH | `/alerts/rules/{id}` | Update alert rule |
| DELETE | `/alerts/rules/{id}` | Delete alert rule |
| POST | `/alerts/{id}/ack` | Acknowledge an alert |

### Billing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/billing/usage` | Current period usage summary |
| GET | `/billing/invoices` | Invoice history |
| POST | `/billing/portal` | Get Stripe customer portal URL |

### Auth

All endpoints require `Authorization: Bearer <clerk_jwt>`.
Team/org scoping via Clerk's `orgId` claim in the JWT.

---

## WebSocket Protocol

### Browser → Backend (control)

```
ws://api.droneswarm.dev/v1/ws/telemetry

→ Client sends:
{ "type": "subscribe", "drone_ids": ["alpha", "bravo"] }
{ "type": "unsubscribe", "drone_ids": ["alpha"] }

← Server sends (10 Hz per drone):
{
  "type": "telemetry",
  "ts": 1711612800.123,
  "drone_id": "alpha",
  "lat": 35.363261, "lon": -117.669056, "alt": 10.0,
  "heading": 90.0, "battery_pct": 95.0, "status": "airborne",
  "health_score": 92.0, "gps_sats": 12,
  "roll": 0.01, "pitch": -0.003, "yaw": 1.57,
  "current_a": 8.2, "voltage": 14.1
}

← Server sends (event):
{
  "type": "alert",
  "ts": 1711612810.0,
  "drone_id": "bravo",
  "alert_type": "low_battery",
  "message": "Battery at 18%, below RTL threshold"
}
```

### Ground Station → Backend (telemetry ingest)

```
ws://api.droneswarm.dev/v1/ws/ground

→ Ground station authenticates:
{ "type": "auth", "api_key": "dso_live_..." }

→ Ground station streams (forwarded from SDK TelemetryServer):
{
  "type": "telemetry",
  "timestamp": 1711612800.0,
  "drones": {
    "alpha": { "lat": ..., "lon": ..., ... },
    "bravo": { "lat": ..., "lon": ..., ... }
  }
}
```

This mirrors the existing `TelemetryServer` wire format from M3,
so ground stations just forward the SDK's WebSocket output.

---

## Mission Builder API (SDK Addition)

New module: `drone_swarm/mission_builder.py`

```python
from drone_swarm import Mission, Waypoint

# Fluent builder pattern
mission = (
    Mission.build("Pipeline Inspection Run 47")
    .add_waypoint(35.363, -117.669, alt=20)
    .add_waypoint(35.365, -117.665, alt=20)
    .set_formation("line", spacing=10)
    .set_geofence(polygon=CORRIDOR, alt_max=50)
    .set_speed(5.0)  # m/s cruise speed
    .on_complete("rtl")
    .validate()  # raises if invalid
)

# Execute
await swarm.run_mission(mission)

# Save/load
mission.save_json("missions/pipeline_47.json")
loaded = Mission.load_json("missions/pipeline_47.json")

# Export to QGC
mission.export_qgc("pipeline_47.waypoints")
```

### Mission Schema (JSON)

```json
{
  "name": "Pipeline Inspection Run 47",
  "version": "1.0",
  "created": "2026-03-29T01:00:00Z",
  "waypoints": [
    {"lat": 35.363, "lon": -117.669, "alt": 20},
    {"lat": 35.365, "lon": -117.665, "alt": 20}
  ],
  "formation": {"pattern": "line", "spacing": 10},
  "geofence": {
    "polygon": [[35.36, -117.67], ...],
    "alt_max_m": 50
  },
  "speed_ms": 5.0,
  "on_complete": "rtl",
  "drones": null
}
```

---

## Database Schema (Postgres)

```sql
-- Teams (synced from Clerk)
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_org_id TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    plan        TEXT DEFAULT 'free',  -- free, pro, enterprise
    stripe_customer_id TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Drones registered to a team
CREATE TABLE drones (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id         UUID REFERENCES teams(id) ON DELETE CASCADE,
    drone_id        TEXT NOT NULL,  -- user-facing ID ("alpha")
    connection_str  TEXT,
    role            TEXT DEFAULT 'recon',
    hw_class        TEXT DEFAULT 'A',
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (team_id, drone_id)
);

-- Telemetry samples (time-series, partitioned by month)
CREATE TABLE telemetry (
    id          BIGSERIAL,
    drone_pk    UUID REFERENCES drones(id) ON DELETE CASCADE,
    ts          TIMESTAMPTZ NOT NULL,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    alt         REAL,
    heading     REAL,
    battery_pct REAL,
    health_score REAL,
    gps_sats    SMALLINT,
    voltage     REAL,
    current_a   REAL,
    status      TEXT,
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

-- Missions
CREATE TABLE missions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id     UUID REFERENCES teams(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    status      TEXT DEFAULT 'planned',  -- planned, active, completed, aborted
    mission_json JSONB NOT NULL,  -- full Mission schema
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Alert rules
CREATE TABLE alert_rules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id     UUID REFERENCES teams(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    condition   JSONB NOT NULL,  -- {"metric": "battery_pct", "op": "<", "value": 20}
    action      TEXT DEFAULT 'webhook',  -- webhook, email, sms
    target      TEXT,  -- URL, email address, phone
    enabled     BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Alert history
CREATE TABLE alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id     UUID REFERENCES alert_rules(id),
    drone_pk    UUID REFERENCES drones(id),
    message     TEXT NOT NULL,
    severity    TEXT DEFAULT 'warning',
    acked       BOOLEAN DEFAULT false,
    acked_by    TEXT,
    fired_at    TIMESTAMPTZ DEFAULT now()
);

-- Usage metering (for billing)
CREATE TABLE usage_records (
    id          BIGSERIAL PRIMARY KEY,
    team_id     UUID REFERENCES teams(id),
    drone_pk    UUID REFERENCES drones(id),
    period      DATE NOT NULL,  -- billing day
    drone_minutes REAL DEFAULT 0,
    api_calls   INTEGER DEFAULT 0,
    telemetry_bytes BIGINT DEFAULT 0,
    UNIQUE (team_id, drone_pk, period)
);
```

---

## Billing Model

| Tier | Price | Includes | Overage |
|------|-------|----------|---------|
| **Free** | $0 | 1 drone, 7-day telemetry, 1K API calls/day | Hard limit |
| **Pro** | $29/mo | 10 drones, 90-day telemetry, 50K API calls/day, alerts | $0.01/drone-min |
| **Enterprise** | Custom | Unlimited drones, 1-year retention, SLA, SSO | Negotiated |

Usage metering via Stripe's metered billing:
- Track `drone_minutes` per team per day
- Report to Stripe at end of billing period
- Overage billed on next invoice

---

## Build Order

### Sprint 1 (Week 1-2): Foundation
1. Scaffold monorepo (Turborepo + Next.js + FastAPI)
2. Set up Neon Postgres + migrations
3. Clerk auth integration (sign-up, sign-in, team/org)
4. FastAPI skeleton with JWT verification
5. Fleet CRUD (REST endpoints + database)
6. Basic dashboard shell (sidebar, nav, fleet list page)

### Sprint 2 (Week 3-4): Real-Time
7. WebSocket telemetry hub (ground station → backend → browser)
8. Map component (Mapbox GL + drone markers)
9. Live telemetry cards (battery, GPS, status per drone)
10. Health gauge component
11. Mission Feed component (from UI_DESIGN.md)

### Sprint 3 (Week 5-6): Missions
12. Mission Builder API (SDK module: `mission_builder.py`)
13. Mission planner UI (drag waypoints on map, formation picker)
14. Mission dispatch (send to ground station via WebSocket)
15. Mission history + replay
16. Mission templates (save/load)

### Sprint 4 (Week 7-8): Analytics + Alerts
17. Telemetry analytics (battery curves, flight time trends)
18. Alert rule engine (backend)
19. Alert configuration UI
20. Webhook delivery for alerts
21. Usage metering + Stripe integration
22. Billing settings page (upgrade, portal link)

### Sprint 5 (Week 9-10): Polish + Launch
23. Landing page / marketing site
24. API documentation (auto-generated from OpenAPI)
25. Rate limiting (Upstash Redis)
26. Error handling, loading states, empty states
27. Performance optimization (telemetry downsampling)
28. Beta launch to early users

---

## Key Design Decisions to Make

| Decision | Options | Recommendation | Why |
|----------|---------|---------------|-----|
| Monorepo vs separate repos | Single repo vs SDK repo + cloud repo | **Separate repos** | SDK is open source (MIT), cloud is proprietary |
| Backend hosting | Vercel (Python runtime) vs Fly.io vs Railway | **Fly.io** | Long-running WebSocket connections; Vercel's function timeout limits don't work for persistent WS |
| Map provider | Mapbox GL vs Leaflet vs Google Maps | **Mapbox GL** | 3D terrain, custom styling, performant for many markers |
| ORM | SQLAlchemy vs Prisma (via Edge) vs raw SQL | **SQLAlchemy** | Python-native, async support, same language as SDK |
| Frontend state | Zustand vs Redux vs Jotai | **Zustand** | Minimal boilerplate, works well with WebSocket updates |

---

*This document will be refined through design review before Sprint 1 begins.*
