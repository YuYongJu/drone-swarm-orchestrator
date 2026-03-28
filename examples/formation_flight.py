#!/usr/bin/env python3
"""
formation_flight.py -- V-formation demo.

Takes off 3 drones and moves them into a V-formation, then returns.
"""

import asyncio

from drone_swarm import Swarm

DEMO_LAT = 35.363261
DEMO_LON = -117.669056


async def main():
    swarm = Swarm()
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5770")
    swarm.add("charlie", "tcp:127.0.0.1:5780")

    await swarm.connect()

    # Take off
    await swarm.takeoff(altitude=15)
    await asyncio.sleep(10)

    # V-formation
    print("[EXAMPLE] Moving to V-formation...")
    await swarm.formation(
        pattern="v",
        spacing=15,
        heading=0,
        center=(DEMO_LAT, DEMO_LON),
        altitude=15,
    )
    await asyncio.sleep(10)
    print(swarm.status_report())

    # Switch to line formation
    print("[EXAMPLE] Switching to line formation...")
    await swarm.formation(pattern="line", spacing=20, heading=90)
    await asyncio.sleep(10)

    # RTL
    await swarm.rtl()
    await asyncio.sleep(15)
    await swarm.shutdown()
    print("[EXAMPLE] Done.")


if __name__ == "__main__":
    asyncio.run(main())
