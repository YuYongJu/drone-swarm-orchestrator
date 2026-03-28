#!/usr/bin/env python3
"""
area_sweep.py -- Area sweep mission demo.

Divides a rectangular area into strips and assigns one strip per drone.
"""

import asyncio

from drone_swarm import Swarm

# Define the search area (SW corner and NE corner)
SW = (35.3628, -117.6695)
NE = (35.3638, -117.6685)


async def main():
    swarm = Swarm()
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5770")
    swarm.add("charlie", "tcp:127.0.0.1:5780")

    await swarm.connect()
    await swarm.takeoff(altitude=12)
    await asyncio.sleep(10)

    # Execute area sweep
    print("[EXAMPLE] Starting area sweep...")
    await swarm.sweep(bounds=[SW, NE], altitude=12)
    await asyncio.sleep(30)
    print(swarm.status_report())

    # RTL
    await swarm.rtl()
    await asyncio.sleep(15)
    await swarm.shutdown()
    print("[EXAMPLE] Done.")


if __name__ == "__main__":
    asyncio.run(main())
