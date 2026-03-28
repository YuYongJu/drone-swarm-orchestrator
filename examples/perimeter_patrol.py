#!/usr/bin/env python3
"""
perimeter_patrol.py -- Continuous perimeter patrol with 2 drones.

Two drones fly opposite directions around a polygon perimeter with
collision avoidance enabled.  Each drone loops the perimeter
continuously until manually stopped (Ctrl-C triggers RTL).

Use case: Security monitoring of a facility perimeter, construction
site boundary, or event venue.  Counter-rotating drones ensure every
segment is observed from both directions with minimal gap time.

For SITL, start 2 ArduCopter instances or use:  dso simulate --drones 2
"""

import asyncio

from drone_swarm import Swarm, Waypoint

# Perimeter polygon (5-sided facility boundary)
PERIMETER = [
    (35.3630, -117.6700),
    (35.3630, -117.6670),
    (35.3645, -117.6660),
    (35.3650, -117.6680),
    (35.3640, -117.6705),
]
ALTITUDE = 18
LAPS = 3


async def main():
    swarm = Swarm()
    swarm.add("patrol-cw", "tcp:127.0.0.1:5760")
    swarm.add("patrol-ccw", "tcp:127.0.0.1:5770")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=10.0)

    print("[PATROL] Taking off...")
    await swarm.takeoff(altitude=ALTITUDE)
    await asyncio.sleep(10)

    # Build waypoint loops -- one clockwise, one counter-clockwise
    cw_wps = [Waypoint(lat, lon, ALTITUDE) for lat, lon in PERIMETER]
    ccw_wps = list(reversed(cw_wps))

    try:
        for lap in range(1, LAPS + 1):
            print(f"[PATROL] Lap {lap}/{LAPS}")
            await swarm.assign_mission("patrol-cw", list(cw_wps))
            await swarm.assign_mission("patrol-ccw", list(ccw_wps))
            await swarm.execute_missions()
            await asyncio.sleep(45)
            print(swarm.status_report())
    except KeyboardInterrupt:
        print("\n[PATROL] Interrupted -- returning to base.")

    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()
    print("[PATROL] Patrol complete.")


if __name__ == "__main__":
    asyncio.run(main())
