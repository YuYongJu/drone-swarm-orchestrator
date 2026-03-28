#!/usr/bin/env python3
"""
demo_video.py -- The script shown in the demo video.

12 lines of meaningful code. 3 drones. Triangle formation.
Full rotation. Landing. That's the wow moment.

For SITL: dso simulate --drones 3 (in another terminal)
For real hardware: update connection strings below.
"""

import asyncio

from drone_swarm import Swarm


async def main():
    swarm = Swarm()
    swarm.add("alpha", "udp:127.0.0.1:14550")
    swarm.add("bravo", "udp:127.0.0.1:14560")
    swarm.add("charlie", "udp:127.0.0.1:14570")

    await swarm.connect()
    await swarm.takeoff(altitude=15)
    await swarm.formation("triangle", spacing=10)
    await swarm.rotate(degrees=360, duration_s=30)
    await swarm.land()
    await swarm.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
