# Gap Audit -- Post-Sprint 2

**Date:** 2026-03-28
**Auditor:** Automated code audit (read-only)
**Scope:** SDK repo (`drone-swarm-orchestrator`) + Cloud Dashboard repo (`drone-swarm-cloud`)

---

## Critical (must fix before beta)

### SDK

- **[FRONTEND/BACKEND TYPE MISMATCH] Frontend sends wrong field names to backend API**
  The frontend `api.ts` defines `CreateDronePayload` with `connection_string` and `hardware_class`, but the backend schema `DroneCreate` expects `connection_str` and `hw_class`. Every "Register Drone" form submission will silently drop those fields (Pydantic ignores unknown keys by default) or fail. The `Drone` interface in `api.ts` also uses `hardware_class` where the backend returns `hw_class`.
  - Frontend: `C:/Users/User/drone-swarm-cloud/apps/web/src/lib/api.ts` lines 11, 17, 22, 24
  - Backend schema: `C:/Users/User/drone-swarm-cloud/apps/api/schemas/drone.py` lines 9, 11
  - Backend model: `C:/Users/User/drone-swarm-cloud/apps/api/models/drone.py` lines 28, 30

- **[FRONTEND TYPE MISMATCH] Fleet page reads fields that the API never returns**
  The `Drone` interface in `api.ts` expects `status`, `battery_pct`, `gps_sats`, `health_score`, and `last_seen` fields. The backend `DroneResponse` schema only returns `id`, `team_id`, `drone_id`, `connection_str`, `role`, `hw_class`, `created_at`, `updated_at`. The fleet table will render `--` for every live-data column because those fields are always `null`/missing.
  - Frontend: `C:/Users/User/drone-swarm-cloud/apps/web/src/lib/api.ts` lines 8-14
  - Backend schema: `C:/Users/User/drone-swarm-cloud/apps/api/schemas/drone.py` lines 22-32
  - Fleet page: `C:/Users/User/drone-swarm-cloud/apps/web/src/app/(dashboard)/fleet/page.tsx` lines 289-340

- **[CLOUD -- NO AUTH] All API endpoints are completely unauthenticated**
  Both routers (`fleet.py`, `missions.py`) use a hardcoded `DEFAULT_TEAM_ID`. There is no auth middleware, no JWT verification, no Clerk integration. Anyone can CRUD any team's drones and missions. The PHASE2_ARCHITECTURE.md specifies `Authorization: Bearer <clerk_jwt>` on all endpoints.
  - `C:/Users/User/drone-swarm-cloud/apps/api/routers/fleet.py` line 13-15
  - `C:/Users/User/drone-swarm-cloud/apps/api/routers/missions.py` line 13-14
  - Missing: `routers/auth.py` (specified in PHASE2_ARCHITECTURE.md line 89)

- **[CLOUD -- NO TESTS] Zero tests in the entire cloud dashboard repo**
  There are no test files anywhere in `drone-swarm-cloud`. The `pyproject.toml` lists `pytest` and `httpx` as dev dependencies but they are unused. No frontend tests either (no vitest, jest, or playwright config).
  - Missing: `apps/api/tests/` directory
  - Missing: `apps/web/__tests__/` or similar

- **[CLOUD -- NO CI/CD] No GitHub Actions or any CI pipeline**
  The cloud repo has no `.github/` directory at all. No linting, no type checking, no tests run on push/PR. The SDK repo has good CI (`ci.yml` with lint, security, test matrix, smoke) but the cloud repo has nothing.
  - Missing: `C:/Users/User/drone-swarm-cloud/.github/workflows/`

### Both Repos

- **[SDK -- `requirements.txt` stale and contradicts `pyproject.toml`]**
  `requirements.txt` lists `aiofiles>=23.0`, `fastapi>=0.110.0`, `uvicorn>=0.27.0` -- none of which are in `pyproject.toml` dependencies. The SDK's `pyproject.toml` correctly lists only `pymavlink>=2.4.40` as a core dependency. The stale `requirements.txt` could confuse contributors or deployment scripts.
  - `C:/Users/User/drone-swarm-orchestrator/requirements.txt` (entire file)
  - `C:/Users/User/drone-swarm-orchestrator/pyproject.toml` lines 27-29

