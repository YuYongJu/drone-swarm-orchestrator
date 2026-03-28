#!/usr/bin/env python3
"""
simulate.py -- Pure simulation example (no hardware required).

Uses Swarm.simulate() to launch SITL instances and get a connected swarm
in one call. Requires ArduPilot SITL binaries installed.

Install SITL:
    https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html

Run:
    python examples/simulate.py
"""

import asyncio

from drone_swarm import Swarm


async def main():
    # Launch 3 simulated drones and get a connected swarm
    print("[SIM] Starting 3 SITL instances...")
    swarm, sim = await Swarm.simulate(n_drones=3, speedup=1)
    print(swarm.status_report())

    # Take off
    print("[SIM] Taking off...")
    await swarm.takeoff(altitude=15)
    await asyncio.sleep(10)
    print(swarm.status_report())

    # Return to launch
    print("[SIM] Returning to launch...")
    await swarm.rtl()
    await asyncio.sleep(15)

    # Clean up
    await swarm.shutdown()
    await sim.stop()
    print("[SIM] Simulation complete.")


if __name__ == "__main__":
    asyncio.run(main())
