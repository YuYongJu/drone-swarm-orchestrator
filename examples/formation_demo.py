#!/usr/bin/env python3
"""
formation_demo.py -- Formation showcase: V -> line -> circle -> triangle.

Demonstrates all formation types with smooth transitions and a full
rotation.  This is the "wow" demo -- 4 drones cycling through every
available pattern with 10-second holds between transitions.

Sequence:
  1. Takeoff to 20m
  2. V-formation (heading north)
  3. Line formation (heading east)
  4. Circle/orbit formation
  5. Triangle formation
  6. Full 360-degree rotation in triangle
  7. Return to launch

For SITL, start 4 ArduCopter instances or use:  dso simulate --drones 4
"""

import asyncio

from drone_swarm import Swarm

CENTER = (35.363261, -117.669056)
ALT = 20
SPACING = 15
HOLD = 10  # seconds between transitions


async def main():
    swarm = Swarm()
    for i, name in enumerate(["demo-1", "demo-2", "demo-3", "demo-4"]):
        swarm.add(name, f"tcp:127.0.0.1:{5760 + i * 10}")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=5.0)

    print("[DEMO] Taking off...")
    await swarm.takeoff(altitude=ALT)
    await asyncio.sleep(HOLD)

    for pattern in ["v", "line", "circle", "triangle"]:
        print(f"[DEMO] Transitioning to {pattern} formation...")
        await swarm.formation(pattern=pattern, spacing=SPACING,
                              center=CENTER, altitude=ALT)
        await asyncio.sleep(HOLD)
        print(swarm.status_report())

    # Full rotation in the final (triangle) formation
    print("[DEMO] Rotating 360 degrees...")
    await swarm.rotate(degrees=360, duration_s=30, spacing=SPACING)

    print("[DEMO] Show complete. Returning to launch.")
    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
