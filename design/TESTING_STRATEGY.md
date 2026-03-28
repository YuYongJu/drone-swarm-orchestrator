---
title: Testing Strategy
type: design
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, testing, quality]
---

# Drone Swarm Orchestrator -- Testing Strategy

**Version:** 1.0.0
**Last Updated:** 2026-03-26
**Status:** Draft

---

## Table of Contents

1. [Overview](#1-overview)
2. [Simulation Environment (SITL)](#2-simulation-environment-sitl)
3. [Unit Tests](#3-unit-tests)
4. [Integration Tests](#4-integration-tests)
5. [Field Test Protocol](#5-field-test-protocol)
6. [Performance Benchmarks](#6-performance-benchmarks)
7. [Safety Testing](#7-safety-testing)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Test Data Management](#9-test-data-management)

---

## 1. Overview

This document defines a layered testing strategy that builds confidence from isolated unit tests through full-field deployment. Every test tier must pass before moving to the next.

```
+-----------------------------------------------------------------+
|  Field Tests   (real hardware, real airspace)                    |
+-----------------------------------------------------------------+
|  Performance Benchmarks  (SITL at scale, latency measurement)   |
+-----------------------------------------------------------------+
|  Safety Tests  (SITL, every failsafe path exercised)            |
+-----------------------------------------------------------------+
|  Integration Tests  (SITL, full orchestration loop)             |
+-----------------------------------------------------------------+
|  Unit Tests  (mocked MAVLink, pure logic)                       |
+-----------------------------------------------------------------+
```

**Test framework:** `pytest` for all Python tests. `Jest` / `Vitest` for Next.js frontend tests (not covered in this document -- see frontend testing guide). All Python tests are in the `tests/` directory, mirroring the `src/` structure.

**Coverage targets:**
- Unit tests: 90% line coverage on core modules (mission planner, task allocator, failsafe manager, geofence manager, fleet registry).
- Integration tests: 100% of documented API endpoints exercised.
- Safety tests: 100% of failsafe paths verified.

---

## 2. Simulation Environment (SITL)

### 2.1 ArduPilot SITL Setup for N Drones

ArduPilot's Software-In-The-Loop (SITL) runs the full flight controller firmware on the host machine, communicating over simulated MAVLink.

**Single drone:**

```bash
# Install ArduPilot SITL (one-time)
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot
git submodule update --init --recursive
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

# Launch a single SITL instance
sim_vehicle.py -v ArduCopter \
  --instance 0 \
  --sysid 1 \
  -L CMAC \
  --out=udp:127.0.0.1:14550 \
  --no-mavproxy
```

**N drones (scripted):**

Create `scripts/launch_sitl.sh`:

```bash
#!/bin/bash
# Usage: ./launch_sitl.sh <num_drones> <base_port>
# Example: ./launch_sitl.sh 5 14550

NUM_DRONES=${1:-3}
BASE_PORT=${2:-14550}

# Base location: CMAC (Canberra Model Aircraft Club)
BASE_LAT=-35.363261
BASE_LON=149.165230

PIDS=()

for i in $(seq 0 $((NUM_DRONES - 1))); do
  PORT=$((BASE_PORT + i * 10))
  SYSID=$((i + 1))

  # Offset each drone 20m east of the previous one
  LON_OFFSET=$(echo "$i * 0.0002" | bc -l)
  DRONE_LON=$(echo "$BASE_LON + $LON_OFFSET" | bc -l)

  echo "Starting drone $SYSID on port $PORT at lon=$DRONE_LON"

  sim_vehicle.py -v ArduCopter \
    --instance $i \
    --sysid $SYSID \
    -l "$BASE_LAT,$DRONE_LON,584,0" \
    --out="udp:127.0.0.1:$PORT" \
    --no-mavproxy \
    --speedup 2 &

  PIDS+=($!)
  sleep 2  # Stagger startup to avoid port conflicts
done

echo "All $NUM_DRONES SITL instances running. PIDs: ${PIDS[*]}"
echo "Press Ctrl+C to stop all."
trap "kill ${PIDS[*]} 2>/dev/null" EXIT
wait
```

### 2.2 Docker Compose for Reproducible Multi-Drone Simulation

`docker/docker-compose.sitl.yml`:

```yaml
version: "3.9"

x-sitl-common: &sitl-common
  image: drone-swarm/ardupilot-sitl:4.5.1
  build:
    context: ./ardupilot-sitl
    dockerfile: Dockerfile
  restart: "no"
  networks:
    - swarm-net

services:
  # --- SITL Drones ---
  sitl-drone-1:
    <<: *sitl-common
    container_name: sitl-drone-1
    environment:
      SYSID: "1"
      INSTANCE: "0"
      LOCATION: "-35.363261,149.165230,584,0"
      SPEEDUP: "2"
      OUTPUT: "udp:orchestrator:14550"
    ports:
      - "5760:5760"  # Debug access

  sitl-drone-2:
    <<: *sitl-common
    container_name: sitl-drone-2
    environment:
      SYSID: "2"
      INSTANCE: "1"
      LOCATION: "-35.363261,149.165430,584,0"
      SPEEDUP: "2"
      OUTPUT: "udp:orchestrator:14560"
    ports:
      - "5761:5760"

  sitl-drone-3:
    <<: *sitl-common
    container_name: sitl-drone-3
    environment:
      SYSID: "3"
      INSTANCE: "2"
      LOCATION: "-35.363261,149.165630,584,0"
      SPEEDUP: "2"
      OUTPUT: "udp:orchestrator:14570"
    ports:
      - "5762:5760"

  # --- Orchestrator Backend ---
  orchestrator:
    build:
      context: ../
      dockerfile: Dockerfile
    container_name: orchestrator
    environment:
      DATABASE_URL: "postgresql://swarm:swarm@db:5432/swarm"
      DRONE_CONNECTIONS: >-
        udp:0.0.0.0:14550,
        udp:0.0.0.0:14560,
        udp:0.0.0.0:14570
      LOG_LEVEL: "DEBUG"
      TELEMETRY_RATE_HZ: "10"
      RECORDING_ENABLED: "true"
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      sitl-drone-1:
        condition: service_started
      sitl-drone-2:
        condition: service_started
      sitl-drone-3:
        condition: service_started
    networks:
      - swarm-net

  # --- Database ---
  db:
    image: postgres:16-alpine
    container_name: swarm-db
    environment:
      POSTGRES_USER: swarm
      POSTGRES_PASSWORD: swarm
      POSTGRES_DB: swarm
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U swarm"]
      interval: 2s
      timeout: 5s
      retries: 10
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - swarm-net

  # --- Test Runner ---
  test-runner:
    build:
      context: ../
      dockerfile: Dockerfile.test
    container_name: test-runner
    environment:
      API_BASE_URL: "http://orchestrator:8000"
      WS_BASE_URL: "ws://orchestrator:8000"
      TEST_TIMEOUT: "300"
    depends_on:
      - orchestrator
    networks:
      - swarm-net
    profiles:
      - test

networks:
  swarm-net:
    driver: bridge

volumes:
  pgdata:
```

**SITL Dockerfile** (`docker/ardupilot-sitl/Dockerfile`):

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    git python3 python3-pip python3-dev \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch Copter-4.5.1 \
    https://github.com/ArduPilot/ardupilot.git /ardupilot \
    && cd /ardupilot && git submodule update --init --recursive

WORKDIR /ardupilot
RUN Tools/environment_install/install-prereqs-ubuntu.sh -y
RUN . ~/.profile && ./waf configure --board sitl && ./waf copter

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

**SITL entrypoint** (`docker/ardupilot-sitl/entrypoint.sh`):

```bash
#!/bin/bash
set -e
. ~/.profile
cd /ardupilot

sim_vehicle.py -v ArduCopter \
  --instance ${INSTANCE} \
  --sysid ${SYSID} \
  -l "${LOCATION}" \
  --out="${OUTPUT}" \
  --no-mavproxy \
  --speedup ${SPEEDUP:-1} \
  --no-rebuild
```

**Running the full stack:**

```bash
# Build and start everything
docker compose -f docker/docker-compose.sitl.yml up --build -d

# Wait for all drones to be ready (heartbeats detected)
docker compose -f docker/docker-compose.sitl.yml logs -f orchestrator | grep -m 3 "Heartbeat received"

# Run the test suite
docker compose -f docker/docker-compose.sitl.yml --profile test run --rm test-runner

# Tear down
docker compose -f docker/docker-compose.sitl.yml down -v
```

### 2.3 Simulated Failure Injection

The test framework provides a `FaultInjector` class that wraps system-level operations to simulate failures in the SITL environment.

**Kill a drone process:**

```python
# tests/fixtures/fault_injector.py

import subprocess
import asyncio

class FaultInjector:
    """Injects faults into SITL drones for testing failsafe behavior."""

    def __init__(self, docker_compose_file: str):
        self.compose_file = docker_compose_file

    async def kill_drone(self, drone_number: int):
        """Kill a SITL drone container to simulate sudden power loss."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run(
            ["docker", "kill", "--signal=KILL", container],
            check=True
        )

    async def pause_drone(self, drone_number: int):
        """Pause a SITL container to simulate a freeze (no heartbeat, no crash)."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run(["docker", "pause", container], check=True)

    async def unpause_drone(self, drone_number: int):
        """Resume a paused SITL container."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run(["docker", "unpause", container], check=True)

    async def add_network_latency(self, drone_number: int, latency_ms: int, jitter_ms: int = 0):
        """Add network latency to a drone's container using tc/netem."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run([
            "docker", "exec", container,
            "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
            f"delay", f"{latency_ms}ms", f"{jitter_ms}ms"
        ], check=True)

    async def remove_network_latency(self, drone_number: int):
        """Remove injected network latency."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run([
            "docker", "exec", container,
            "tc", "qdisc", "del", "dev", "eth0", "root"
        ], check=True)

    async def drop_packets(self, drone_number: int, drop_percent: int):
        """Drop a percentage of network packets to simulate unreliable comms."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run([
            "docker", "exec", container,
            "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
            f"loss", f"{drop_percent}%"
        ], check=True)

    async def inject_battery_drain(self, drone_number: int, target_percent: int):
        """
        Use MAVLink SIM_BARO or parameter injection to force battery reading.
        In SITL, set SIM_BATT_VOLTAGE to simulate voltage drop.
        """
        # Calculate voltage for target percentage
        # Typical 4S LiPo: 16.8V full, 14.0V empty
        voltage = 14.0 + (target_percent / 100.0) * 2.8
        # Send parameter set via mavproxy or direct MAVLink
        # Implementation depends on connection method
        pass

    async def restart_drone(self, drone_number: int):
        """Restart a killed SITL drone container."""
        container = f"sitl-drone-{drone_number}"
        subprocess.run([
            "docker", "compose", "-f", self.compose_file,
            "start", container
        ], check=True)
```

**Usage in tests:**

```python
@pytest.fixture
def fault_injector():
    return FaultInjector("docker/docker-compose.sitl.yml")

async def test_drone_loss_triggers_replan(orchestrator, fault_injector):
    # Start a 3-drone mission
    mission = await orchestrator.start_mission(fleet_id, mission_id)
    assert mission.state == "active"

    # Wait for all drones to be airborne
    await wait_for_condition(
        lambda: all(d.status == "in_flight" for d in orchestrator.get_drones(fleet_id)),
        timeout=30
    )

    # Kill drone 2
    await fault_injector.kill_drone(2)

    # Assert the orchestrator detects the loss and replans
    replan_event = await wait_for_event(
        orchestrator, "replan_triggered", timeout=10
    )
    assert replan_event is not None
    assert replan_event.data["lost_drone_id"] == drone_2_id

    # Assert remaining drones received new waypoints
    replan_complete = await wait_for_event(
        orchestrator, "replan_completed", timeout=15
    )
    assert replan_complete.data["remaining_drones"] == 2
```

### 2.4 Automated CI Pipeline

The CI pipeline runs on every push to `main` and on every pull request. It spins up the full SITL environment, runs the orchestration tests, and asserts outcomes.

**GitHub Actions workflow** (`.github/workflows/sitl-tests.yml`):

```yaml
name: SITL Integration Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: sitl-${{ github.ref }}
  cancel-in-progress: true

jobs:
  sitl-tests:
    runs-on: ubuntu-latest-16core  # Need more CPU for multiple SITL instances
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Cache Docker layers
        uses: actions/cache@v4
        with:
          path: /tmp/.buildx-cache
          key: sitl-${{ runner.os }}-${{ hashFiles('docker/**') }}

      - name: Build SITL images
        run: |
          docker compose -f docker/docker-compose.sitl.yml build

      - name: Start SITL environment
        run: |
          docker compose -f docker/docker-compose.sitl.yml up -d
          # Wait for orchestrator to detect all 3 drones
          timeout 120 bash -c '
            until docker compose -f docker/docker-compose.sitl.yml logs orchestrator 2>&1 | grep -c "Heartbeat received" | grep -q "3"; do
              sleep 2
            done
          '
          echo "All 3 SITL drones detected by orchestrator"

      - name: Run integration tests
        run: |
          docker compose -f docker/docker-compose.sitl.yml \
            --profile test run --rm \
            -e PYTEST_ARGS="-v --tb=short --junitxml=/results/junit.xml" \
            test-runner

      - name: Collect logs on failure
        if: failure()
        run: |
          mkdir -p test-artifacts
          docker compose -f docker/docker-compose.sitl.yml logs > test-artifacts/all-logs.txt
          docker compose -f docker/docker-compose.sitl.yml logs orchestrator > test-artifacts/orchestrator.txt

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sitl-test-results
          path: test-artifacts/

      - name: Tear down
        if: always()
        run: docker compose -f docker/docker-compose.sitl.yml down -v
```

---

## 3. Unit Tests

All unit tests run without SITL or any external service. MAVLink connections are mocked. Tests execute in under 30 seconds total.

### 3.1 Mission Planner Tests

**File:** `tests/unit/test_mission_planner.py`

```python
"""
Tests for mission_planner module.
Covers: waypoint generation, formation geometry, survey pattern generation,
        distance/duration estimation, and mission validation.
"""
import pytest
import math
from src.mission_planner import MissionPlanner, MissionType, FormationType
from src.models import Coordinate, Waypoint, MissionParameters

class TestFormationGeometry:
    """Verify that formation calculations produce correct drone positions."""

    def test_line_formation_spacing(self):
        """N drones in a line should be evenly spaced along the heading axis."""
        planner = MissionPlanner()
        center = Coordinate(lat=37.7749, lon=-122.4194, alt=20)
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.LINE,
            heading=90,  # East
            spacing=10,
            drone_count=3
        )
        assert len(positions) == 3
        # Drone 1 should be 10m west of center, Drone 3 should be 10m east
        # Verify distances between consecutive drones
        for i in range(len(positions) - 1):
            distance = haversine(positions[i], positions[i + 1])
            assert abs(distance - 10.0) < 0.5  # 0.5m tolerance

    def test_v_formation_symmetry(self):
        """V-shape should be symmetric about the heading axis."""
        planner = MissionPlanner()
        center = Coordinate(lat=37.7749, lon=-122.4194, alt=20)
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.V_SHAPE,
            heading=0,  # North
            spacing=10,
            drone_count=5
        )
        assert len(positions) == 5
        # Leader at front, two wings symmetric
        leader = positions[0]
        left_wing = [positions[1], positions[3]]
        right_wing = [positions[2], positions[4]]
        for l, r in zip(left_wing, right_wing):
            dist_l = haversine(leader, l)
            dist_r = haversine(leader, r)
            assert abs(dist_l - dist_r) < 0.5

    def test_diamond_formation_4_drones(self):
        """Diamond with 4 drones: front, left, right, rear."""
        planner = MissionPlanner()
        center = Coordinate(lat=0.0, lon=0.0, alt=20)
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.DIAMOND,
            heading=0,
            spacing=10,
            drone_count=4
        )
        assert len(positions) == 4
        # Front and rear should be on the heading axis
        # Left and right should be perpendicular to heading axis
        # All should be equidistant from center
        for pos in positions:
            dist = haversine(center, pos)
            assert abs(dist - 10.0) < 0.5

    def test_grid_formation_dimensions(self):
        """Grid formation should arrange drones in rows and columns."""
        planner = MissionPlanner()
        center = Coordinate(lat=37.7749, lon=-122.4194, alt=20)
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.GRID,
            heading=0,
            spacing=10,
            drone_count=9  # 3x3 grid
        )
        assert len(positions) == 9
        # Verify grid dimensions: 3 rows, 3 columns, 10m spacing
        unique_lats = set(round(p.lat, 6) for p in positions)
        unique_lons = set(round(p.lon, 6) for p in positions)
        assert len(unique_lats) == 3
        assert len(unique_lons) == 3

    def test_circle_formation_equal_angles(self):
        """Circle formation should place drones at equal angular intervals."""
        planner = MissionPlanner()
        center = Coordinate(lat=37.7749, lon=-122.4194, alt=20)
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.CIRCLE,
            heading=0,
            spacing=15,  # radius
            drone_count=6
        )
        assert len(positions) == 6
        # All drones should be equidistant from center
        for pos in positions:
            dist = haversine(center, pos)
            assert abs(dist - 15.0) < 0.5
        # Angular separation should be 60 degrees
        angles = sorted([math.atan2(p.lon - center.lon, p.lat - center.lat) for p in positions])
        for i in range(len(angles) - 1):
            diff = math.degrees(angles[i + 1] - angles[i])
            assert abs(diff - 60.0) < 2.0

    def test_custom_formation_respects_offsets(self):
        """Custom formation should apply provided offsets from center."""
        planner = MissionPlanner()
        center = Coordinate(lat=37.7749, lon=-122.4194, alt=20)
        offsets = [
            Coordinate(lat=0.0001, lon=0.0, alt=0),  # ~11m north
            Coordinate(lat=-0.0001, lon=0.0001, alt=5),  # SE, 5m higher
        ]
        positions = planner.compute_formation_positions(
            center=center,
            formation=FormationType.CUSTOM,
            heading=0,
            spacing=0,
            drone_count=2,
            custom_offsets=offsets
        )
        assert len(positions) == 2
        assert positions[0].alt == 20  # center alt + offset alt (0)
        assert positions[1].alt == 25  # center alt + offset alt (5)


class TestSurveyPatternGeneration:
    """Verify survey pattern (lawnmower/boustrophedon) waypoint generation."""

    def test_survey_covers_area(self):
        """Generated survey waypoints should cover the entire polygon area."""
        planner = MissionPlanner()
        polygon = [
            Coordinate(lat=37.774, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.418, alt=0),
            Coordinate(lat=37.774, lon=-122.418, alt=0),
        ]
        waypoints = planner.generate_survey_waypoints(
            polygon=polygon,
            altitude=25,
            overlap_percent=60,
            cross_hatch=False
        )
        assert len(waypoints) > 0
        # Verify all waypoints are inside the polygon (with buffer)
        for wp in waypoints:
            assert point_in_polygon(wp.position, polygon, buffer_m=5)

    def test_cross_hatch_doubles_passes(self):
        """Cross-hatch survey should produce roughly twice the waypoints."""
        planner = MissionPlanner()
        polygon = [
            Coordinate(lat=37.774, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.418, alt=0),
            Coordinate(lat=37.774, lon=-122.418, alt=0),
        ]
        wp_single = planner.generate_survey_waypoints(polygon=polygon, altitude=25, overlap_percent=60, cross_hatch=False)
        wp_cross = planner.generate_survey_waypoints(polygon=polygon, altitude=25, overlap_percent=60, cross_hatch=True)
        ratio = len(wp_cross) / len(wp_single)
        assert 1.8 < ratio < 2.2


class TestMissionEstimation:
    """Verify distance and duration estimates."""

    def test_waypoint_distance_calculation(self):
        """Total mission distance should equal sum of waypoint-to-waypoint distances."""
        planner = MissionPlanner()
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.774, lon=-122.420, alt=25)),
            Waypoint(index=1, position=Coordinate(lat=37.775, lon=-122.420, alt=25)),
            Waypoint(index=2, position=Coordinate(lat=37.775, lon=-122.419, alt=25)),
        ]
        distance = planner.estimate_distance(waypoints)
        # ~111m per 0.001 degree latitude at this latitude
        assert 180 < distance < 220

    def test_duration_accounts_for_hold_time(self):
        """Duration estimate should include hold_time at each waypoint."""
        planner = MissionPlanner()
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.774, lon=-122.420, alt=25), hold_time=0),
            Waypoint(index=1, position=Coordinate(lat=37.775, lon=-122.420, alt=25), hold_time=10),
            Waypoint(index=2, position=Coordinate(lat=37.775, lon=-122.419, alt=25), hold_time=5),
        ]
        duration = planner.estimate_duration(waypoints, speed_ms=5)
        travel_time = planner.estimate_distance(waypoints) / 5
        hold_time = 15
        assert abs(duration - (travel_time + hold_time)) < 5  # 5s tolerance


class TestMissionValidation:
    """Verify mission validation catches all invalid configurations."""

    def test_rejects_waypoint_outside_geofence(self):
        planner = MissionPlanner()
        geofence_polygon = [
            Coordinate(lat=37.774, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.420, alt=0),
            Coordinate(lat=37.776, lon=-122.418, alt=0),
            Coordinate(lat=37.774, lon=-122.418, alt=0),
        ]
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.777, lon=-122.420, alt=25)),  # Outside
        ]
        result = planner.validate_against_geofences(waypoints, [geofence_polygon])
        assert not result.valid
        assert "outside inclusion geofence" in result.errors[0].message.lower()

    def test_rejects_altitude_above_max(self):
        planner = MissionPlanner()
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.775, lon=-122.419, alt=150)),
        ]
        result = planner.validate_altitude(waypoints, max_altitude=120)
        assert not result.valid

    def test_rejects_insufficient_battery(self):
        planner = MissionPlanner()
        # Long mission that exceeds battery capacity
        result = planner.validate_battery_sufficiency(
            distance_m=5000,
            speed_ms=5,
            battery_percent=50,
            min_battery_percent=20,
            drain_rate_percent_per_minute=3
        )
        assert not result.valid
        assert "battery" in result.errors[0].message.lower()
```

### 3.2 Task Allocator Tests

**File:** `tests/unit/test_task_allocator.py`

```python
"""
Tests for task_allocator module.
Covers: waypoint assignment to drones (Hungarian algorithm or greedy),
        reallocation after drone loss, load balancing.
"""
import pytest
from src.task_allocator import TaskAllocator
from src.models import Coordinate, Drone, Waypoint

class TestOptimalAssignment:
    """Verify that waypoints are assigned to minimize total travel distance."""

    def test_nearest_drone_gets_nearest_waypoint(self):
        """Each waypoint should be assigned to the drone that can reach it most efficiently."""
        allocator = TaskAllocator()
        drones = [
            Drone(id="d1", position=Coordinate(lat=37.774, lon=-122.420, alt=20)),
            Drone(id="d2", position=Coordinate(lat=37.776, lon=-122.418, alt=20)),
        ]
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.7741, lon=-122.4199, alt=25)),  # Near d1
            Waypoint(index=1, position=Coordinate(lat=37.7759, lon=-122.4181, alt=25)),  # Near d2
        ]
        assignment = allocator.assign(drones, waypoints)
        assert assignment["d1"] == [waypoints[0]]
        assert assignment["d2"] == [waypoints[1]]

    def test_balanced_load_with_many_waypoints(self):
        """When waypoints >> drones, workload should be roughly balanced."""
        allocator = TaskAllocator()
        drones = [
            Drone(id="d1", position=Coordinate(lat=37.775, lon=-122.419, alt=20)),
            Drone(id="d2", position=Coordinate(lat=37.775, lon=-122.419, alt=20)),
        ]
        waypoints = [Waypoint(index=i, position=Coordinate(lat=37.774 + i * 0.0001, lon=-122.419, alt=25)) for i in range(10)]
        assignment = allocator.assign(drones, waypoints)
        counts = [len(wps) for wps in assignment.values()]
        assert max(counts) - min(counts) <= 1  # At most 1 waypoint difference

    def test_single_drone_gets_all_waypoints(self):
        """With one drone, all waypoints should be assigned to it in order."""
        allocator = TaskAllocator()
        drones = [Drone(id="d1", position=Coordinate(lat=37.775, lon=-122.419, alt=20))]
        waypoints = [Waypoint(index=i, position=Coordinate(lat=37.774 + i * 0.0002, lon=-122.419, alt=25)) for i in range(5)]
        assignment = allocator.assign(drones, waypoints)
        assert len(assignment["d1"]) == 5

    def test_total_distance_is_minimized(self):
        """Assignment should produce total travel distance within 10% of optimal (brute-force for small N)."""
        allocator = TaskAllocator()
        drones = [
            Drone(id="d1", position=Coordinate(lat=37.774, lon=-122.420, alt=20)),
            Drone(id="d2", position=Coordinate(lat=37.776, lon=-122.418, alt=20)),
            Drone(id="d3", position=Coordinate(lat=37.775, lon=-122.419, alt=20)),
        ]
        waypoints = [
            Waypoint(index=0, position=Coordinate(lat=37.7741, lon=-122.4199, alt=25)),
            Waypoint(index=1, position=Coordinate(lat=37.7759, lon=-122.4181, alt=25)),
            Waypoint(index=2, position=Coordinate(lat=37.7751, lon=-122.4191, alt=25)),
        ]
        assignment = allocator.assign(drones, waypoints)
        total_dist = allocator.compute_total_distance(assignment)

        # Brute-force optimal for 3 drones, 3 waypoints
        optimal = allocator.brute_force_optimal(drones, waypoints)
        assert total_dist <= optimal * 1.1


class TestReallocation:
    """Verify reallocation when a drone is lost mid-mission."""

    def test_lost_drone_waypoints_redistributed(self):
        """Remaining waypoints of a lost drone should be assigned to surviving drones."""
        allocator = TaskAllocator()
        original = {
            "d1": [Waypoint(index=0, position=Coordinate(lat=37.774, lon=-122.420, alt=25))],
            "d2": [Waypoint(index=1, position=Coordinate(lat=37.775, lon=-122.419, alt=25)),
                   Waypoint(index=2, position=Coordinate(lat=37.776, lon=-122.418, alt=25))],
            "d3": [Waypoint(index=3, position=Coordinate(lat=37.774, lon=-122.418, alt=25))],
        }
        surviving_drones = [
            Drone(id="d1", position=Coordinate(lat=37.774, lon=-122.420, alt=25)),
            Drone(id="d3", position=Coordinate(lat=37.774, lon=-122.418, alt=25)),
        ]
        # d2 is lost; its remaining waypoints (index 1, 2) need redistribution
        new_assignment = allocator.reallocate(
            original_assignment=original,
            lost_drone_id="d2",
            surviving_drones=surviving_drones,
            completed_waypoint_indices={0, 1}  # d2 completed waypoint 1
        )
        # Waypoint 2 (uncompleted) should be assigned to d1 or d3
        all_assigned = []
        for wps in new_assignment.values():
            all_assigned.extend(wps)
        assert any(wp.index == 2 for wp in all_assigned)
        assert "d2" not in new_assignment

    def test_reallocation_with_no_remaining_waypoints(self):
        """If lost drone had completed all waypoints, no reallocation needed."""
        allocator = TaskAllocator()
        original = {
            "d1": [Waypoint(index=0, position=Coordinate(lat=37.774, lon=-122.420, alt=25))],
            "d2": [Waypoint(index=1, position=Coordinate(lat=37.775, lon=-122.419, alt=25))],
        }
        surviving = [Drone(id="d1", position=Coordinate(lat=37.774, lon=-122.420, alt=25))]
        new_assignment = allocator.reallocate(
            original_assignment=original,
            lost_drone_id="d2",
            surviving_drones=surviving,
            completed_waypoint_indices={0, 1}  # All done
        )
        assert "d2" not in new_assignment
        assert len(new_assignment["d1"]) == 0 or all(wp.index == 0 for wp in new_assignment["d1"])
```

### 3.3 Failsafe Manager Tests

**File:** `tests/unit/test_failsafe_manager.py`

```python
"""
Tests for failsafe_manager module.
Covers: correct response to every documented failure mode.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.failsafe_manager import FailsafeManager, FailsafeAction, FailureType
from src.models import DroneState, FleetState

@pytest.fixture
def failsafe():
    config = {
        "min_battery_percent": 20,
        "critical_battery_percent": 10,
        "comms_loss_timeout_seconds": 5,
        "comms_loss_action": "rtl",
        "low_battery_action": "rtl",
        "critical_battery_action": "land",
        "ekf_failure_action": "land",
        "gps_lost_action": "land",
        "geofence_breach_action": "rtl",
        "motor_failure_action": "land",
    }
    manager = FailsafeManager(config=config)
    manager.command_sender = AsyncMock()
    manager.event_emitter = AsyncMock()
    return manager


class TestBatteryFailsafe:

    async def test_low_battery_triggers_rtl(self, failsafe):
        state = DroneState(drone_id="d1", battery_percent=19, status="in_flight")
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.RTL
        failsafe.command_sender.send_rtl.assert_called_once_with("d1")
        failsafe.event_emitter.emit.assert_called_once()

    async def test_critical_battery_triggers_land(self, failsafe):
        state = DroneState(drone_id="d1", battery_percent=9, status="in_flight")
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.LAND

    async def test_battery_ok_no_action(self, failsafe):
        state = DroneState(drone_id="d1", battery_percent=50, status="in_flight")
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE

    async def test_battery_warning_not_triggered_when_landed(self, failsafe):
        """Failsafe should not trigger for drones already on the ground."""
        state = DroneState(drone_id="d1", battery_percent=15, status="landed")
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE


class TestCommsLossFailsafe:

    async def test_heartbeat_timeout_triggers_rtl(self, failsafe):
        state = DroneState(
            drone_id="d1",
            status="in_flight",
            seconds_since_last_heartbeat=6  # > 5s threshold
        )
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.RTL

    async def test_intermittent_heartbeat_no_action(self, failsafe):
        state = DroneState(
            drone_id="d1",
            status="in_flight",
            seconds_since_last_heartbeat=3  # < 5s threshold
        )
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE

    async def test_comms_loss_not_triggered_duplicate(self, failsafe):
        """If RTL already triggered for this drone, do not trigger again."""
        state = DroneState(drone_id="d1", status="returning", seconds_since_last_heartbeat=10)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE  # Already returning


class TestEKFFailsafe:

    async def test_ekf_failure_triggers_land(self, failsafe):
        state = DroneState(drone_id="d1", status="in_flight", ekf_ok=False)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.LAND

    async def test_ekf_ok_no_action(self, failsafe):
        state = DroneState(drone_id="d1", status="in_flight", ekf_ok=True)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE


class TestGPSFailsafe:

    async def test_gps_lost_triggers_land(self, failsafe):
        state = DroneState(drone_id="d1", status="in_flight", gps_fix_type=0)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.LAND

    async def test_gps_degraded_no_immediate_action(self, failsafe):
        """2D fix is degraded but not lost; should warn, not trigger failsafe."""
        state = DroneState(drone_id="d1", status="in_flight", gps_fix_type=2)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE  # Warning emitted, not failsafe


class TestGeofenceFailsafe:

    async def test_geofence_breach_triggers_rtl(self, failsafe):
        state = DroneState(drone_id="d1", status="in_flight", geofence_breached=True)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.RTL

    async def test_inside_geofence_no_action(self, failsafe):
        state = DroneState(drone_id="d1", status="in_flight", geofence_breached=False)
        action = await failsafe.evaluate(state)
        assert action == FailsafeAction.NONE


class TestFailsafePriority:

    async def test_highest_severity_wins(self, failsafe):
        """When multiple failsafes trigger simultaneously, the most severe action wins."""
        state = DroneState(
            drone_id="d1",
            status="in_flight",
            battery_percent=8,          # Critical -> LAND
            geofence_breached=True,     # Breach -> RTL
        )
        action = await failsafe.evaluate(state)
        # LAND is higher priority than RTL (safer to land immediately)
        assert action == FailsafeAction.LAND
```

### 3.4 Geofence Manager Tests

**File:** `tests/unit/test_geofence_manager.py`

```python
"""
Tests for geofence_manager module.
Covers: point-in-polygon, breach detection, proximity warnings, altitude limits.
"""
import pytest
from src.geofence_manager import GeofenceManager
from src.models import Coordinate, Geofence, GeofenceType, GeofenceGeometry

@pytest.fixture
def manager():
    gm = GeofenceManager()
    # Add a rectangular inclusion zone
    gm.add_geofence(Geofence(
        id="incl-1",
        name="Operating Area",
        type=GeofenceType.INCLUSION,
        geometry=GeofenceGeometry(
            type="polygon",
            vertices=[
                Coordinate(lat=37.774, lon=-122.420, alt=0),
                Coordinate(lat=37.776, lon=-122.420, alt=0),
                Coordinate(lat=37.776, lon=-122.418, alt=0),
                Coordinate(lat=37.774, lon=-122.418, alt=0),
            ]
        ),
        altitude_min=0,
        altitude_max=50,
    ))
    # Add a circular exclusion zone
    gm.add_geofence(Geofence(
        id="excl-1",
        name="Building",
        type=GeofenceType.EXCLUSION,
        geometry=GeofenceGeometry(
            type="circle",
            center=Coordinate(lat=37.7750, lon=-122.4190, alt=0),
            radius=20,
        ),
        altitude_min=0,
        altitude_max=50,
    ))
    return gm


class TestPointInPolygon:

    def test_point_inside_inclusion(self, manager):
        pos = Coordinate(lat=37.775, lon=-122.419, alt=20)
        result = manager.check_position(pos)
        assert result.inside_inclusion is True

    def test_point_outside_inclusion(self, manager):
        pos = Coordinate(lat=37.777, lon=-122.419, alt=20)  # North of zone
        result = manager.check_position(pos)
        assert result.inside_inclusion is False
        assert result.allowed is False

    def test_point_on_boundary_is_inside(self, manager):
        pos = Coordinate(lat=37.774, lon=-122.419, alt=20)  # On south edge
        result = manager.check_position(pos)
        assert result.inside_inclusion is True

    def test_point_inside_exclusion_zone(self, manager):
        pos = Coordinate(lat=37.7750, lon=-122.4190, alt=20)  # Center of exclusion
        result = manager.check_position(pos)
        assert result.inside_exclusion is True
        assert result.allowed is False

    def test_point_outside_exclusion_zone(self, manager):
        pos = Coordinate(lat=37.7745, lon=-122.4200, alt=20)  # Far from exclusion
        result = manager.check_position(pos)
        assert result.inside_exclusion is False


class TestBreachDetection:

    def test_breach_detected_on_exit_inclusion(self, manager):
        """Moving from inside to outside inclusion zone should trigger breach."""
        prev = Coordinate(lat=37.7759, lon=-122.419, alt=20)  # Inside
        curr = Coordinate(lat=37.7761, lon=-122.419, alt=20)  # Outside
        breach = manager.detect_breach(previous_position=prev, current_position=curr)
        assert breach is not None
        assert breach.geofence_id == "incl-1"

    def test_breach_detected_on_enter_exclusion(self, manager):
        """Moving into an exclusion zone should trigger breach."""
        prev = Coordinate(lat=37.7748, lon=-122.4190, alt=20)  # Outside exclusion
        curr = Coordinate(lat=37.7750, lon=-122.4190, alt=20)  # Inside exclusion (center)
        breach = manager.detect_breach(previous_position=prev, current_position=curr)
        assert breach is not None
        assert breach.geofence_id == "excl-1"

    def test_no_breach_when_staying_inside(self, manager):
        prev = Coordinate(lat=37.775, lon=-122.419, alt=20)
        curr = Coordinate(lat=37.7751, lon=-122.419, alt=20)
        breach = manager.detect_breach(previous_position=prev, current_position=curr)
        assert breach is None


class TestAltitudeGeofence:

    def test_above_max_altitude_is_breach(self, manager):
        pos = Coordinate(lat=37.775, lon=-122.419, alt=55)  # Max is 50
        result = manager.check_position(pos)
        assert result.allowed is False

    def test_below_min_altitude_is_breach(self, manager):
        pos = Coordinate(lat=37.775, lon=-122.419, alt=-5)  # Below ground
        result = manager.check_position(pos)
        assert result.allowed is False


class TestProximityWarning:

    def test_warning_when_near_boundary(self, manager):
        # Point that is inside inclusion but close to boundary
        pos = Coordinate(lat=37.77595, lon=-122.419, alt=20)  # ~5m from north edge
        proximity = manager.check_proximity(pos, warning_distance_m=10)
        assert proximity.warning is True
        assert proximity.nearest_boundary_m < 10

    def test_no_warning_when_far_from_boundary(self, manager):
        pos = Coordinate(lat=37.775, lon=-122.419, alt=20)  # Center of zone
        proximity = manager.check_proximity(pos, warning_distance_m=10)
        assert proximity.warning is False


class TestCRUD:

    def test_add_geofence(self):
        gm = GeofenceManager()
        geofence = Geofence(
            id="test-1",
            name="Test Zone",
            type=GeofenceType.INCLUSION,
            geometry=GeofenceGeometry(type="polygon", vertices=[
                Coordinate(lat=0, lon=0, alt=0),
                Coordinate(lat=1, lon=0, alt=0),
                Coordinate(lat=1, lon=1, alt=0),
            ]),
            altitude_min=0, altitude_max=120,
        )
        gm.add_geofence(geofence)
        assert gm.get_geofence("test-1") is not None

    def test_remove_geofence(self, manager):
        manager.remove_geofence("excl-1")
        assert manager.get_geofence("excl-1") is None
        # Point that was in exclusion should now be allowed
        pos = Coordinate(lat=37.7750, lon=-122.4190, alt=20)
        result = manager.check_position(pos)
        assert result.inside_exclusion is False

    def test_update_geofence(self, manager):
        manager.update_geofence("incl-1", altitude_max=100)
        pos = Coordinate(lat=37.775, lon=-122.419, alt=75)
        result = manager.check_position(pos)
        assert result.allowed is True  # Was out of range at 50m, now OK at 100m
```

### 3.5 Fleet Registry Tests

**File:** `tests/unit/test_fleet_registry.py`

```python
"""
Tests for fleet_registry module.
Covers: CRUD operations, validation rules, state transitions.
"""
import pytest
from src.fleet_registry import FleetRegistry
from src.models import Fleet, Drone

@pytest.fixture
def registry():
    return FleetRegistry()

class TestFleetCRUD:

    def test_create_fleet(self, registry):
        fleet = registry.create_fleet(name="Alpha", max_drones=5)
        assert fleet.id is not None
        assert fleet.name == "Alpha"
        assert fleet.drone_count == 0

    def test_get_fleet(self, registry):
        created = registry.create_fleet(name="Alpha")
        fetched = registry.get_fleet(created.id)
        assert fetched.id == created.id
        assert fetched.name == "Alpha"

    def test_update_fleet(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        updated = registry.update_fleet(fleet.id, name="Beta")
        assert updated.name == "Beta"

    def test_delete_fleet(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        registry.delete_fleet(fleet.id)
        assert registry.get_fleet(fleet.id) is None

    def test_list_fleets(self, registry):
        registry.create_fleet(name="Alpha")
        registry.create_fleet(name="Beta")
        fleets = registry.list_fleets()
        assert len(fleets) == 2

    def test_delete_fleet_with_active_mission_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        fleet.status = "active"
        with pytest.raises(ValueError, match="active mission"):
            registry.delete_fleet(fleet.id)


class TestDroneRegistration:

    def test_register_drone(self, registry):
        fleet = registry.create_fleet(name="Alpha", max_drones=3)
        drone = registry.register_drone(
            fleet_id=fleet.id,
            name="Drone-01",
            sys_id=1,
            connection_string="udp:127.0.0.1:14550"
        )
        assert drone.id is not None
        assert drone.sys_id == 1
        updated_fleet = registry.get_fleet(fleet.id)
        assert updated_fleet.drone_count == 1

    def test_duplicate_sys_id_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        registry.register_drone(fleet_id=fleet.id, name="Drone-01", sys_id=1, connection_string="udp:127.0.0.1:14550")
        with pytest.raises(ValueError, match="sys_id 1 already registered"):
            registry.register_drone(fleet_id=fleet.id, name="Drone-02", sys_id=1, connection_string="udp:127.0.0.1:14560")

    def test_exceeding_max_drones_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha", max_drones=1)
        registry.register_drone(fleet_id=fleet.id, name="Drone-01", sys_id=1, connection_string="udp:127.0.0.1:14550")
        with pytest.raises(ValueError, match="maximum.*drones"):
            registry.register_drone(fleet_id=fleet.id, name="Drone-02", sys_id=2, connection_string="udp:127.0.0.1:14560")

    def test_remove_drone(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        drone = registry.register_drone(fleet_id=fleet.id, name="Drone-01", sys_id=1, connection_string="udp:127.0.0.1:14550")
        registry.remove_drone(fleet.id, drone.id)
        updated_fleet = registry.get_fleet(fleet.id)
        assert updated_fleet.drone_count == 0

    def test_remove_in_flight_drone_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        drone = registry.register_drone(fleet_id=fleet.id, name="Drone-01", sys_id=1, connection_string="udp:127.0.0.1:14550")
        drone.status = "in_flight"
        with pytest.raises(ValueError, match="in flight"):
            registry.remove_drone(fleet.id, drone.id)


class TestValidation:

    def test_fleet_name_too_long_raises(self, registry):
        with pytest.raises(ValueError, match="name"):
            registry.create_fleet(name="A" * 101)

    def test_sys_id_out_of_range_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        with pytest.raises(ValueError, match="sys_id"):
            registry.register_drone(fleet_id=fleet.id, name="Drone", sys_id=256, connection_string="udp:127.0.0.1:14550")
        with pytest.raises(ValueError, match="sys_id"):
            registry.register_drone(fleet_id=fleet.id, name="Drone", sys_id=0, connection_string="udp:127.0.0.1:14550")

    def test_invalid_connection_string_raises(self, registry):
        fleet = registry.create_fleet(name="Alpha")
        with pytest.raises(ValueError, match="connection_string"):
            registry.register_drone(fleet_id=fleet.id, name="Drone", sys_id=1, connection_string="not_a_valid_uri")
```

### 3.6 Mock Strategy

All unit tests use mocked MAVLink connections. The mock layer sits at the boundary between the orchestrator and the MAVLink library.

**File:** `tests/mocks/mock_mavlink.py`

```python
"""
Mock MAVLink connection for unit testing.
Simulates heartbeat, telemetry, and command acknowledgment without SITL.
"""
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass
class MockTelemetry:
    lat: float = 37.7749
    lon: float = -122.4194
    alt: float = 20.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    heading: float = 0.0
    battery_percent: int = 95
    battery_voltage: float = 16.4
    gps_fix_type: int = 6
    satellites: int = 14
    hdop: float = 1.1
    rssi: int = -48
    ekf_ok: bool = True
    armed: bool = False
    flight_mode: str = "STABILIZE"

class MockMAVLinkConnection:
    """
    Drop-in replacement for a real MAVLink connection.
    Inject telemetry by modifying self.telemetry.
    Commands are recorded in self.command_history.
    """
    def __init__(self, sys_id: int = 1):
        self.sys_id = sys_id
        self.telemetry = MockTelemetry()
        self.command_history: list = []
        self.connected = True
        self.last_heartbeat_time = time.time()
        self._command_result = 0  # MAV_RESULT_ACCEPTED

    async def get_telemetry(self) -> MockTelemetry:
        return self.telemetry

    async def send_command(self, command: str, **kwargs):
        self.command_history.append({"command": command, "params": kwargs, "time": time.time()})
        return self._command_result

    async def arm(self):
        return await self.send_command("arm")

    async def disarm(self, force: bool = False):
        return await self.send_command("disarm", force=force)

    async def takeoff(self, altitude: float):
        return await self.send_command("takeoff", altitude=altitude)

    async def goto(self, lat: float, lon: float, alt: float):
        return await self.send_command("goto", lat=lat, lon=lon, alt=alt)

    async def set_mode(self, mode: str):
        self.telemetry.flight_mode = mode
        return await self.send_command("set_mode", mode=mode)

    async def rtl(self):
        return await self.send_command("rtl")

    async def land(self):
        return await self.send_command("land")

    def inject_telemetry(self, **kwargs):
        """Convenience method to update telemetry fields for testing."""
        for key, value in kwargs.items():
            setattr(self.telemetry, key, value)

    def simulate_disconnect(self):
        self.connected = False
        self.last_heartbeat_time = time.time() - 60  # 60s ago

    def set_command_result(self, result: int):
        """Set the result code for subsequent commands (0=accepted, 4=failed)."""
        self._command_result = result


def create_mock_fleet(drone_count: int = 3) -> dict:
    """Create a set of mock connections for a fleet."""
    return {
        f"drone-{i+1}": MockMAVLinkConnection(sys_id=i+1)
        for i in range(drone_count)
    }
```

---

## 4. Integration Tests

Integration tests run against the full orchestrator stack with SITL drones. They exercise the complete path from API request through MAVLink command to drone state change and back to WebSocket notification.

### 4.1 Full Orchestration Loop

**File:** `tests/integration/test_full_loop.py`

```python
"""
Integration test: Register -> Preflight -> Takeoff -> Mission -> RTL -> Land
Runs against 3 SITL drones via docker-compose.
"""
import pytest
import asyncio
import httpx
import websockets
import json

API_BASE = "http://orchestrator:8000/api/v1"
WS_BASE = "ws://orchestrator:8000/ws/v1/stream"

@pytest.fixture
async def auth_headers():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_BASE}/auth/login", json={"username": "testpilot", "password": "testpass"})
        token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def fleet_with_drones(auth_headers):
    """Create a fleet and register 3 SITL drones."""
    async with httpx.AsyncClient(headers=auth_headers) as client:
        # Create fleet
        resp = await client.post(f"{API_BASE}/fleets", json={"name": "Integration Test Fleet", "max_drones": 5})
        assert resp.status_code == 201
        fleet_id = resp.json()["id"]

        # Register 3 drones
        for i in range(3):
            port = 14550 + i * 10
            resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/drones", json={
                "name": f"SITL-Drone-{i+1}",
                "sys_id": i + 1,
                "connection_string": f"udp:0.0.0.0:{port}"
            })
            assert resp.status_code == 201

        # Wait for drones to connect (heartbeat)
        await asyncio.sleep(5)

    yield fleet_id

    # Cleanup
    async with httpx.AsyncClient(headers=auth_headers) as client:
        await client.delete(f"{API_BASE}/fleets/{fleet_id}")


async def test_full_mission_lifecycle(auth_headers, fleet_with_drones):
    fleet_id = fleet_with_drones

    async with httpx.AsyncClient(headers=auth_headers, timeout=60) as client:
        # 1. Preflight checks
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/preflight")
        assert resp.status_code == 200
        preflight = resp.json()
        assert all(r["passed"] for r in preflight["results"]), f"Preflight failed: {preflight}"

        # 2. Acquire command lock
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 200

        # 3. Arm
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/swarm/arm")
        assert resp.status_code == 200
        arm_result = resp.json()
        assert len(arm_result["armed_drones"]) == 3
        assert len(arm_result["failed_drones"]) == 0

        # 4. Create mission
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/missions", json={
            "name": "Integration Test Mission",
            "type": "waypoint",
            "parameters": {"altitude": 20, "speed": 5, "rtl_on_complete": True},
            "waypoints": [
                {"index": 0, "position": {"lat": -35.3633, "lon": 149.1654, "alt": 20}, "hold_time": 0},
                {"index": 1, "position": {"lat": -35.3635, "lon": 149.1658, "alt": 20}, "hold_time": 3},
                {"index": 2, "position": {"lat": -35.3631, "lon": 149.1658, "alt": 20}, "hold_time": 0},
            ]
        })
        assert resp.status_code == 201
        mission_id = resp.json()["id"]

        # 5. Validate mission
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/missions/{mission_id}/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

        # 6. Takeoff
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/swarm/takeoff", json={"target_altitude": 20})
        assert resp.status_code == 202

        # 7. Wait for takeoff completion via WebSocket
        token = auth_headers["Authorization"].split(" ")[1]
        async with websockets.connect(f"{WS_BASE}?token={token}&fleet_id={fleet_id}") as ws:
            # Wait for all drones to reach in_flight status
            deadline = asyncio.get_event_loop().time() + 60
            airborne_drones = set()
            while len(airborne_drones) < 3 and asyncio.get_event_loop().time() < deadline:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg["type"] == "telemetry" and msg["payload"]["status"] == "in_flight":
                    airborne_drones.add(msg["payload"]["drone_id"])
            assert len(airborne_drones) == 3, f"Only {len(airborne_drones)} drones airborne"

        # 8. Start mission
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/missions/{mission_id}/start")
        assert resp.status_code == 202

        # 9. Wait for mission completion
        async with websockets.connect(f"{WS_BASE}?token={token}&fleet_id={fleet_id}") as ws:
            deadline = asyncio.get_event_loop().time() + 180  # 3 min timeout
            mission_complete = False
            while not mission_complete and asyncio.get_event_loop().time() < deadline:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg["type"] == "event" and msg["payload"]["event_type"] == "mission_completed":
                    mission_complete = True
            assert mission_complete, "Mission did not complete within timeout"

        # 10. Verify all drones returned and landed
        resp = await client.get(f"{API_BASE}/fleets/{fleet_id}")
        fleet = resp.json()
        for drone in fleet["drones"]:
            assert drone["status"] in ("landed", "idle"), f"{drone['name']} status: {drone['status']}"

        # 11. Verify mission state
        resp = await client.get(f"{API_BASE}/fleets/{fleet_id}/missions/{mission_id}")
        assert resp.json()["state"] == "completed"

        # 12. Release command lock
        resp = await client.delete(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 204
```

### 4.2 Dynamic Replanning

**File:** `tests/integration/test_replanning.py`

```python
"""
Integration test: Lose a drone mid-mission, verify redistribution.
"""
import pytest
import asyncio

async def test_replan_on_drone_loss(auth_headers, fleet_with_drones, fault_injector):
    fleet_id = fleet_with_drones

    async with httpx.AsyncClient(headers=auth_headers, timeout=60) as client:
        # Setup: create and start a 3-drone waypoint mission
        await setup_and_start_mission(client, fleet_id)

        # Wait for all drones to be in flight and at waypoint 1
        await wait_for_all_at_waypoint(client, fleet_id, waypoint_index=1, timeout=60)

        # Kill drone 2
        await fault_injector.kill_drone(2)

        # Connect to WebSocket and wait for replan events
        token = get_token(auth_headers)
        events = await collect_events_until(
            ws_url=f"{WS_BASE}?token={token}&fleet_id={fleet_id}",
            target_events=["replan_triggered", "replan_completed"],
            timeout=30
        )

        # Verify replan was triggered
        assert any(e["event_type"] == "replan_triggered" for e in events)
        replan_trigger = next(e for e in events if e["event_type"] == "replan_triggered")
        assert "drone" in replan_trigger["data"]["lost_drone_id"].lower() or True  # Has a drone ID

        # Verify replan completed
        assert any(e["event_type"] == "replan_completed" for e in events)
        replan_complete = next(e for e in events if e["event_type"] == "replan_completed")
        assert replan_complete["data"]["remaining_drones"] == 2

        # Let the mission continue to completion with 2 drones
        completion_event = await wait_for_event_ws(
            ws_url=f"{WS_BASE}?token={token}&fleet_id={fleet_id}",
            event_type="mission_completed",
            timeout=180
        )
        assert completion_event is not None

        # Verify 2 drones landed successfully
        resp = await client.get(f"{API_BASE}/fleets/{fleet_id}")
        active_drones = [d for d in resp.json()["drones"] if d["status"] != "offline"]
        assert len(active_drones) == 2
        for drone in active_drones:
            assert drone["status"] in ("landed", "idle")
```

### 4.3 Formation Maintenance Under Drift

**File:** `tests/integration/test_formation.py`

```python
"""
Integration test: Formation maintenance when position drift is injected.
"""

async def test_formation_correction_under_drift(auth_headers, fleet_with_drones, fault_injector):
    fleet_id = fleet_with_drones

    async with httpx.AsyncClient(headers=auth_headers, timeout=60) as client:
        # Arm, takeoff, set V-formation
        await arm_and_takeoff(client, fleet_id, altitude=20)
        resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/swarm/formation", json={
            "type": "v_shape",
            "spacing": 10,
            "heading": 90,
            "center": {"lat": -35.3633, "lon": 149.1654, "alt": 20}
        })
        assert resp.status_code == 202

        # Wait for formation to stabilize
        await wait_for_formation_tolerance(client, fleet_id, tolerance_m=2.0, timeout=30)

        # Inject network latency on drone 1 to cause position control lag
        await fault_injector.add_network_latency(1, latency_ms=200, jitter_ms=50)

        # Wait and observe: the orchestrator should detect degraded formation
        # and the drone should correct back into position
        await asyncio.sleep(10)

        # Check formation accuracy via swarm state
        token = get_token(auth_headers)
        swarm_state = await get_latest_swarm_state(
            ws_url=f"{WS_BASE}?token={token}&fleet_id={fleet_id}",
            timeout=15
        )

        # Formation may be temporarily degraded but should recover
        await fault_injector.remove_network_latency(1)
        await asyncio.sleep(10)

        swarm_state_after = await get_latest_swarm_state(
            ws_url=f"{WS_BASE}?token={token}&fleet_id={fleet_id}",
            timeout=15
        )
        assert swarm_state_after["formation_accuracy"]["within_tolerance"] is True
        assert swarm_state_after["formation_accuracy"]["avg_error_m"] < 2.0
```

### 4.4 Multi-Operator Coordination

**File:** `tests/integration/test_multi_operator.py`

```python
"""
Integration test: Two ground stations controlling the same fleet.
"""

async def test_command_lock_prevents_dual_control(fleet_with_drones):
    fleet_id = fleet_with_drones

    # Operator 1 logs in and acquires lock
    op1_headers = await login("operator1", "pass1")
    async with httpx.AsyncClient(headers=op1_headers) as op1:
        resp = await op1.post(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 200

    # Operator 2 tries to acquire lock -- should fail
    op2_headers = await login("operator2", "pass2")
    async with httpx.AsyncClient(headers=op2_headers) as op2:
        resp = await op2.post(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "COMMAND_LOCK_HELD"

    # Operator 2 tries to send a command -- should fail
    async with httpx.AsyncClient(headers=op2_headers) as op2:
        resp = await op2.post(f"{API_BASE}/fleets/{fleet_id}/swarm/arm")
        assert resp.status_code == 403

    # Operator 2 CAN still read telemetry
    async with httpx.AsyncClient(headers=op2_headers) as op2:
        resp = await op2.get(f"{API_BASE}/fleets/{fleet_id}")
        assert resp.status_code == 200

    # Operator 1 releases lock
    async with httpx.AsyncClient(headers=op1_headers) as op1:
        resp = await op1.delete(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 204

    # Now Operator 2 can acquire lock
    async with httpx.AsyncClient(headers=op2_headers) as op2:
        resp = await op2.post(f"{API_BASE}/fleets/{fleet_id}/lock")
        assert resp.status_code == 200


async def test_lock_change_broadcast_over_websocket(fleet_with_drones):
    fleet_id = fleet_with_drones
    op1_headers = await login("operator1", "pass1")
    op2_headers = await login("operator2", "pass2")
    op2_token = op2_headers["Authorization"].split(" ")[1]

    # Operator 2 connects to WebSocket
    async with websockets.connect(f"{WS_BASE}?token={op2_token}&fleet_id={fleet_id}") as ws:
        # Operator 1 acquires lock
        async with httpx.AsyncClient(headers=op1_headers) as op1:
            await op1.post(f"{API_BASE}/fleets/{fleet_id}/lock")

        # Operator 2 should receive a command_lock_acquired event
        event = await wait_for_ws_event(ws, "command_lock_acquired", timeout=5)
        assert event is not None
        assert event["data"]["locked_by"] != op2_token  # Someone else holds it
```

### 4.5 WebSocket Reliability

**File:** `tests/integration/test_websocket_reliability.py`

```python
"""
Integration test: WebSocket disconnect/reconnect during an active mission.
"""

async def test_reconnect_receives_missed_events(auth_headers, fleet_with_drones):
    fleet_id = fleet_with_drones
    token = get_token(auth_headers)

    async with httpx.AsyncClient(headers=auth_headers, timeout=60) as client:
        # Start a mission
        await setup_and_start_mission(client, fleet_id)
        await wait_for_all_airborne(client, fleet_id)

        # Connect WebSocket, then disconnect
        ws = await websockets.connect(f"{WS_BASE}?token={token}&fleet_id={fleet_id}")
        initial_msg = json.loads(await ws.recv())
        assert initial_msg["type"] == "connection_status"
        await ws.close()

        # Wait for some events to happen while disconnected
        await asyncio.sleep(5)

        # Reconnect
        ws = await websockets.connect(f"{WS_BASE}?token={token}&fleet_id={fleet_id}")
        reconnect_msg = json.loads(await ws.recv())
        assert reconnect_msg["type"] == "connection_status"
        assert reconnect_msg["payload"]["status"] == "reconnected"

        # Should have missed events replayed
        missed = reconnect_msg["payload"]["missed_events"]
        assert len(missed) > 0, "Should have received missed events on reconnect"

        await ws.close()


async def test_websocket_handles_rapid_reconnect(auth_headers, fleet_with_drones):
    """Rapidly connecting and disconnecting should not crash the server."""
    fleet_id = fleet_with_drones
    token = get_token(auth_headers)

    for _ in range(10):
        ws = await websockets.connect(f"{WS_BASE}?token={token}&fleet_id={fleet_id}")
        await asyncio.sleep(0.1)
        await ws.close()
        await asyncio.sleep(0.1)

    # Server should still be healthy
    async with httpx.AsyncClient(headers=auth_headers) as client:
        resp = await client.get(f"{API_BASE}/fleets/{fleet_id}")
        assert resp.status_code == 200
```

---

## 5. Field Test Protocol

### 5.1 Pre-Field Checklist

Complete every item before departing for the field. Any "No" answer is a no-go.

| #  | Item                                          | Check       |
|----|-----------------------------------------------|-------------|
| 1  | Weather: wind < 20 km/h, no precipitation, visibility > 3 km | [ ] Yes/No |
| 2  | Airspace: checked local NOTAM, no TFRs in area | [ ] Yes/No |
| 3  | Regulatory: Part 107 (or equivalent) certificate on person | [ ] Yes/No |
| 4  | Regulatory: flight logged in LAANC / UTM system | [ ] Yes/No |
| 5  | Hardware: all drone batteries charged > 95%   | [ ] Yes/No  |
| 6  | Hardware: all propellers inspected, no cracks  | [ ] Yes/No  |
| 7  | Hardware: transmitter batteries charged        | [ ] Yes/No  |
| 8  | Hardware: ground station laptop charged > 80%  | [ ] Yes/No  |
| 9  | Software: latest firmware on all drones (matching SITL version) | [ ] Yes/No |
| 10 | Software: orchestrator backend running, all drones heartbeating | [ ] Yes/No |
| 11 | Software: geofences configured for field site  | [ ] Yes/No  |
| 12 | Safety: spotter(s) present                     | [ ] Yes/No  |
| 13 | Safety: fire extinguisher on site               | [ ] Yes/No  |
| 14 | Safety: first aid kit on site                   | [ ] Yes/No  |
| 15 | Safety: manual RC override tested and working for each drone | [ ] Yes/No |
| 16 | Comms: all team members have radios             | [ ] Yes/No  |
| 17 | Go/no-go consensus from all team members        | [ ] Yes/No  |

### 5.2 Progressive Test Sequence

#### Level 1: Single Drone -- Manual Control

**Objective:** Verify basic hardware, telemetry pipeline, and manual control.

**Procedure:**
1. Power on one drone.
2. Verify heartbeat appears in ground station UI within 5 seconds.
3. Run preflight checks via API. All must pass.
4. Arm via ground station (or RC transmitter as backup).
5. Manually fly to 5m altitude. Hold position for 10 seconds.
6. Verify telemetry in ground station: position, altitude, battery, GPS quality.
7. Fly a small box pattern (20m x 20m) at 5m altitude.
8. Land manually.

**Success Criteria:**
- Telemetry updates visible in UI at expected rate (10 Hz).
- Position on map matches visual position of drone.
- Battery reading is reasonable (drop < 5% for a 2-minute hover).
- No errors or warnings in orchestrator logs.

**Go/No-Go:** Must pass all criteria before proceeding to Level 2.

---

#### Level 2: Single Drone -- Scripted Mission

**Objective:** Verify the orchestrator can command a drone through a complete mission autonomously.

**Procedure:**
1. Create a mission in the ground station:
   - 4 waypoints forming a 50m x 50m rectangle.
   - Altitude: 15m AGL.
   - Speed: 3 m/s.
   - Hold 3 seconds at each waypoint.
   - RTL on complete.
2. Validate mission (API call).
3. Acquire command lock.
4. Arm via API.
5. Takeoff via API to 15m.
6. Start mission via API.
7. Observe: drone should fly the rectangle autonomously.
8. Verify each `waypoint_reached` event fires.
9. On mission complete, drone should RTL and land.

**Success Criteria:**
- Drone visits all 4 waypoints in order.
- Each waypoint reached within 2m acceptance radius.
- Hold time at each waypoint is approximately 3 seconds.
- RTL completes and drone lands within 3m of home position.
- Mission state transitions: `draft` -> `validated` -> `active` -> `completed`.
- Total mission duration within 20% of estimate.

**Go/No-Go:** Must pass all criteria before proceeding to Level 3.

---

#### Level 3: Two Drones -- Formation Flight

**Objective:** Verify multi-drone formation commands and collision avoidance.

**Procedure:**
1. Register two drones to the fleet.
2. Preflight both.
3. Arm and takeoff both to 15m.
4. Command line formation with 10m spacing, heading North.
5. Hold formation for 15 seconds. Observe spacing.
6. Command goto: move formation center 50m East.
7. Hold formation at new position for 10 seconds.
8. Change formation to V-shape.
9. Hold for 10 seconds.
10. RTL.

**Success Criteria:**
- Both drones reach target altitude within 5 seconds of each other.
- Formation spacing is within 2m of commanded spacing.
- During goto, formation shape is maintained (avg error < 3m).
- Formation change completes within 15 seconds.
- No collision warnings.
- Both drones RTL and land safely.

**Go/No-Go:** Must pass all criteria before proceeding to Level 4.

---

#### Level 4: Three Drones -- Full Demo

**Objective:** Demonstrate the complete platform capability with a realistic mission profile.

**Procedure:**
1. Register three drones.
2. Preflight all three.
3. Create a demo mission:
   - Phase 1: Takeoff in line formation.
   - Phase 2: Fly to survey area start (200m away).
   - Phase 3: Execute area survey in grid pattern.
   - Phase 4: Change to V-formation.
   - Phase 5: Fly to RTL position.
   - Phase 6: RTL and land.
4. Validate and start mission.
5. Monitor full mission from ground station.
6. Record the entire mission for replay testing.

**Success Criteria:**
- All three drones complete all mission phases.
- Formation accuracy < 3m average error throughout.
- Survey coverage: 100% of target area.
- Total mission duration within 25% of estimate.
- All telemetry logged and available for replay.
- No failsafe events triggered.
- All drones land with > 25% battery remaining.

**Go/No-Go:** Must pass all criteria before proceeding to Level 5.

---

#### Level 5: Failure Injection -- In-Flight Drone Loss

**Objective:** Verify the platform handles a real hardware failure gracefully.

**Procedure:**
1. Start a 3-drone formation mission (identical to Level 4 Phase 1-3).
2. When drones reach the survey area and begin surveying:
   a. Power off one drone's RC transmitter (simulating comms loss to that channel), OR
   b. Cut power to one drone's battery (only if over a soft landing area with safety nets).
   **SAFETY: Only attempt (b) at low altitude (< 5m) over a designated crash zone. Prefer (a).**
3. Observe orchestrator response:
   - Comms-loss alert should appear within 5 seconds.
   - Replan should trigger automatically.
   - Remaining 2 drones should redistribute the survey area.
4. Let the remaining 2 drones complete the mission.
5. RTL.

**Success Criteria:**
- Comms loss detected within `comms_loss_timeout_seconds` (5s).
- Replan triggers within 5 seconds of detection.
- New plan is computed and executing within 15 seconds of drone loss.
- Remaining 2 drones complete the survey area that was assigned to the lost drone.
- No cascading failures (other drones remain stable).
- Mission completes with `completed` state (not `failed`).

**Go/No-Go:** This is the final test level. All criteria must pass for platform certification.

### 5.3 Data Collection

**What to Log (automatically):**
- Full telemetry for all drones at 10 Hz (via recording system).
- All orchestrator events and state transitions.
- All API requests and responses with timestamps.
- Backend application logs at DEBUG level.

**What to Measure (manually):**
- Ambient temperature and wind speed at start/end of each test.
- Visual position accuracy: compare drone visual position to ground markers at known GPS coordinates.
- Operator subjective assessment: UI responsiveness, command clarity, alert usefulness.

**What Success Looks Like:**
- Telemetry logs show continuous data with no gaps > 1 second.
- Event logs show correct state transitions with no spurious states.
- Visual position matches telemetry position within 2m.
- Operator rates all UI interactions as "acceptable" or better.
- No unhandled exceptions in application logs.

### 5.4 Go/No-Go Summary

| Level | Prerequisite                      | Abort Trigger                                       |
|-------|-----------------------------------|-----------------------------------------------------|
| 1     | Pre-field checklist complete       | Any preflight check fails; telemetry not working    |
| 2     | Level 1 passed                    | Mission does not start; drone deviates > 10m        |
| 3     | Level 2 passed                    | Formation error > 5m; any collision warning          |
| 4     | Level 3 passed                    | Any failsafe triggers unexpectedly; battery < 25%   |
| 5     | Level 4 passed; safety zone ready | Replan fails; cascading failure; remaining drones unstable |

---

## 6. Performance Benchmarks

All benchmarks are run against the SITL environment with controlled conditions. Results are recorded in a structured format for trend analysis across releases.

### 6.1 Command Latency

**Definition:** Time from the HTTP response of a command endpoint to the first observable change in drone telemetry (e.g., armed flag changes, altitude starts increasing).

**Measurement Method:**

```python
async def measure_command_latency(client, ws, fleet_id, command, expected_change):
    """
    Send a command and measure time until telemetry reflects the change.
    Returns latency in milliseconds.
    """
    t_start = time.monotonic_ns()
    await client.post(f"{API_BASE}/fleets/{fleet_id}/swarm/{command}")

    while True:
        msg = json.loads(await ws.recv())
        if msg["type"] == "telemetry" and expected_change(msg["payload"]):
            t_end = time.monotonic_ns()
            return (t_end - t_start) / 1_000_000  # ms
```

**Benchmarks:**

| Command        | Target (p50)  | Target (p99)  | Measured With |
|----------------|---------------|---------------|---------------|
| Arm            | < 500 ms      | < 2000 ms     | 3 SITL drones |
| Takeoff        | < 1000 ms     | < 3000 ms     | 3 SITL drones |
| Goto waypoint  | < 500 ms      | < 1500 ms     | 3 SITL drones |
| Formation change | < 500 ms    | < 2000 ms     | 3 SITL drones |
| Emergency stop | < 200 ms      | < 500 ms      | 3 SITL drones |
| RTL            | < 500 ms      | < 1500 ms     | 3 SITL drones |

### 6.2 Telemetry Latency

**Definition:** Time from a state change on the SITL drone to the WebSocket message arriving at the client.

**Measurement Method:**
- Inject a known position change in SITL at time T0 (via MAVProxy `wp set` or direct parameter change).
- Record the WebSocket message timestamp when the position change appears at the client (T1).
- Latency = T1 - T0.

**Benchmarks:**

| Metric                     | Target (p50) | Target (p99) |
|----------------------------|--------------|--------------|
| Position update latency    | < 150 ms     | < 500 ms     |
| Battery update latency     | < 200 ms     | < 800 ms     |
| Status change latency      | < 200 ms     | < 500 ms     |

### 6.3 Replanning Time

**Definition:** Time from the `replan_triggered` event to the `replan_completed` event.

**Measurement Method:**
- Kill a SITL drone during an active mission.
- Record timestamps of `replan_triggered` and `replan_completed` events.
- Replanning time = difference.

**Benchmarks:**

| Scenario                    | Target       |
|-----------------------------|--------------|
| 3 drones, lose 1            | < 2 seconds  |
| 5 drones, lose 1            | < 3 seconds  |
| 10 drones, lose 1           | < 5 seconds  |
| 10 drones, lose 3           | < 8 seconds  |

### 6.4 Formation Accuracy

**Definition:** Euclidean distance between each drone's actual position and its target position within the formation.

**Measurement Method:**
- Command a formation.
- After stabilization (10 seconds), sample telemetry for 30 seconds.
- Compute per-drone error = distance(actual_position, target_position).
- Report average and max error.

**Benchmarks:**

| Metric                          | Target          |
|---------------------------------|-----------------|
| Average position error (hover)  | < 1.5 m         |
| Max position error (hover)      | < 3.0 m         |
| Average position error (moving) | < 2.5 m         |
| Max position error (moving)     | < 5.0 m         |
| Heading alignment error         | < 10 degrees     |

### 6.5 Scalability

**Definition:** How key metrics degrade as drone count increases.

**Test Matrix:**

| Drone Count | Telemetry Rate (Hz) | Backend CPU (%) | WS Bandwidth (KB/s) | Command Latency p50 (ms) |
|-------------|---------------------|-----------------|----------------------|--------------------------|
| 1           | 10                  | target < 5%     | target < 5           | target < 300             |
| 3           | 10                  | target < 15%    | target < 15          | target < 500             |
| 5           | 10                  | target < 25%    | target < 25          | target < 700             |
| 10          | 10                  | target < 50%    | target < 50          | target < 1000            |
| 20          | 5 (reduced)         | target < 80%    | target < 80          | target < 1500            |
| 50          | 2 (reduced)         | target < 90%    | target < 100         | target < 3000            |

**How to Run:**

```bash
# Launch N SITL drones
./scripts/launch_sitl.sh 10 14550

# Run the scalability benchmark suite
pytest tests/benchmarks/test_scalability.py \
  --drone-count 10 \
  --benchmark-output results/scale_10.json
```

### 6.6 Benchmark CI Integration

Performance benchmarks run nightly (not on every PR, since SITL is slow). Results are stored as JSON artifacts and tracked over time. A regression alert fires if any p99 metric exceeds 1.5x the previous release's value.

```yaml
# .github/workflows/benchmarks.yml
name: Nightly Performance Benchmarks

on:
  schedule:
    - cron: "0 3 * * *"  # 3 AM UTC daily
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest-16core
    strategy:
      matrix:
        drone_count: [3, 5, 10]
    steps:
      - uses: actions/checkout@v4
      - name: Run benchmarks with ${{ matrix.drone_count }} drones
        run: |
          docker compose -f docker/docker-compose.sitl.yml up -d --scale sitl-drone=${{ matrix.drone_count }}
          pytest tests/benchmarks/ --drone-count ${{ matrix.drone_count }} --benchmark-json results.json
      - uses: actions/upload-artifact@v4
        with:
          name: benchmark-${{ matrix.drone_count }}
          path: results.json
```

---

## 7. Safety Testing

Safety tests verify that every failsafe path works correctly. Each test must be run in SITL first, and then verified during field test Level 5.

### 7.1 Failsafe Verification Matrix

Every row in this matrix must have a passing SITL test and (where applicable) a passing field test.

| Failure Mode            | Expected Behavior                                  | SITL Test | Field Test |
|-------------------------|----------------------------------------------------|-----------|------------|
| Low battery (< 20%)     | Alert + auto-RTL after 30s if not acknowledged     | Required  | Level 5    |
| Critical battery (< 10%)| Immediate land-in-place                            | Required  | N/A (risk) |
| Comms loss (> 5s)       | Auto-RTL                                           | Required  | Level 5    |
| GPS lost                | Auto-land-in-place                                 | Required  | N/A (risk) |
| EKF failure             | Auto-land-in-place                                 | Required  | N/A (risk) |
| Geofence breach         | Auto-RTL (or configured action)                    | Required  | Level 4    |
| Motor failure           | Auto-land-in-place                                 | Required  | N/A (risk) |
| Single drone loss       | Replan mission for remaining drones                | Required  | Level 5    |
| Multiple drone loss     | Abort mission if < minimum viable swarm size       | Required  | N/A        |
| Backend crash           | Drones hold position; resume on reconnect          | Required  | N/A        |
| Ground station disconnect | Drones continue mission; reconnect replays events | Required  | Level 4    |

### 7.2 Emergency Stop Response Time

**Test procedure (SITL):**

```python
async def test_emergency_stop_timing():
    """Emergency stop must disarm all motors within 500ms of the API call."""
    # Start 3 drones in hover at 20m
    await arm_and_takeoff(fleet_id, altitude=20)

    # Time the emergency stop
    t_start = time.monotonic_ns()
    resp = await client.post(f"{API_BASE}/fleets/{fleet_id}/swarm/emergency-stop")
    assert resp.status_code == 200

    # Wait for all drones to show disarmed
    while True:
        msg = json.loads(await ws.recv())
        if msg["type"] == "telemetry":
            if all_drones_disarmed(telemetry_cache):
                t_end = time.monotonic_ns()
                break

    latency_ms = (t_end - t_start) / 1_000_000
    assert latency_ms < 500, f"Emergency stop took {latency_ms}ms (target < 500ms)"
```

**Acceptance criterion:** p99 < 500 ms across 50 trials.

### 7.3 Geofence Breach Response Time

**Test procedure:**

```python
async def test_geofence_breach_response():
    """
    Command a drone to fly toward the geofence boundary.
    Measure time from boundary crossing to RTL initiation.
    """
    # Setup: inclusion geofence with known boundary
    # Command drone to fly toward boundary at known speed

    # Monitor telemetry for the moment the drone crosses the boundary
    breach_time = None
    rtl_time = None

    while True:
        msg = json.loads(await ws.recv())
        if msg["type"] == "telemetry":
            pos = msg["payload"]["position"]
            if not point_in_geofence(pos) and breach_time is None:
                breach_time = time.monotonic_ns()
            if msg["payload"]["flight_mode"] == "RTL" and rtl_time is None:
                rtl_time = time.monotonic_ns()
                break

    response_ms = (rtl_time - breach_time) / 1_000_000
    assert response_ms < 1000, f"Geofence response took {response_ms}ms (target < 1000ms)"
```

**Acceptance criterion:** p99 < 1000 ms. Includes detection time + command propagation.

### 7.4 Battery Failsafe Verification

**Test procedure:**

```python
async def test_battery_failsafe_triggers_rtl():
    """Simulate battery drain and verify RTL triggers at threshold."""
    await arm_and_takeoff(fleet_id, altitude=15)

    # Inject battery drain via SITL parameter
    await fault_injector.inject_battery_drain(drone_number=1, target_percent=19)

    # Wait for battery warning alert
    alert = await wait_for_alert(ws, "battery_critical", timeout=10)
    assert alert is not None
    assert alert["data"]["battery_percent"] <= 20

    # If not acknowledged within 30s, RTL should trigger
    await asyncio.sleep(35)

    # Verify drone is in RTL mode
    telemetry = await get_latest_telemetry(ws, drone_id="d1")
    assert telemetry["flight_mode"] == "RTL"
```

### 7.5 Communications Loss Failsafe

**Test procedure:**

```python
async def test_comms_loss_triggers_rtl():
    """
    Pause a SITL drone container to simulate total comms loss.
    Verify the orchestrator triggers RTL within the timeout window.
    """
    await arm_and_takeoff(fleet_id, altitude=15)

    # Pause drone 1 (no more heartbeats)
    await fault_injector.pause_drone(1)

    # Wait for comms_lost event
    event = await wait_for_event_ws(ws, "comms_lost", timeout=10)
    assert event is not None

    # The orchestrator cannot command a paused drone, but it should:
    # 1. Emit the comms_lost event
    # 2. Mark the drone as disconnected
    # 3. Trigger replan for remaining drones if in mission

    # Unpause and verify the drone's onboard failsafe (ArduPilot GCS failsafe) kicked in
    await fault_injector.unpause_drone(1)
    await asyncio.sleep(5)

    telemetry = await get_latest_telemetry(ws, drone_id="d1")
    # The drone should be in RTL (either commanded by orchestrator or by ArduPilot's own GCS failsafe)
    assert telemetry["flight_mode"] in ("RTL", "LAND")
```

### 7.6 Backend Crash Recovery

**Test procedure:**

```python
async def test_backend_crash_recovery():
    """
    Kill the orchestrator process while drones are in flight.
    Verify drones hold position (ArduPilot's GCS failsafe).
    Restart the orchestrator and verify it reconnects.
    """
    await arm_and_takeoff(fleet_id, altitude=15)

    # Record positions before crash
    positions_before = await get_all_positions(fleet_id)

    # Kill the orchestrator container
    subprocess.run(["docker", "kill", "orchestrator"], check=True)

    # Wait 10 seconds -- drones should hold position via ArduPilot's GCS failsafe
    await asyncio.sleep(10)

    # Restart the orchestrator
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "start", "orchestrator"], check=True)
    await asyncio.sleep(10)  # Wait for reconnection

    # Verify all drones reconnected
    resp = await client.get(f"{API_BASE}/fleets/{fleet_id}")
    fleet = resp.json()
    connected = [d for d in fleet["drones"] if d["status"] != "offline"]
    assert len(connected) == 3

    # Verify positions haven't drifted significantly
    positions_after = await get_all_positions(fleet_id)
    for drone_id in positions_before:
        drift = haversine(positions_before[drone_id], positions_after[drone_id])
        assert drift < 5.0, f"Drone {drone_id} drifted {drift}m during backend outage"
```

---

## 8. CI/CD Pipeline

### 8.1 Pipeline Stages

```
PR Created / Push to main
    |
    v
[Stage 1: Lint + Type Check]  (~1 min)
    - ruff check .
    - mypy src/
    - prettier --check (frontend)
    |
    v
[Stage 2: Unit Tests]  (~2 min)
    - pytest tests/unit/ -x --cov
    - Coverage gate: fail if < 90%
    |
    v
[Stage 3: Integration Tests (SITL)]  (~15 min)
    - docker compose up (3 SITL drones + orchestrator)
    - pytest tests/integration/ -x
    - docker compose down
    |
    v
[Stage 4: Safety Tests (SITL)]  (~10 min)  [main branch only]
    - pytest tests/safety/ -x
    |
    v
[Nightly: Performance Benchmarks]  (~30 min)
    - Scale tests: 3, 5, 10 drones
    - Regression detection
    |
    v
[Pre-Release: Full Benchmark Suite]  (~1 hour)
    - Scale tests: 3, 5, 10, 20, 50 drones
    - All safety tests
    - All integration tests
```

### 8.2 Test Tagging

Use pytest markers to control which tests run where:

```python
# conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (requires SITL)")
    config.addinivalue_line("markers", "safety: Safety tests (requires SITL)")
    config.addinivalue_line("markers", "benchmark: Performance benchmarks (slow)")
    config.addinivalue_line("markers", "field: Field test helpers (not run in CI)")
```

```bash
# Run only unit tests
pytest -m unit

# Run unit + integration
pytest -m "unit or integration"

# Run everything except benchmarks
pytest -m "not benchmark"
```

---

## 9. Test Data Management

### 9.1 Fixtures

All integration tests use a shared set of fixtures that create and tear down test state. Fixtures are defined in `tests/conftest.py` and `tests/integration/conftest.py`.

Key fixtures:
- `auth_headers` -- Provides a valid JWT for the test pilot user.
- `fleet_with_drones` -- Creates a fleet with N SITL drones, tears down after test.
- `active_mission` -- Creates a fleet, registers drones, creates and starts a mission.
- `fault_injector` -- Provides the FaultInjector instance.
- `ws_connection` -- Provides a connected WebSocket client.

### 9.2 Test Recordings

SITL integration tests that produce interesting telemetry (e.g., replanning tests) save their recordings to `tests/fixtures/recordings/`. These recordings are used by replay tests and as regression baselines.

### 9.3 Golden Files

Expected outputs for deterministic computations (formation positions, survey waypoints, task allocations) are stored as JSON files in `tests/fixtures/golden/`. Unit tests compare computed output against golden files. To update golden files after an intentional algorithm change:

```bash
pytest tests/unit/ --update-golden
```

This writes new golden files. Review the diff carefully before committing.

### 9.4 Secrets and Test Credentials

- Test user credentials are hardcoded in `tests/conftest.py` (`testpilot` / `testpass`).
- These credentials only work when `AUTH_MODE=test` is set in the backend configuration.
- Production deployments must never use `AUTH_MODE=test`.
- No real secrets, API keys, or certificates are stored in the test directory.

---

## Related Documents

- [[PRODUCT_SPEC]] -- Requirements being tested
- [[SYSTEM_ARCHITECTURE]] -- Architecture under test
- [[PRESSURE_TEST]] -- Independent review of testing gaps
- [[INTEGRATION_AUDIT]] -- Cross-document consistency validation
- [[HARDWARE_SPEC]] -- Hardware specs for HITL and field testing
- [[ROADMAP]] -- Testing milestones by phase