---

## Important (fix soon)

### Cloud Dashboard

- **[CLOUD -- CORS wide open] CORS allows all methods and all headers**
  The `CORSMiddleware` config uses `allow_methods=["*"]` and `allow_headers=["*"]`. While `allow_origins` is restricted to `settings.CORS_ORIGINS`, the wildcard methods/headers weaken the CORS posture. Should restrict to actual methods used (`GET, POST, PATCH, DELETE, OPTIONS`).
  - `C:/Users/User/drone-swarm-cloud/apps/api/main.py` lines 56-62

- **[CLOUD -- No rate limiting] No rate limiting on any endpoint**
  PHASE2_ARCHITECTURE.md specifies Upstash Redis for rate limiting (Sprint 5, item 25). Currently there is zero rate limiting. A single client could hammer the fleet/missions endpoints or flood the WebSocket hub. This is a DDoS and abuse vector.
  - Entire `C:/Users/User/drone-swarm-cloud/apps/api/` directory

- **[CLOUD -- WebSocket hub holds lock during broadcast]**
  `TelemetryHub.broadcast()` acquires `self._lock` to copy the client list, then releases it. However, individual `send_text()` calls can block, and stale client cleanup re-acquires the lock. Under high client counts with slow connections, this could introduce latency spikes. Consider a non-blocking broadcast pattern or asyncio.gather with return_exceptions.
  - `C:/Users/User/drone-swarm-cloud/apps/api/ws/telemetry_hub.py` lines 86-108

- **[CLOUD -- WebSocket has no auth] WebSocket endpoint accepts any connection**
  The `/v1/ws/telemetry` endpoint has no authentication check. In production, any client that knows the URL can subscribe to all drone telemetry. The PHASE2_ARCHITECTURE.md specifies auth for the ground station link but the browser WS also needs token validation.
  - `C:/Users/User/drone-swarm-cloud/apps/api/main.py` lines 75-78

- **[CLOUD -- Missing NEXT_PUBLIC_WS_URL in .env.example]**
  The `use-telemetry.ts` hook reads `NEXT_PUBLIC_WS_URL` but this variable is not listed in `.env.example`. Developers setting up the project will get the hardcoded `ws://localhost:8000` default, which works for local dev but the variable should be documented.
  - `C:/Users/User/drone-swarm-cloud/apps/web/src/lib/use-telemetry.ts` line 19
  - `C:/Users/User/drone-swarm-cloud/.env.example` (missing entry)

- **[CLOUD -- 4 placeholder pages] Missions, Alerts, Analytics, Settings are all "Coming soon"**
  Four of six dashboard pages contain only a card with "Coming soon" text. They have no loading states, no empty states, no error handling -- just static placeholder content. Per PHASE2_ARCHITECTURE.md Sprint 2 scope, Mission Feed should be functional by now.
  - `C:/Users/User/drone-swarm-cloud/apps/web/src/app/(dashboard)/missions/page.tsx`
  - `C:/Users/User/drone-swarm-cloud/apps/web/src/app/(dashboard)/alerts/page.tsx`
  - `C:/Users/User/drone-swarm-cloud/apps/web/src/app/(dashboard)/analytics/page.tsx`
  - `C:/Users/User/drone-swarm-cloud/apps/web/src/app/(dashboard)/settings/page.tsx`

