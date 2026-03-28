#!/usr/bin/env python3
"""
basic_swarm.py -- Simplest possible 3-drone swarm example.

Registers three drones, connects, takes off, holds for 10 seconds,
then returns to launch.

For SITL simulation, start 3 ArduCopter instances first:
    sim_vehicle.py -v ArduCopter --sysid 1 -I 0
    sim_vehicle.py -v ArduCopter --sysid 2 -I 1
    sim_vehicle.py -v ArduCopter --sysid 3 -I 2

Then run:
    python examples/basic_swarm.py
"""

import asyncio

from drone_swarm import Swarm


async def main():
    swarm = Swarm()

    # Register drones (update ports for your setup)
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5770")
    swarm.add("charlie", "tcp:127.0.0.1:5780")

    # Connect to all drones
    print("[EXAMPLE] Connecting...")
    await swarm.connect()
    print(swarm.status_report())

    # Take off to 10 meters
    print("[EXAMPLE] Taking off...")
    await swarm.takeoff(altitude=10)
    await asyncio.sleep(10)
    print(swarm.status_report())

    # Return to launch
    print("[EXAMPLE] Returning to launch...")
    await swarm.rtl()
    await asyncio.sleep(15)

    # Clean shutdown
    await swarm.shutdown()
    print("[EXAMPLE] Done.")


if __name__ == "__main__":
    asyncio.run(main())
