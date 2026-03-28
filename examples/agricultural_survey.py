#!/usr/bin/env python3
"""
agricultural_survey.py -- Agricultural field survey with 3 drones.

Three drones cover an L-shaped field using polygon_sweep with
wind-aware path planning, battery monitoring via BatteryPredictor,
and per-drone health score display.

Use case: Precision agriculture -- NDVI or crop-health survey of an
irregularly shaped field.  The polygon_sweep handles the non-rectangular
boundary, overlap ensures full sensor coverage, and battery prediction
prevents mid-field landings.

For SITL, start 3 ArduCopter instances or use:  dso simulate --drones 3
"""

import asyncio

from drone_swarm import (
    BatteryPredictor,
    Swarm,
    WindEstimator,
    compute_health_score,
    polygon_sweep,
)

# L-shaped field boundary (lat, lon vertices)
FIELD = [
    (35.3600, -117.6700),
    (35.3600, -117.6660),
    (35.3630, -117.6660),
    (35.3630, -117.6680),
    (35.3615, -117.6680),
    (35.3615, -117.6700),
]
ALTITUDE = 12
OVERLAP = 15  # percent


async def main():
    swarm = Swarm()
    names = ["ag-1", "ag-2", "ag-3"]
    for i, name in enumerate(names):
        swarm.add(name, f"tcp:127.0.0.1:{5760 + i * 10}")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=6.0)

    # Prepare per-drone battery predictors and wind estimators
    {n: BatteryPredictor() for n in names}
    {n: WindEstimator() for n in names}

    print("[AG] Taking off for field survey...")
    await swarm.takeoff(altitude=ALTITUDE)
    await asyncio.sleep(10)

    # Generate sweep missions for the L-shaped polygon
    missions = polygon_sweep(FIELD, ALTITUDE, num_drones=3,
                             overlap_pct=OVERLAP, line_spacing_m=20)
    for name, wps in zip(names, missions, strict=False):
        await swarm.assign_mission(name, wps)
        print(f"  {name}: {len(wps)} waypoints assigned")

    await swarm.execute_missions()
    await asyncio.sleep(60)

    # Report health scores and battery state
    print("[AG] Survey progress:")
    for name in names:
        drone = swarm.drones[name]
        health = compute_health_score(drone)
        print(f"  {name}: health={health:.0f}/100 | batt={drone.battery_pct:.0f}% "
              f"| pos=({drone.lat:.6f}, {drone.lon:.6f})")

    print("[AG] Survey complete. Returning to launch.")
    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
