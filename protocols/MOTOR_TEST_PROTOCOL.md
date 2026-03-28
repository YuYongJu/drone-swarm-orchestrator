---
title: Motor Thrust Test Protocol
type: protocol
status: active
created: 2026-03-26
updated: 2026-03-26
tags: [hardware, testing, motors, thrust-stand, protocol]
---

# Motor Thrust Test Protocol

A step-by-step guide for running a motor thrust test at a maker space (e.g., Northeastern EXP labs). Written for someone who has never done this before.

The goal: measure how much thrust and current your motor+prop+battery combination actually produces at each throttle level. This data feeds directly into the loadout checker for accurate flight time and performance predictions.

---

## Safety Warnings

> **Spinning propellers are extremely dangerous.** A 10-inch prop at full throttle can sever fingers, cut skin to the bone, and throw debris at high speed. Treat every powered prop like a table saw blade.

1. **Wear safety glasses** at all times during the test. No exceptions.
2. **Secure the motor mount** to the table with C-clamps or bolts. If the mount breaks free at full throttle, it becomes a projectile.
3. **Keep hands, hair, and loose clothing away** from the propeller arc at all times. Never reach over or near a spinning prop.
4. **Stand behind the motor**, not in the plane of the propeller. If a prop blade breaks, fragments fly outward in the prop plane.
5. **Use a power cut switch** (ESC arming switch or XT60 disconnect) so you can kill power instantly without reaching near the prop.
6. **Test in a well-ventilated area** -- LiPo batteries can vent toxic fumes if shorted or damaged.
7. **Have a LiPo fire bag and extinguisher** nearby.
8. **Never leave a connected LiPo unattended.**
9. **If anything feels wrong -- vibration, strange noise, burning smell -- cut power immediately.**

---

## Equipment Needed

| Item | Notes | Approximate Cost |
|------|-------|-----------------|
| Motor under test | The motor you want to characterize | varies |
| ESC (Electronic Speed Controller) | Must be rated for the motor's max current + 20% margin | $15-30 |
| Propeller(s) to test | Match motor KV range; have spares, they break | $2-5 each |
| LiPo battery | Matched cell count (3S/4S/6S), enough C-rating for the motor | $25-60 |
| Watt meter (inline power meter) | E.g., GT Power 150A -- reads voltage, current, watts, mAh | $15-25 |
| Digital scale | At least 5 kg capacity, 1g resolution | $15-30 |
| Thrust test stand / mount board | A piece of 3/4" plywood (12"x6") with the motor mounted so thrust pushes down onto the scale | $5 (DIY) |
| Servo tester or throttle source | A $5 servo tester knob, or use a transmitter+receiver | $5-15 |
| C-clamps (x2) | To secure the mount board to the table | $5 |
| Zip ties | To secure ESC and wires to the mount board | $2 |
| Safety glasses | Polycarbonate, ANSI Z87+ rated | $5 |
| Digital tachometer (optional) | Measures RPM -- helps verify motor health | $15-25 |
| Notebook or laptop | For recording data | -- |

**Total budget: roughly $90-200** (excluding motor, ESC, battery, and prop which you likely already have).

---

## Test Stand Setup

```
                  +-----------+
                  |   Motor   |  <- Mounted upside-down (thrust pushes DOWN)
                  |  + Prop   |
                  +-----+-----+
                        |
              +---------+---------+
              |    Mount Board    |  <- 3/4" plywood, motor bolted through
              |  (12" x 6")      |
              +---------+---------+
                        |
                   +----+----+
                   |  Scale  |  <- Digital kitchen/postal scale
                   +---------+

     [Battery] ---[Watt Meter]---[ESC]---[Motor]
                                  |
                          [Servo Tester]
                          (throttle knob)
```

### Setup Instructions

1. **Mount the motor** to the plywood board using the motor's mounting screws. The motor should point DOWN so that thrust pushes the board onto the scale. Use all mounting holes -- do not skip any.

2. **Attach the propeller** to the motor shaft. Ensure the correct rotation direction (most props are marked). Tighten the prop nut firmly -- a loose prop is dangerous.

3. **Secure the ESC** to the mount board with zip ties. Connect the motor's three wires to the ESC (order doesn't matter for direction; if the motor spins backward, swap any two).

4. **Wire the power path**: Battery -> Watt meter -> ESC. Use an XT60 connector as your safety disconnect between the battery and watt meter.

5. **Connect the servo tester** to the ESC's signal wire (the thin 3-wire connector). Set the servo tester to minimum position before connecting power.

