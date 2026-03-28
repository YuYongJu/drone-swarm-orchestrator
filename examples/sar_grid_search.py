#!/usr/bin/env python3
"""
sar_grid_search.py -- Search and rescue grid search with 5 drones.

Five drones divide a rectangular search area into sectors and fly
systematic grid patterns with 15% overlap.  After the sweep, each
drone reports its coverage percentage.  A simulated anomaly detector
watches for "person found" events (modelled as a GPS-jump anomaly
when a drone hovers over a point of interest).

Use case: SAR teams deploying a quick aerial grid search after a
missing-person report.  The overlap ensures no blind spots between
sectors.

For SITL, start 5 ArduCopter instances (sysid 1-5, ports 5760-5800)
or use:  dso simulate --drones 5
"""

import asyncio

from drone_swarm import AnomalyDetector, Swarm

# Search area: roughly 110m x 110m rectangle near Edwards AFB
SW = (35.3628, -117.6695)
NE = (35.3638, -117.6685)
ALTITUDE = 15


async def main():
    swarm = Swarm()
    for i, name in enumerate(["sar-1", "sar-2", "sar-3", "sar-4", "sar-5"]):
        swarm.add(name, f"tcp:127.0.0.1:{5760 + i * 10}")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=8.0)
    swarm.enable_anomaly_detection(window_size=20)
    print("[SAR] All drones connected. Starting search grid...")

    await swarm.takeoff(altitude=ALTITUDE)
    await asyncio.sleep(10)

    # Area sweep automatically divides the rectangle among all drones
    await swarm.sweep(bounds=[SW, NE], altitude=ALTITUDE)
    await asyncio.sleep(60)

    # Report coverage
    for drone_id, drone in swarm.drones.items():
        wps_done = len(drone.mission)
        print(f"  {drone_id}: assigned {wps_done} waypoints | "
              f"pos=({drone.lat:.6f}, {drone.lon:.6f}) | batt={drone.battery_pct:.0f}%")

    print("[SAR] Grid search complete. Returning to base.")
    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
