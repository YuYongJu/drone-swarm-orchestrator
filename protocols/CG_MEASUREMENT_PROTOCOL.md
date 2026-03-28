---
title: Center of Gravity Measurement Protocol
type: protocol
status: active
created: 2026-03-26
updated: 2026-03-26
tags: [hardware, testing, CG, balance, protocol]
---

# Center of Gravity (CG) Measurement Protocol

A step-by-step guide for measuring the center of gravity on assembled drones. Proper CG is critical for stable flight -- an off-center CG forces some motors to work harder, reduces flight time, and can make the drone uncontrollable in wind.

---

## Why CG Matters

A quadcopter hovers by distributing its weight equally across four motors. If the CG is off-center:

- Motors on the heavy side spin faster to compensate, drawing more current.
- Motors on the light side spin slower, wasting potential thrust.
- The flight controller constantly fights the imbalance, reducing efficiency by 5-20%.
- In wind or aggressive maneuvers, the overworked motors may hit their limits, causing a crash.
- A badly off-center CG (30mm+) can make the drone unflyable.

---

## Equipment Needed

| Item | Notes |
|------|-------|
| Wooden dowel rod (6-8mm diameter) or straight metal rod | Used as the balance point -- must be straight and smooth |
| Alternatively: a thin ruler or straightedge on its edge | Any straight edge that the frame can balance on |
| Ruler (30cm / 12") | For measuring CG offset from the geometric center |
| Fine-tip marker or tape | To mark CG position on the frame |
| Assembled drone (no props) | **Remove propellers before handling** -- always |
| Payload to test with | The actual payload you will fly with |

**Total cost: under $5** (dowel rod + ruler). You probably already have these.

---

## Procedure

### Step 1: Prepare the Drone

1. **Remove all propellers.** You will be handling the drone with your hands near the motors.
2. Install the battery in its normal flight position. Strap it down as you would for flight.
3. Attach all equipment that will be present during flight (camera, companion computer, radio, GPS, etc.).
4. **Do NOT attach the payload yet** -- measure CG without payload first.

### Step 2: Find the Geometric Center

The geometric center of a symmetrical quad frame is the intersection of diagonal lines between opposite motors.

1. Measure the distance between the front-left and rear-right motor mounts. Mark the midpoint.
2. Measure the distance between the front-right and rear-left motor mounts. Mark the midpoint.
3. These midpoints should be the same point (or very close). This is your **geometric center**. Mark it with a small piece of tape or marker dot.

For an asymmetrical frame (like an H-frame or one with a camera mount), the geometric center is still the midpoint between motor positions, even though the frame itself may not be symmetrical.

### Step 3: Measure CG -- Lateral (Left-Right) Axis

1. Place the dowel rod on a flat table, perpendicular to you.
2. Rest the drone across the dowel so the rod runs front-to-back (along the drone's longitudinal axis).
3. Gently release the drone and let it settle. It will tip toward the heavier side.
4. Slide the drone left or right on the dowel until it balances level.
5. The balance point is the lateral CG. Mark it on the frame.
6. Measure the distance from this balance point to the geometric center. This is your **lateral CG offset**.

### Step 4: Measure CG -- Longitudinal (Front-Back) Axis

1. Rotate the drone 90 degrees so the dowel now runs left-to-right (along the lateral axis).
2. Balance the drone on the dowel as before.
3. Slide it forward or backward until it balances level.
4. Mark the balance point. Measure the distance from the geometric center. This is your **longitudinal CG offset**.

### Step 5: Measure CG with Payload

1. Attach your payload to the drone in its intended mount position.
2. Repeat Steps 3 and 4.
3. Record the new CG offset. The difference between no-payload CG and payload CG tells you exactly how much the payload shifts the balance.

### Step 6: Record Your Measurements

**Drone ID**: _______________
**Date**: _______________
**Battery position**: _______________

| Condition | Lateral Offset (mm) | Longitudinal Offset (mm) | Direction |
|-----------|:-------------------:|:------------------------:|-----------|
| No payload | | | e.g., "5mm left, 2mm forward" |
| With payload: _____________ | | | |
| With payload (adjusted): _____________ | | | |

---

## Interpreting CG Offset

| Offset Range | Status | Action |
|:------------:|:------:|--------|
| 0-5 mm | OK | No action needed. This is within normal tolerance for hobby quads. |
| 5-15 mm | CAUTION | Flight is safe but not optimal. Try adjusting battery position first. Monitor motor balance in flight logs (see calibration_engine.py motor health check). |
| 15-30 mm | NEEDS CORRECTION | Add a counterweight on the light side, or reposition the battery/payload. Do not fly in windy conditions until corrected. |
| 30+ mm | DANGEROUS | Do not fly. The flight controller may not be able to compensate. Significant redesign of component placement is needed. |

### Why These Thresholds

On a typical 450mm quad frame:
- 5mm offset means one pair of motors carries roughly 2% more load -- negligible.
- 15mm offset means roughly 7% load imbalance -- noticeable in motor current differences.
- 30mm offset means 13%+ imbalance -- motors on the heavy side may be at 60-70% while light side is at 30-40%, leaving almost no headroom for control authority.

---

## Inputting CG Data into the Loadout Checker

The loadout checker uses CG offset to estimate the efficiency penalty from motor imbalance.

### In the Fleet Registration

Add CG data to the drone's fleet registration file (`fleet/{drone_id}.json`):

```json
{
    "drone_id": "alpha",
    "sysid": 1,
    "hw_class": "D",
    "cg_data": {
        "measured_date": "2026-03-26",
        "no_payload": {
            "lateral_offset_mm": 3,
            "longitudinal_offset_mm": -2,
            "direction": "3mm right, 2mm aft"
        },
        "with_payload": {
            "payload_name": "RPG Grenade",
            "lateral_offset_mm": 8,
            "longitudinal_offset_mm": 12,
            "direction": "8mm right, 12mm forward"
        },
        "battery_position": "center, snug against rear plate",
        "notes": "Moved battery 5mm aft to compensate for payload"
    }
}
```

### After Calibration Flights

The calibration engine (`src/calibration_engine.py`) will automatically detect CG-related issues through motor health analysis:

```bash
python src/calibration_engine.py motors logs/your_session/ --drone alpha
```

This compares actual motor outputs during flight. If motor imbalance correlates with your CG offset, the engine will flag it and suggest corrections.

---

## Tips for Correcting Bad CG

### Battery Placement (First Thing to Try)

The battery is usually the heaviest single component (200-500g). Moving it even 10-15mm can correct most CG issues.

1. Loosen the battery strap.
2. Slide the battery toward the light side.
3. Re-measure CG.
4. Repeat until offset is under 5mm.
5. Mark the optimal battery position on the frame with tape so you can replicate it every flight.

### Counterweights (When Battery Adjustment Is Not Enough)

If moving the battery is not sufficient (common when a heavy payload forces CG off-center):

1. Use small lead or steel weights (fishing weights work well and are cheap).
2. Attach them with double-sided foam tape or zip ties on the light side of the frame.
3. Aim for the minimum weight needed to bring CG within 5mm of center.
4. Secure weights firmly -- they must not shift in flight.

**Weight penalty**: Every gram of counterweight reduces payload capacity and flight time. A 20g counterweight on a 1200g drone costs roughly 1.7% of payload capacity. Prefer repositioning components over adding dead weight.

### Component Rearrangement

If CG is consistently bad, consider moving components:

- **GPS module**: Light (20g) but mounted on a tall mast, so it has leverage. Moving it 30mm can shift CG by 1-2mm.
- **Companion computer** (Raspberry Pi, Jetson Nano): 40-80g. Mount it centered or on the light side.
- **Camera**: If front-mounted, it pulls CG forward. Consider a shorter camera mount or adding the battery further aft.
- **Radio/telemetry module**: Usually light, but can be repositioned easily.

### Payload-Specific Strategies

For drones that carry different payloads on different missions:

1. Measure CG with each payload type.
2. Create a "battery position card" for each payload (e.g., "With RPG grenade: battery at mark B, add 15g counterweight at rear").
3. Include this in your pre-flight checklist.

---

## Integration with Other Tools

| Tool | How CG data is used |
|------|-------------------|
| `src/loadout_checker.py` | Estimates efficiency penalty from CG offset |
| `src/calibration_engine.py` | Motor health check detects CG-related imbalance from flight data |
| `src/preflight.py` | Pre-flight check can verify CG was measured recently |
| `src/flight_report.py` | Post-flight report flags motor imbalance anomalies |

---

#hardware #testing #CG #balance #protocol
