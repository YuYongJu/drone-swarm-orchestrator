# Tutorial: Formation Flying

Learn how to coordinate drones into geometric patterns using drone-swarm's built-in formation library.

---

## Available Formations

| Formation | Function | Min Drones | Description |
|-----------|----------|-----------|-------------|
| V-Shape | `v_formation()` | 3 | Classic chevron with leader at front |
| Line | `line_formation()` | 2 | Single file along a heading |
| Area Sweep | `area_sweep()` | 2 | Parallel lawnmower tracks over an area |
| Orbit | `orbit_point()` | 1 | Circular pattern around a GPS point |

## V-Formation

The classic military chevron. One drone leads, others form a V behind it.

```python
from drone_swarm.missions import v_formation

formations = v_formation(
    center_lat=-35.3632,     # GPS latitude of formation center
    center_lon=149.1652,     # GPS longitude
    altitude=20,             # meters above home
    num_drones=5,            # number of drones
    spacing_m=15,            # distance between adjacent drones
    heading_deg=90,          # formation heading (east)
)
# Returns: list of waypoint lists, one per drone
# formations[0] = leader waypoints
# formations[1], formations[2] = left/right wingmen
```

**How it works:**
- Drone 0 (leader) flies to the center point
- Odd-numbered drones offset to the left and behind
- Even-numbered drones offset to the right and behind
- Spacing is measured diagonally between adjacent drones

## Line Formation

Single file — drones fly in a straight line along a heading.

```python
from drone_swarm.missions import line_formation

formations = line_formation(
    center_lat=-35.3632,
    center_lon=149.1652,
    altitude=20,
    num_drones=4,
    spacing_m=10,            # distance between each drone
    heading_deg=180,         # line runs north-south
)
```

**Use cases:** Corridor search, power line inspection, border patrol.

## Area Sweep

Divides a rectangular area into parallel strips — one per drone — for efficient coverage.

```python
from drone_swarm.missions import area_sweep

missions = area_sweep(
    sw_lat=-35.364,          # southwest corner
    sw_lon=149.164,
    ne_lat=-35.362,          # northeast corner
    ne_lon=149.166,
    altitude=30,
    num_drones=3,
)
# Each drone gets 2 waypoints defining its strip (south end, north end)
```

**How it works:**
- The area is divided into N vertical strips (one per drone)
- Each drone flies a north-south track within its strip
- No overlap between strips

**Use cases:** Search and rescue, crop mapping, site surveying.

## Orbit

Drones fly a circular path around a point of interest. Multiple drones are evenly spaced around the circle.

```python
from drone_swarm.missions import orbit_point

missions = orbit_point(
    center_lat=-35.3632,
    center_lon=149.1652,
    altitude=25,
    radius_m=50,             # orbit radius
    num_drones=3,
    points_per_orbit=12,     # waypoints per full circle
)
# Each drone gets 12 waypoints around the circle
# Drones start at evenly-spaced phase offsets (120 deg apart for 3 drones)
```

**Use cases:** Perimeter surveillance, point-of-interest monitoring, drone shows.

## Assigning Formations to a Swarm

All formation functions return a list of waypoint lists. Assign them to drones:

```python
drone_ids = list(swarm.drones.keys())
formations = v_formation(lat, lon, alt, num_drones=len(drone_ids), spacing_m=15)

for drone_id, waypoints in zip(drone_ids, formations, strict=True):
    await swarm.assign_mission(drone_id, waypoints)

await swarm.execute_missions()
```

## Custom Formations

You can create any formation by computing waypoints manually:

```python
from drone_swarm.drone import Waypoint

# Diamond formation
diamond = [
    [Waypoint(lat, lon + 0.0001, 20)],          # north
    [Waypoint(lat - 0.0001, lon, 20)],           # west
    [Waypoint(lat, lon - 0.0001, 20)],           # south
    [Waypoint(lat + 0.0001, lon, 20)],           # east
]

for drone_id, waypoints in zip(drone_ids, diamond, strict=True):
    await swarm.assign_mission(drone_id, waypoints)
await swarm.execute_missions()
```

## Tips

- **Spacing matters.** Too close (< 5m) risks collision. Too far (> 50m) loses visual cohesion.
  Start with 15m for testing.
- **Heading affects layout.** A V-formation at heading 0 (north) looks different from heading 90 (east).
  The leader always faces the heading direction.
- **Altitude is consistent.** All drones in a formation fly at the same altitude by default.
  For altitude staggering (safer), assign different altitudes manually.
- **Wind affects formation accuracy.** In simulation, formations are pixel-perfect. In real flight,
  expect 2-5m drift depending on wind. The SDK does not currently correct for drift
  (planned for v0.5 with formation feedback loop).
