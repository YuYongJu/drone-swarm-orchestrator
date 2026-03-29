#!/usr/bin/env python3
"""
drone_light_show.py -- Choreographed drone formation show with 5 drones.

Demonstrates time-synchronized formation transitions that could be set to
music for a drone light show.  Each "act" holds a formation for a set
duration, then transitions to the next.

Sequence:
  1. Line formation (parade entry)
  2. V-formation (flyover)
  3. Circle (orbit around center)
  4. 360-degree rotation (spinning wheel)
  5. Expand to wide V
  6. Collapse to tight line (finale)
  7. Return to launch

Use case: Entertainment drone shows, event demonstrations, marketing
video footage. The timed sequences can be synced with music or lighting.

For SITL: dso simulate --drones 5
"""

import asyncio

from drone_swarm import Swarm

CENTER = (35.363261, -117.669056)
ALT = 25
DRONE_COUNT = 5


async def act(swarm: Swarm, name: str, pattern: str, spacing: float,
              heading: float = 0.0, hold_s: float = 10.0) -> None:
    """Execute one show act: transition to formation, hold, report."""
    print(f"  Act: {name}")
    await swarm.formation(
        pattern=pattern, spacing=spacing,
        heading=heading, center=CENTER, altitude=ALT,
    )
    await asyncio.sleep(hold_s)


async def main():
    swarm = Swarm()
    for i in range(DRONE_COUNT):
        swarm.add(f"show-{i+1}", f"tcp:127.0.0.1:{5760 + i * 10}")

    await swarm.connect()
    swarm.enable_collision_avoidance(min_distance_m=5.0)

    print("[SHOW] Taking off...")
    await swarm.takeoff(altitude=ALT)
    await asyncio.sleep(12)

    print("[SHOW] Starting show sequence...")

    # Act 1: Parade entry — tight line heading north
    await act(swarm, "Parade Entry", "line", spacing=10, heading=0)

    # Act 2: V-formation flyover heading east
    await act(swarm, "V-Formation Flyover", "v", spacing=15, heading=90)

    # Act 3: Circle orbit
    await act(swarm, "Orbital Ring", "circle", spacing=30, hold_s=15)

    # Act 4: Spinning wheel — 360-degree rotation
    print("  Act: Spinning Wheel")
    await swarm.rotate(degrees=360, duration_s=20, spacing=20)

    # Act 5: Wide V heading south
    await act(swarm, "Wide V Spread", "v", spacing=25, heading=180)

    # Act 6: Tight collapse — finale
    await act(swarm, "Finale Collapse", "line", spacing=6, heading=0, hold_s=8)

    print("[SHOW] Show complete! Returning to launch.")
    await swarm.rtl()
    await asyncio.sleep(20)
    await swarm.shutdown()
    print("[SHOW] All drones landed safely.")


if __name__ == "__main__":
    asyncio.run(main())
