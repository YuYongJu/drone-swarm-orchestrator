# Quickstart

Get a 3-drone swarm flying in simulation in under 5 minutes.

## Prerequisites

- drone-swarm installed (`pip install drone-swarm`)
- ArduPilot SITL installed ([install guide](https://ardupilot.org/dev/docs/building-setup-linux.html))

## Step 1: Start the simulator

drone-swarm can launch ArduPilot SITL instances for you:

```bash
dso simulate --drones 3
```

This starts 3 simulated ArduCopter instances on ports 5760, 5762, and 5763. Wait until you see "SITL Ready" for all 3.

!!! tip
    If you don't have SITL installed, you can still follow along using the
    direct connection example below with a single SITL instance started manually.

## Step 2: Connect and fly

Create a file called `my_first_swarm.py`:

```python
import asyncio
from drone_swarm import Swarm

async def main():
    # Create a swarm and add 3 drones
    swarm = Swarm()
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5762")
    swarm.add("charlie", "tcp:127.0.0.1:5763")

    # Connect to all drones
    print("Connecting...")
    await swarm.connect()
    print(swarm.status_report())

    # Take off to 15 meters
    print("Taking off...")
    await swarm.takeoff(altitude=15)

    # Hold for 10 seconds
    await asyncio.sleep(10)
    print(swarm.status_report())

    # Return to launch
    print("Returning to launch...")
    await swarm.rtl()
    await asyncio.sleep(15)

    # Clean shutdown
    await swarm.shutdown()
    print("Done!")

asyncio.run(main())
```

Run it:

```bash
python my_first_swarm.py
```

You should see all 3 drones connect, arm, take off, hover, and return to launch.

## Step 3: Try a formation

Add formation flying to your script:

```python
from drone_swarm.missions import v_formation

# After takeoff...
formations = v_formation(
    center_lat=-35.3632, center_lon=149.1652,
    altitude=15, num_drones=3, spacing_m=15, heading_deg=0,
)
for drone_id, waypoints in zip(["alpha", "bravo", "charlie"], formations):
    await swarm.assign_mission(drone_id, waypoints)
await swarm.execute_missions()
```

## What's next?

- [Core Concepts](concepts.md) — understand drones, roles, state machines, and missions
- [Formation Flying Tutorial](../tutorials/formations.md) — deep dive into formation patterns
- [API Reference](../api/swarm.md) — full API documentation