- **[CLOUD -- Missing API endpoints from architecture spec]**
  PHASE2_ARCHITECTURE.md defines these routers/endpoints that do not exist:
  - `routers/telemetry.py` -- `/fleet/{drone_id}/telemetry` (historical), `/fleet/{drone_id}/health`
  - `routers/alerts.py` -- `/alerts`, `/alerts/rules` CRUD, `/alerts/{id}/ack`
  - `routers/billing.py` -- `/billing/usage`, `/billing/invoices`, `/billing/portal`
  - `routers/auth.py` -- JWT verification middleware
  - `ws/ground_link.py` -- inbound WS from field ground stations
  - `services/telemetry_ingest.py`, `services/alert_engine.py`, `services/usage_meter.py`
  - `models/telemetry.py`, `models/alert.py`
  - Missions router is missing: `POST /missions/{id}/start`, `POST /missions/{id}/abort`, `GET /missions/{id}/replay`, templates endpoints

- **[CLOUD -- No Alembic migrations configured]**
  The `migrations/versions/` directory is empty. The app uses `Base.metadata.create_all` in the lifespan handler (dev convenience), but there is no Alembic `env.py` or `alembic.ini`. Database schema evolution will require manual intervention.
  - `C:/Users/User/drone-swarm-cloud/apps/api/migrations/versions/` (empty)

- **[CLOUD -- Missions router missing PATCH/DELETE]**
  The missions router only has `GET /`, `POST /`, and `GET /{id}`. There is no `PATCH` for updating a mission or `DELETE` for removing one. The fleet router has full CRUD but missions is incomplete.
  - `C:/Users/User/drone-swarm-cloud/apps/api/routers/missions.py` (only 3 endpoints)

### SDK

- **[SDK -- No dedicated test for `geo.py` module]**
  The `geo.py` module (haversine, offset_gps, meters_per_deg_lon) is used by 5 other modules but has no dedicated test file. The functions are tested indirectly through other module tests (collision, path_planner, etc.) but edge cases like polar coordinates, antipodal points, and zero-distance are not covered.
  - Missing: `tests/test_geo.py`
  - Used by: collision.py, anomaly.py, allocation.py, path_planner.py, swarm.py

- **[SDK -- No dedicated test for `viz.py` module]**
  The `viz.py` module (start_map_server, MAP_HTML template, SSE endpoint) has no test file. It uses raw HTTP server threading and string interpolation for SSE data -- both worth testing.
  - Missing: `tests/test_viz.py`
  - Module: `C:/Users/User/drone-swarm-orchestrator/drone_swarm/viz.py`

- **[SDK -- `mission_builder.py` not wired to `run_mission()`]**
  The `Mission` and `MissionBuilder` classes are exported in `__init__.py`, and there is a test file (`test_mission_builder.py`). However, `SwarmOrchestrator` does not have a `run_mission()` method as specified in PHASE2_ARCHITECTURE.md. The mission builder can build and serialize missions but cannot execute them through the swarm.
  - `C:/Users/User/drone-swarm-orchestrator/drone_swarm/swarm.py` -- no `run_mission` method
  - PHASE2_ARCHITECTURE.md line 249: `await swarm.run_mission(mission)`

- **[SDK -- Swarm methods raise KeyError for unknown drone_id]**
  Multiple methods (`goto`, `return_to_launch`, `land`, `assign_mission`) directly index `self.drones[drone_id]` without checking if the key exists. An unknown drone_id produces a raw `KeyError` with no helpful message. Public API methods should raise `ValueError` or a custom error.
  - `C:/Users/User/drone-swarm-orchestrator/drone_swarm/swarm.py` lines 482, 517, 543, 697