6. **Place the mount board on the scale.** The scale should be on a flat, stable surface. The motor+board will rest on the scale, and thrust will push down, increasing the reading.

7. **Clamp the mount board edges** to the table with C-clamps so it cannot tip over. The board should only be able to move vertically (compressing down onto the scale).

8. **Tare the scale to zero** with the unpowered motor+board+prop sitting on it. Now the scale reads only thrust force.

9. **ESC calibration**: With the servo tester at maximum, connect the battery. The ESC should beep its calibration sequence. Then move the servo tester to minimum. The ESC should confirm with beeps. This sets the throttle range. (Consult your ESC's manual for its specific procedure.)

---

## Test Procedure

**Before starting**: Verify the servo tester is at 0% throttle. Verify the prop is tight. Put on safety glasses. Clear the area.

For each throttle increment, hold the throttle steady for **5 seconds** to let readings stabilize, then record the values.

### Data Recording Template

Copy this table into your notebook or spreadsheet:

**Test ID**: _______________
**Date**: _______________
**Motor**: _______________  (model, KV)
**Prop**: _______________  (size, e.g., 1045 = 10" diameter, 4.5" pitch)
**Battery**: _______________ (cells, mAh, C-rating)
**ESC**: _______________
**Ambient temp**: _______  C
**Notes**: _______________

| Throttle % | Thrust (g) | Current (A) | Watts (W) | Voltage (V) | RPM (optional) | Notes |
|:----------:|:----------:|:-----------:|:---------:|:-----------:|:--------------:|:-----:|
| 0 | 0 | 0 | 0 | -- | -- | baseline |
| 10 | | | | | | |
| 20 | | | | | | |
| 30 | | | | | | |
| 40 | | | | | | |
| 50 | | | | | | |
| 60 | | | | | | |
| 70 | | | | | | |
| 80 | | | | | | |
| 90 | | | | | | |
| 100 | | | | | | hold briefly |

### Procedure Steps

1. Connect the battery (servo tester at 0%). ESC should arm.
2. Zero / tare the scale.
3. Reset the watt meter's mAh counter if it has one.
4. Slowly increase throttle to **10%**. Wait 5 seconds for readings to stabilize. Record thrust, current, watts, and voltage.
5. Increase to **20%**. Wait, record.
6. Continue in 10% increments up to **100%**.
7. At 100%, **hold for no more than 5-10 seconds** -- full throttle generates a lot of heat. Record quickly.
8. Return throttle to 0% immediately after the 100% reading.
9. Disconnect the battery.
10. Feel the motor -- if it is too hot to touch, let it cool before the next run. Warm is normal; burning hot means something is wrong.

**Repeat the test 2-3 times** and average the results for more reliable data.

---

## Expected Results for Common Motors

Use these as sanity checks. If your readings are wildly different, something may be wrong with your setup.

### EMAX MT2212 920KV with 1045 prop on 3S

| Throttle % | Thrust (g) | Current (A) |
|:----------:|:----------:|:-----------:|
| 50 | ~350 | ~4.5 |
| 75 | ~550 | ~9.0 |
| 100 | ~750 | ~14.0 |

### EMAX MT2212 920KV with 1045 prop on 4S

| Throttle % | Thrust (g) | Current (A) |
|:----------:|:----------:|:-----------:|
| 50 | ~450 | ~5.5 |
| 75 | ~700 | ~11.0 |
| 100 | ~900 | ~18.0 |

### SunnySky X2212 980KV with 1047 prop on 4S

| Throttle % | Thrust (g) | Current (A) |
|:----------:|:----------:|:-----------:|
| 50 | ~400 | ~5.0 |
| 75 | ~650 | ~10.0 |
| 100 | ~850 | ~16.0 |

**Typical efficiency**: 5-8 g/W at 50% throttle is normal for these motors. Below 4 g/W suggests a problem (wrong prop, damaged motor, etc.).

---

## Entering Data into the Parts Database

After your test, format the results as JSON and add them to the motor's entry in `src/parts_db/motors.json`.

### JSON Format

Each motor entry has a `thrust_tests` object. The key format is `{cells}S_{prop_size}` (e.g., `4S_1045`):

```json
{
    "id": "emax_mt2212_920kv",
    "name": "EMAX MT2212 920KV",
    "kv": 920,
    "max_current_a": 18,
    "weight_g": 56,
    "shaft_diameter_mm": 3.175,
    "thrust_tests": {
        "3S_1045": [
            {"throttle_pct": 10, "thrust_g": 75, "current_a": 0.8},
            {"throttle_pct": 20, "thrust_g": 160, "current_a": 1.6},
            {"throttle_pct": 30, "thrust_g": 250, "current_a": 2.8},
            {"throttle_pct": 40, "thrust_g": 340, "current_a": 3.8},
            {"throttle_pct": 50, "thrust_g": 350, "current_a": 4.5},
            {"throttle_pct": 60, "thrust_g": 450, "current_a": 6.0},
            {"throttle_pct": 70, "thrust_g": 520, "current_a": 7.5},
            {"throttle_pct": 80, "thrust_g": 600, "current_a": 9.5},
            {"throttle_pct": 90, "thrust_g": 680, "current_a": 12.0},
            {"throttle_pct": 100, "thrust_g": 750, "current_a": 14.0}
        ],
        "4S_1045": [
            {"throttle_pct": 10, "thrust_g": 95, "current_a": 1.0},
            {"throttle_pct": 20, "thrust_g": 200, "current_a": 2.1},
            {"throttle_pct": 30, "thrust_g": 310, "current_a": 3.5},
            {"throttle_pct": 40, "thrust_g": 420, "current_a": 5.0},
            {"throttle_pct": 50, "thrust_g": 450, "current_a": 5.5},
            {"throttle_pct": 60, "thrust_g": 560, "current_a": 7.5},
            {"throttle_pct": 70, "thrust_g": 650, "current_a": 9.5},
            {"throttle_pct": 80, "thrust_g": 750, "current_a": 12.0},
            {"throttle_pct": 90, "thrust_g": 830, "current_a": 15.0},
            {"throttle_pct": 100, "thrust_g": 900, "current_a": 18.0}
        ]
    }
}
```

### Steps to Add Your Data

1. Open `src/parts_db/motors.json` in a text editor.
2. Find the motor entry by its `id` field, or create a new entry if the motor is not yet listed.
3. Add a new key under `thrust_tests` with the format `{cells}S_{prop_size}`.
4. Enter each throttle step as an object with `throttle_pct`, `thrust_g`, and `current_a`.
5. Save the file.
6. Run `python src/loadout_checker.py --list motors` to verify the data loaded correctly.

---

## Troubleshooting

### Motor vibrates excessively
- **Prop is not balanced.** Try a different prop or balance it (tape on the light blade).
- **Prop is cracked or chipped.** Replace it.
- **Motor mounting screws are loose.** Tighten all mounting hardware.
- **Motor bearings are worn.** Spin the motor by hand -- it should spin freely and quietly. Grinding = bad bearings.

### ESC beeps continuously (won't arm)
- **Throttle not at zero.** The ESC requires minimum throttle to arm. Set servo tester to 0%.
- **ESC needs calibration.** Follow the calibration procedure in the setup section above.
- **Battery voltage too low.** Check the battery voltage with a multimeter or cell checker. A 4S battery should read 14.8-16.8V.
- **Signal wire not connected properly.** Ensure the signal wire (usually white or orange) is on the correct pin.

### Readings seem wrong (too low thrust, too high current)
- **Wrong prop direction.** If thrust is very low, the prop may be on backward (pushing air up instead of down). Flip it.
- **Battery is nearly empty.** A depleted battery has high internal resistance and cannot deliver full current. Charge it fully before testing.
- **Watt meter is on the wrong scale.** Ensure it is reading amps, not milliamps.
- **Scale is not tared.** Re-tare with the motor assembly on the scale, power off.
- **Motor is too small for the prop.** A high-KV motor with an oversized prop will draw excessive current and produce little thrust. Check the recommended prop range.

### Motor gets very hot
- **Prop is too large or too high pitch.** The motor is overloaded. Try a smaller or lower-pitch prop.
- **ESC is undersized.** If the ESC is near its current limit, it may overheat. Use a higher-rated ESC.
- **Motor windings are damaged.** If the motor is hot even at low throttle with the correct prop, the windings may be shorted. Replace the motor.

---

## After Testing

1. Enter the data into the parts database (see above).
2. Run the loadout checker to see how the real data changes your flight predictions:
   ```
   python src/loadout_checker.py --motor your_motor_id --prop your_prop_id --battery your_battery_id --frame your_frame_id
   ```
3. The loadout checker will automatically use your measured thrust curve instead of estimated values and mark the data confidence as "measured."
4. After your first real flight, run the calibration engine to further refine accuracy:
   ```
   python src/calibration_engine.py calibrate logs/your_session/ --drone your_drone_id
   ```

---

#hardware #testing #motors #protocol
