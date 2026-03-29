#!/usr/bin/env python3
"""
infrastructure_inspection.py -- Pipeline/powerline inspection with 3 drones.

Three drones fly a linear corridor (e.g., a pipeline or powerline route)
in staggered formation. Each drone covers a parallel track offset from
the centerline, giving overlapping camera coverage from multiple angles.

Features demonstrated:
  - Custom waypoint generation along a corridor
  - Staggered altitude for deconfliction
  - Geofencing along the corridor buffer zone
  - Health monitoring during long linear flights
  - Anomaly detection for vibration spikes (prop/motor issues)

Use case: Oil/gas pipeline survey, powerline inspection, highway bridge
corridor survey. Three drones fly parallel tracks at different altitudes,
giving left/center/right perspectives for 3D reconstruction.

For SITL: dso simulate --drones 3
"""

import asyncio
import math

from drone_swarm import (
    Swarm,
    Waypoint,
    compute_health_score,
)

# Pipeline route: 5 waypoints along a ~500m corridor
PIPELINE_ROUTE = [
    (35.3630, -117.6700),
    (35.3635, -117.6690),
    (35.3640, -117.6680),
    (35.3643, -117.6668),
    (35.3648, -117.6660),
]

# Geofence: 100m buffer around the corridor
GEOFENCE_BUFFER_M = 100
BASE_ALTITUDE = 20
ALT_STAGGER = 5  # meters between drone altitudes

# Lateral offset for parallel tracks (meters from centerline)
TRACK_OFFSETS_M = [-15, 0, 15]  # left, center, right

_METERS_PER_DEG_LAT = 111_320.0


def _offset_lateral(
    lat: float, lon: float, heading_deg: float, offset_m: float,
) -> tuple[float, float]:
    """Offset a GPS point perpendicular to the heading."""
    perp_rad = math.radians(heading_deg + 90)
    dlat = offset_m * math.cos(perp_rad) / _METERS_PER_DEG_LAT
    dlon = offset_m * math.sin(perp_rad) / (
        _METERS_PER_DEG_LAT * math.cos(math.radians(lat))
    )
    return lat + dlat, lon + dlon


def build_corridor_missions(
    route: list[tuple[float, float]],
    offsets_m: list[float],
    base_alt: float,
    alt_stagger: float,
) -> list[list[Waypoint]]:
    """Generate parallel track missions along a corridor.

    Each drone gets a laterally offset copy of the route at a staggered
    altitude. Headings are computed segment-by-segment for correct offsets.
    """
    missions: list[list[Waypoint]] = []

    for drone_idx, offset in enumerate(offsets_m):
        alt = base_alt + drone_idx * alt_stagger
        waypoints: list[Waypoint] = []

        for i, (lat, lon) in enumerate(route):
            # Compute heading from this point to the next (or use previous)
            if i < len(route) - 1:
                next_lat, next_lon = route[i + 1]
                heading = math.degrees(math.atan2(
                    next_lon - lon, next_lat - lat,
                ))
            # else: reuse heading from previous segment

            olat, olon = _offset_lateral(lat, lon, heading, offset)
            waypoints.append(Waypoint(olat, olon, alt))

        missions.append(waypoints)

    return missions


def build_corridor_geofence(
    route: list[tuple[float, float]], buffer_m: float,
) -> list[tuple[float, float]]:
    """Build a polygon geofence around the corridor route."""
    # Outbound pass (left side), then inbound (right side)
    left_points: list[tuple[float, float]] = []
    right_points: list[tuple[float, float]] = []

    for i in range(len(route)):
        lat, lon = route[i]
        if i < len(route) - 1:
            next_lat, next_lon = route[i + 1]
            heading = math.degrees(math.atan2(
                next_lon - lon, next_lat - lat,
            ))
        left_points.append(_offset_lateral(lat, lon, heading, -buffer_m))
        right_points.append(_offset_lateral(lat, lon, heading, buffer_m))

    # Close the polygon: left side forward, right side backward
    right_points.reverse()
    return left_points + right_points


async def main():
    swarm = Swarm()
    names = ["inspect-L", "inspect-C", "inspect-R"]
    for i, name in enumerate(names):
        swarm.add(name, f"tcp:127.0.0.1:{5760 + i * 10}")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=8.0)
    swarm.enable_anomaly_detection(window_size=30)

    # Set corridor geofence
    fence = build_corridor_geofence(PIPELINE_ROUTE, GEOFENCE_BUFFER_M)
    swarm.set_geofence(fence, alt_max_m=BASE_ALTITUDE + ALT_STAGGER * 3 + 10,
                       action="rtl")
    print(f"[INSPECT] Geofence set: {len(fence)} vertices, {GEOFENCE_BUFFER_M}m buffer")

    print("[INSPECT] Taking off...")
    await swarm.takeoff(altitude=BASE_ALTITUDE)
    await asyncio.sleep(10)

    # Generate parallel track missions
    missions = build_corridor_missions(
        PIPELINE_ROUTE, TRACK_OFFSETS_M, BASE_ALTITUDE, ALT_STAGGER,
    )
    for name, wps in zip(names, missions, strict=False):
        await swarm.assign_mission(name, wps)
        print(f"  {name}: {len(wps)} waypoints, alt={wps[0].alt:.0f}m")

    await swarm.execute_missions()
    print("[INSPECT] Corridor survey in progress...")
    await asyncio.sleep(60)

    # Mid-mission health check
    print("[INSPECT] Health report:")
    for name in names:
        drone = swarm.drones[name]
        health = compute_health_score(drone)
        print(f"  {name}: health={health:.0f}/100 | batt={drone.battery_pct:.0f}% "
              f"| vibe={drone.vibration_level:.1f}")

    print("[INSPECT] Inspection complete. Returning to launch.")
    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