- **[SDK -- examples require running SITL but no guidance on Windows setup]**
  `basic_swarm.py` instructions say "start 3 ArduCopter instances" using `sim_vehicle.py` but do not mention WSL. On Windows (this user's platform), SITL must run in WSL. The `simulate.py` example handles this via `SimulationHarness` but `basic_swarm.py` uses manual SITL with TCP connections that may not work cross-WSL without port forwarding.
  - `C:/Users/User/drone-swarm-orchestrator/examples/basic_swarm.py` lines 8-12

---

## Nice-to-have (backlog)

### Cloud Dashboard

- **[CLOUD -- No `packages/shared` for types]** PHASE2_ARCHITECTURE.md specifies a `packages/shared/` directory with matching TypeScript and Python type definitions for telemetry messages. Currently, types are defined independently in both codebases and have already drifted (see Critical type mismatch above).

- **[CLOUD -- No Zustand stores]** PHASE2_ARCHITECTURE.md specifies Zustand for state management. Currently the fleet page uses local `useState` and the telemetry page uses a custom WebSocket hook. This works but won't scale as pages need to share state.

- **[CLOUD -- No Mapbox integration]** PHASE2_ARCHITECTURE.md specifies Mapbox GL JS for the map. The telemetry page uses a custom SVG position grid instead. This is functional for dev but should be replaced with a real map before beta.

- **[CLOUD -- No `docker-compose.yml` for local dev]** PHASE2_ARCHITECTURE.md specifies Docker Compose for local Postgres + Redis. Currently the API uses SQLite via aiosqlite. This is fine for dev but the production path requires Postgres testing.

- **[CLOUD -- Telemetry sim status values don't match SDK enums]** The telemetry simulator uses `"rtl"` and `"landing"` as status strings, but the SDK's `DroneStatus` enum uses `"returning"` and `"landing"`. The `"rtl"` value is not a valid SDK status and could confuse the frontend.
  - `C:/Users/User/drone-swarm-cloud/apps/api/ws/telemetry_sim.py` line 107

- **[CLOUD -- No error boundary in dashboard layout]** If any dashboard page throws during render, the entire app crashes. A React error boundary in the dashboard layout would provide graceful degradation.

### SDK

- **[SDK -- `__all__` includes internal symbols]** `BehaviorRegistry`, `optimal_assign`, and `replan_optimal` are listed in `__all__` but marked as "Internal" in `API_STABILITY.md`. The stability doc says these "may be removed from `__all__` in a future release" -- should clean this up.
  - `C:/Users/User/drone-swarm-orchestrator/drone_swarm/__init__.py` lines 101-175
  - `C:/Users/User/drone-swarm-orchestrator/API_STABILITY.md` lines 146-155

- **[SDK -- No CHANGELOG.md]** The API_STABILITY.md references deprecation warnings and changelog entries, but there is no CHANGELOG.md file in the repo. Needed before v1.0.

- **[SDK -- License mismatch]** README.md says "MIT License" and LICENSE file contains MIT. But ROADMAP.md line 108 says "Apache 2.0 license". These should be consistent.
  - `C:/Users/User/drone-swarm-orchestrator/README.md` line 86
  - `C:/Users/User/drone-swarm-orchestrator/design/ROADMAP.md` line 108

- **[SDK -- CI does not run benchmarks or SITL tests]** The CI pipeline runs unit tests but does not include the benchmark suite (`benchmarks/`) or SITL integration tests (`test_sitl_integration.py`, gated behind `--sitl`). Consider a nightly CI job for these.

- **[SDK -- `mav.tlog`, `mav.tlog.raw`, `eeprom.bin` committed to repo]** Binary telemetry log files and EEPROM dumps are tracked in git. These are ~700KB of binary data that should be in `.gitignore`.
  - `C:/Users/User/drone-swarm-orchestrator/mav.tlog` (407KB)
  - `C:/Users/User/drone-swarm-orchestrator/mav.tlog.raw` (266KB)
  - `C:/Users/User/drone-swarm-orchestrator/eeprom.bin` (16KB)

- **[SDK -- `_legacy_src/` and `src/` directories still present]** The SDK modules live in `drone_swarm/`, but old `_legacy_src/` and `src/` directories remain. If these are superseded, they should be removed to avoid confusion.

- **[SDK -- Docstring style not 100% consistent]** Most modules use Google-style docstrings with `Args:` / `Returns:` sections (e.g., `swarm.py`, `safety.py`, `behavior.py`). A few use reStructuredText-style `:param:` (e.g., parts of `simulation.py`). Minor but worth standardizing before the docs site goes live.

- **[SDK -- No `py.typed` marker file]** For PEP 561 compliance (allowing downstream type checkers to use the SDK's type annotations), the package should include a `py.typed` marker file in the `drone_swarm/` directory.
  - Missing: `C:/Users/User/drone-swarm-orchestrator/drone_swarm/py.typed`

---

## What's Working Well

- **SDK module architecture is clean and well-decomposed.** 26 modules with clear separation of concerns: core types (`drone.py`), orchestration (`swarm.py`), safety (`safety.py`), subsystems (collision, formation, anomaly, path planning), and extension points (behavior, telemetry_server). No circular imports, clean dependency graph.

- **Comprehensive test coverage for SDK.** 28 test files covering every major module. Tests run without hardware (mocked MAVLink connections). The conftest.py provides reusable fixtures. Tests include state machine transitions, algorithm correctness, edge cases, and API surface validation (`test_api_surface.py`).

- **SDK CI pipeline is solid.** GitHub Actions with lint (ruff), security scan (bandit), multi-version test matrix (Python 3.11/3.12/3.13), and smoke test (build wheel, install, verify imports). This catches real issues.

- **API stability contract is well-defined.** `API_STABILITY.md` with clear Stable/Provisional/Internal tiers, versioning policy, and deprecation process. This is unusually mature for a pre-1.0 project.

- **Behavior plugin system is well-designed.** The `Behavior` base class with lifecycle hooks (setup, on_tick, on_event, teardown), priority ordering, and enable/disable toggle is a clean extension point. Both `FlightLogger` and `TelemetryServer` demonstrate the pattern working in practice.

- **Collision avoidance has two algorithms (ORCA + repulsive).** The ORCA implementation is the real deal -- velocity obstacles, half-plane intersection, reciprocal avoidance. The repulsive fallback provides graceful degradation. Both integrate cleanly via the telemetry loop.

- **Cloud dashboard telemetry pipeline works end-to-end.** The `TelemetryHub` correctly handles WebSocket lifecycle, subscription filtering, stale client cleanup, and concurrent broadcast. The dev simulator (`telemetry_sim.py`) generates realistic telemetry with orbiting positions, battery drain, and health drift. The frontend `useTelemetry` hook handles reconnection properly.

- **Cloud frontend has proper loading/empty/error states on fleet page.** The fleet page correctly shows a skeleton loader during fetch, an empty state prompt when no drones exist, and an error banner on failure. This is the right pattern for all pages.

- **Type annotations are thorough across the SDK.** All public methods have return type annotations. Dataclasses use typed fields. `TYPE_CHECKING` imports are used correctly to avoid circular import issues.

- **Security posture of the SDK is good.** No hardcoded secrets, no `eval()` or `exec()`, no shell injection vectors. The `simulation.py` subprocess calls use list-form arguments (not `shell=True`). The ruff config enforces bugbear and security rules. Bandit scans run in CI.

---

## Summary by Numbers

| Metric | SDK | Cloud |
|--------|-----|-------|
| Source modules | 26 (including mission_builder) | 10 (API) + 28 (frontend) |
| Test files | 28 | 0 |
| CI pipeline | Yes (4-job matrix) | No |
| Auth | N/A (local SDK) | None |
| API endpoints (built / planned) | N/A | 8 / 28+ |
| Frontend pages (functional / total) | N/A | 2 / 6 |
| Type safety | Strong | Drifted from backend |
| Linting | ruff (configured) | eslint (configured, not in CI) |

**Bottom line:** The SDK is in solid shape for beta -- good test coverage, clean architecture, proper CI. The cloud dashboard has a working telemetry pipeline and fleet CRUD, but has critical type mismatches between frontend and backend, zero authentication, zero tests, and zero CI. The type mismatch in `api.ts` vs `schemas/drone.py` is the most urgent fix since it breaks the "Register Drone" flow silently.
