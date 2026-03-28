# Tutorial: Your First Drone Swarm

This tutorial walks you through coordinating 3 simulated drones from scratch. By the end, you'll have drones taking off, flying a formation, and landing — all from Python.

**Time:** 15-30 minutes
**Prerequisites:** Python 3.11+, ArduPilot SITL ([install guide](https://ardupilot.org/dev/docs/building-setup-linux.html))

---

## Step 1: Install drone-swarm

```bash
pip install drone-swarm
```

Verify it worked:

```python
python -c "from drone_swarm import Swarm; print('Ready!')"
```

## Step 2: Start the simulator

The quickest way to get simulated drones running:

```bash
dso simulate --drones 3
```

You should see output like:

```
[SITL] Starting 3 ArduCopter instances...
[SITL] sim-0 ready on tcp:127.0.0.1:5760
[SITL] sim-1 ready on tcp:127.0.0.1:5770
[SITL] sim-2 ready on tcp:127.0.0.1:5780
[SITL] All instances ready. Press Ctrl+C to stop.
```

Leave this running and open a **second terminal** for the next step.

!!! tip "No SITL installed?"
    If you don't have ArduPilot SITL, you can still explore the API using
    mock connections. See the [Simulation Guide](../api/simulation.md) for options.

## Step 3: Connect and take off

Create a file called `first_swarm.py`:

```python
import asyncio
from drone_swarm import Swarm

async def main():
    # Create a swarm
    swarm = Swarm()

    # Add the 3 simulated drones
    swarm.add("alpha", "tcp:127.0.0.1:5760")
    swarm.add("bravo", "tcp:127.0.0.1:5770")
    swarm.add("charlie", "tcp:127.0.0.1:5780")

    # Connect to all drones
    print("Connecting...")
    await swarm.connect()
    print(swarm.status_report())

    # Take off to 15 meters
    print("Taking off...")
    await swarm.takeoff(altitude=15)

    # Wait for drones to reach altitude
    await asyncio.sleep(10)
    print(swarm.status_report())

    # Return to launch
    print("Landing...")
    await swarm.rtl()
    await asyncio.sleep(15)

    # Clean shutdown
    await swarm.shutdown()
    print("Done!")

asyncio.run(main())
```

Run it:

```bash
python first_swarm.py
```

You should see:

```
Connecting...
=== SWARM STATUS ===
  alpha [recon] — connected | pos=(-35.363262, 149.165237, 0.0m) | batt=100% | hdg=353deg
  bravo [recon] — connected | pos=(-35.363262, 149.165237, 0.0m) | batt=100% | hdg=353deg
  charlie [recon] — connected | pos=(-35.363262, 149.165237, 0.0m) | batt=100% | hdg=353deg

Taking off...
[SWARM] 'alpha' armed
[SWARM] 'alpha' taking off to 15.0m
[SWARM] 'bravo' armed
[SWARM] 'bravo' taking off to 15.0m
[SWARM] 'charlie' armed
[SWARM] 'charlie' taking off to 15.0m
```

**Congratulations — you just coordinated 3 drones from Python.**

## Step 4: Add a formation

Now let's make them fly in a V-formation. Replace the sleep after takeoff with:

```python
from drone_swarm.missions import v_formation

# After takeoff...
print("Flying V-formation...")
drone_ids = ["alpha", "bravo", "charlie"]
formations = v_formation(
    center_lat=-35.3632,
    center_lon=149.1652,
    altitude=15,
    num_drones=3,
    spacing_m=15,
    heading_deg=0,
)

for drone_id, waypoints in zip(drone_ids, formations, strict=True):
    await swarm.assign_mission(drone_id, waypoints)
await swarm.execute_missions()

# Wait for formation to converge
await asyncio.sleep(15)
print(swarm.status_report())
```

The drones will spread out into a V-shape with 15-meter spacing. The leader flies to the center point while wingmen take positions offset behind.

## Step 5: Add an area sweep

After the formation, add a coordinated area search:

```python
from drone_swarm.missions import area_sweep

print("Starting area sweep...")
center_lat, center_lon = -35.3632, 149.1652
sweep_missions = area_sweep(
    sw_lat=center_lat - 0.0005,
    sw_lon=center_lon - 0.0005,
    ne_lat=center_lat + 0.0005,
    ne_lon=center_lon + 0.0005,
    altitude=15,
    num_drones=3,
)

for drone_id, waypoints in zip(drone_ids, sweep_missions, strict=True):
    await swarm.assign_mission(drone_id, waypoints)
await swarm.execute_missions()

await asyncio.sleep(15)
print("Sweep complete!")
```

Each drone automatically gets assigned a strip of the search area. They fly parallel tracks with no overlap.

## What you just built

In about 40 lines of Python, you:

1. Connected to 3 drones
2. Coordinated a synchronized takeoff
3. Flew a V-formation
4. Executed a parallel area sweep
5. Returned all drones safely

This same code works on real ArduPilot hardware — just change the connection strings from `tcp:127.0.0.1:5760` to your serial ports.

## Next steps

- [Formation Flying](formations.md) — learn all available formation patterns
- [Custom Missions](custom-missions.md) — build your own mission types
- [API Reference](../api/swarm.md) — full Swarm class documentation
- [Deploying to Real Hardware](../getting-started/concepts.md) — go from simulation to real drones
