---
title: Ground Station UI/UX Design
type: design
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, ui, frontend]
---

# Drone Swarm Orchestrator -- Ground Station UI/UX Design Document

Version 1.0 | Target: Field operators in outdoor/harsh conditions

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Design Concept: Mission Feed](#design-concept-mission-feed)
3. [Design System](#design-system)
4. [Screen 1: Mission Control (Main Screen)](#screen-1-mission-control-main-screen)
5. [Screen 2: Mission Planner (Pre-Flight)](#screen-2-mission-planner-pre-flight)
6. [Screen 3: Fleet Manager](#screen-3-fleet-manager)
7. [Screen 4: Pre-Flight Check Screen](#screen-4-pre-flight-check-screen)
8. [Screen 5: Telemetry Dashboard](#screen-5-telemetry-dashboard)
9. [Screen 6: Mission Replay](#screen-6-mission-replay)
10. [Screen 7: Tablet and Mobile Mode](#screen-7-tablet-and-mobile-mode)
11. [Screen 8: Drone Loadout Builder](#screen-8-drone-loadout-builder)
12. [Component Architecture (Next.js)](#component-architecture-nextjs)
13. [Interaction Patterns](#interaction-patterns)
14. [Keyboard Shortcuts](#keyboard-shortcuts)
15. [Accessibility and Field Ergonomics](#accessibility-and-field-ergonomics)

---

## Design Principles

1. **Glove-first**: Every interactive element must be operable with thick work gloves. No hover states as primary interactions. Minimum touch target: 48x48px.
2. **Sunlight-readable**: Dark theme with high-contrast accents. No pastel or low-contrast elements. All text meets WCAG AAA contrast ratio (7:1) against its background.
3. **Safety-critical clarity**: Destructive or irreversible actions (arm, takeoff, emergency stop) are visually distinct and require confirmation. The Emergency Stop button is always visible and reachable.
4. **Progressive disclosure**: Show only what is needed for the current task. Details are one tap away, never zero taps in the way.
5. **Offline-resilient**: The UI must degrade gracefully when telemetry drops. Stale data is marked with a timestamp badge, never shown as current.

---

## Design Concept: Mission Feed

The Mission Feed is the central nervous system of the operator experience. Instead of burying events in a telemetry tab's event log, the feed is a persistent, always-visible, real-time scrolling log of **everything** happening in the swarm: drone events, swarm-level events, telemetry alerts, system messages, and operator commands (echoed back as confirmation).

### Why a Feed?

Military and field operators are trained on radio logs. Under stress, a scrolling text feed is **faster to parse than charts or dashboards**. Operators can glance at the feed and immediately know what happened in the last 30 seconds without interpreting axes, legends, or color gradients. The Mission Feed borrows this instinct and combines it with a modern terminal/chat aesthetic.

### Appearance

- **Font**: `Geist Mono 13px`, the entire feed is monospace for scannable alignment.
- **Background**: `--bg-secondary` with 1px `--border` left edge separator.
- **Color-coding**: Each entry's timestamp and drone ID are tinted with that drone's role color (`--drone-recon`, `--drone-relay`, `--drone-strike`, `--drone-decoy`). Swarm-level and system messages use `--text-secondary`.
- **Severity icons**: Inline prefix icons -- `[i]` info (gray), `[!]` warning (amber), `[!!]` critical (red, bold). Critical entries have a `--danger` left-border accent (3px).
- **Operator commands**: When the operator issues a command (e.g., RTL All), the feed echoes it back with a `>` prefix and `--text-muted` color, confirming what was sent.

### Entry Types

| Type | Prefix | Example |
| --- | --- | --- |
| Drone event | Drone ID in role color | `14:23:07 alpha  [i] armed` |
| Swarm event | `SWARM` in white | `14:23:12 SWARM  [i] mission started -- 3 drones active` |
| Telemetry alert | Drone ID in role color | `14:24:02 charlie [!] battery 28%` |
| Critical alert | Drone ID in role color, bold | `14:25:17 charlie [!!] CONNECTION LOST` |
| System message | `SYS` in muted | `14:20:01 SYS    [i] WebSocket connected` |
| Operator command | `> CMD` in muted | `14:23:06 > CMD  arm all` |

### Scroll Behavior

- Auto-scrolls to the newest entry by default.
- Scrolling up pauses auto-scroll; a floating "Jump to latest" pill button appears at the bottom of the feed.
- Max 2000 entries displayed; older entries are virtualized out of the DOM (`react-window`) but remain in memory for scroll-back.

### Notification Overlay (Streak Alerts)

Critical events do not just appear in the feed -- they **streak across the map** as overlay notifications, inspired by livestream donation/subscription alerts:

- **Trigger events**: Drone lost, battery critical (<10%), geofence breach, crash/impact detected.
- **Appearance**: A semi-transparent banner (`--bg-secondary` at 92% opacity) that slides in from the right edge of the map view, spanning the full width of the map area. Height: 56px. Left accent border: 4px solid `--danger`. Content: severity icon + bold white message text + drone role color indicator dot.
- **Animation**: Slides in over 300ms (`cubic-bezier(0.4, 0, 0.2, 1)`), holds for 5 seconds, then fades out over 500ms. Tap/click dismisses immediately.
- **Stacking**: If multiple critical alerts fire in quick succession, they stack vertically from the top of the map. Maximum 3 visible overlays at a time; if a 4th arrives, the oldest is dismissed immediately to make room.
- **Audio**: Each overlay triggers the same alarm tone as the existing Alert Bar (2-second tone). Overlays do not repeat the alarm on 10-second intervals -- that behavior remains on the Alert Bar for unacknowledged alerts.

### Responsive Behavior

| Breakpoint | Feed Placement |
| --- | --- |
| Desktop (>1200px) | Persistent right panel, 320px wide, always visible alongside map |
| Tablet landscape (768-1200px) | Hidden by default; swipe RIGHT from right edge to reveal as overlay panel |
| Tablet portrait (600-768px) | Bottom drawer, swipe up to reveal, 40% viewport height |
| Phone (<600px) | **Primary view** -- full-screen scrolling feed is the default; map is a collapsible thumbnail header |

On phone, the feed IS the main interface. The rationale: on a small screen, a map with tiny drone markers is nearly useless. A text feed with color-coded entries gives the operator more actionable information per square centimeter.

---

## Design System

### Color Palette

| Token                  | Hex       | Usage                                      |
| ---------------------- | --------- | ------------------------------------------ |
| `--bg-primary`         | `#0F1117` | App background                             |
| `--bg-secondary`       | `#1A1D27` | Cards, panels, sidebar                     |
| `--bg-tertiary`        | `#252836` | Hover states, active rows                  |
| `--border`             | `#2E3247` | Borders, dividers                          |
| `--text-primary`       | `#F1F3F9` | Primary text                               |
| `--text-secondary`     | `#9BA1B7` | Secondary/label text                       |
| `--text-muted`         | `#5C6178` | Disabled text, timestamps                  |
| `--drone-recon`        | `#3B82F6` | Recon role color (blue)                    |
| `--drone-relay`        | `#22C55E` | Relay role color (green)                   |
| `--drone-strike`       | `#EF4444` | Strike role color (red)                    |
| `--drone-decoy`        | `#EAB308` | Decoy role color (yellow)                  |
| `--status-connected`   | `#22C55E` | Connected/healthy                          |
| `--status-armed`       | `#F59E0B` | Armed (caution)                            |
| `--status-airborne`    | `#3B82F6` | In flight                                  |
| `--status-lost`        | `#EF4444` | Connection lost                            |
| `--status-rtl`         | `#A855F7` | Returning to launch                        |
| `--danger`             | `#DC2626` | Emergency stop, critical alerts            |
| `--danger-bg`          | `#450A0A` | Emergency stop button background           |
| `--warning`            | `#F59E0B` | Warnings                                   |
| `--success`            | `#22C55E` | Checks passed, confirmations               |

### Typography

| Usage              | Font Family  | Weight | Size   | Line Height |
| ------------------ | ------------ | ------ | ------ | ----------- |
| Page title         | Geist Sans   | 700    | 24px   | 32px        |
| Section heading    | Geist Sans   | 600    | 18px   | 24px        |
| Body / labels      | Geist Sans   | 400    | 14px   | 20px        |
| Button text        | Geist Sans   | 600    | 14px   | 20px        |
| Telemetry values   | Geist Mono   | 500    | 16px   | 24px        |
| Coordinates / IDs  | Geist Mono   | 400    | 13px   | 18px        |
| Badge / chip text  | Geist Sans   | 600    | 12px   | 16px        |

Minimum font size across the entire application: **14px** (exception: badge/chip text at 12px uses bold weight and high-contrast colors to compensate).

### Spacing Scale

Base unit: 4px. Standard increments: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.

### Border Radius

- Cards / Panels: 8px
- Buttons: 6px
- Badges / Chips: 4px
- Map overlays: 12px

### Elevation / Shadows

Shadows are used sparingly. Only floating elements (modals, dropdowns, toasts) receive a shadow:
- `--shadow-float`: `0 8px 32px rgba(0, 0, 0, 0.5)`
- `--shadow-popup`: `0 4px 16px rgba(0, 0, 0, 0.4)`

### Iconography

Use Lucide icons throughout. Minimum icon size: 20x20px. Clickable icons: 24x24px inside a 48x48px tap target. Icons are `--text-secondary` by default, `--text-primary` on active/hover.

### Motion

- Duration: 150ms for micro-interactions, 300ms for panel transitions.
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)` for most transitions.
- Respect `prefers-reduced-motion`.
- Map animations (drone movement): 100ms interpolation for smooth position updates.

---

## Screen 1: Mission Control (Main Screen)

This is the primary operational screen. Operators spend 90%+ of their time here during active missions.

### Layout (z-index, bottom to top)

```
+----------------------------------------------------------------------+
| TOP BAR (h: 48px, sticky)                                 [E-STOP]   |
+--------+----------------------------------------------+--------------+
|        |                                              |              |
| FLEET  |              MAP (~60% width)                | MISSION      |
| PANEL  |                                              | FEED         |
|(w:300px|        (Leaflet/Mapbox GL JS)                | (w:320px)    |
|collaps-|                                              |              |
| ible)  |   [Notification Overlay banners float here]  | [scrolling   |
|        |                                              |  real-time   |
|        |                                              |  event log]  |
+--------+----------------------------------------------+--------------+
| BOTTOM ACTION BAR (h: 64px, sticky)                                  |
+----------------------------------------------------------------------+
```

The desktop layout is a **3-column design**: Fleet sidebar (left, 300px collapsible), Map (center, fluid ~60%), and Mission Feed (right, 320px persistent). The Mission Feed replaces the old concept of a separate event log in the Telemetry tab -- events are now surfaced here in real-time during active missions.

### Mission Feed Panel (Right Sidebar)

- **Width**: 320px, always visible on desktop (>1200px). On tablet, accessible via swipe (see Screen 7).
- **Background**: `--bg-secondary`.
- **Header**: "Mission Feed" label + unread critical count badge (red pill) + filter dropdown (All / Critical / Warnings / Commands).
- **Feed entries**: As specified in [Design Concept: Mission Feed](#design-concept-mission-feed). Each entry is a single line (or wraps to 2 lines max) in `Geist Mono 13px`. Entries are color-coded by the originating drone's role color. Timestamps are left-aligned, messages right of the timestamp.
- **Entry format example**:
  ```
  14:23:07  alpha   [i] armed
  14:23:08  bravo   [i] armed
  14:23:12  SWARM   [i] mission started
  14:23:45  alpha   [i] reached WP-1
  14:24:02  charlie [!] battery 28%
  14:25:17  charlie [!!] CONNECTION LOST
  14:25:17  > CMD   rtl charlie
  ```
- **Interaction**: Tapping a drone ID in any feed entry selects that drone (same as tapping its fleet card -- map pans to it, fleet card highlights).
- **Collapse**: On desktop, the feed can be collapsed via a 48x48px chevron tab on its left edge (mirrors the fleet panel's collapse behavior). Keyboard shortcut: `]`.

### Notification Overlay (Map Streak Alerts)

Critical events appear as semi-transparent banners that slide across the top of the map area:

- **Trigger**: Drone lost, battery critical (<10%), geofence breach, crash/impact detected.
- **Position**: Anchored to the top of the map viewport, spanning the full width of the map (not the sidebars).
- **Appearance**: `--bg-secondary` at 92% opacity, 56px height, 4px left border in `--danger`. Icon + bold white text + drone role color dot.
- **Behavior**: Slides in from right (300ms), holds for 5 seconds, fades out (500ms). Tap to dismiss early. Stacks up to 3; oldest dismissed if a 4th arrives.
- **Relationship to feed**: The same event also appears as a `[!!]` entry in the Mission Feed. The overlay is a redundant visual interrupt for events that demand immediate attention even if the operator is not watching the feed.

### Top Bar

- **Left section**: Navigation tabs rendered as pill buttons: `Mission Control` (active), `Planner`, `Fleet`, `Pre-Flight`, `Telemetry`, `Replay`. Active tab uses `--bg-tertiary` with `--text-primary`. Inactive tabs use `--text-secondary`.
- **Center section**: Mission status cluster:
  - Status badge: pill-shaped, background color matches status. States: `IDLE` (gray), `ACTIVE` (green, pulsing dot), `PAUSED` (amber), `COMPLETE` (blue), `ABORTED` (red).
  - Elapsed time: `Geist Mono`, format `HH:MM:SS`, updates every second.
  - Active drone count: icon (drone silhouette) + `"3/5 active"` in `--text-primary`.
- **Right section**: Emergency Stop button (detailed below).

### Emergency Stop Button

Two distinct modes: **EMERGENCY LAND** (default, controlled descent) and **KILL MOTORS** (last resort).

- **Position**: Top-right corner, fixed. Always visible regardless of scroll or panel state.
- **Size**: 80x48px minimum (desktop), 96x56px (tablet).
- **Appearance**: Background `--danger-bg` (#450A0A) with a 2px solid `--danger` (#DC2626) border. Text: "E-LAND" in `Geist Sans 700`, 16px, color `#FFFFFF`. Icon: `OctagonX` from Lucide, 24px, to the left of text.
- **Hover/Press**: Background transitions to `#DC2626` (full red). Scale 1.02 on press.
- **Interaction (E-LAND)**: Single tap opens a confirmation dialog. The operator must explicitly tap "CONFIRM EMERGENCY LAND" (full-width red button) or tap "Cancel" to dismiss. There is no auto-cancel countdown -- the operator decides. On confirmation, executes `emergency_land()` which commands all drones to descend and land at their current position (controlled descent, motors active).
- **Interaction (KILL MOTORS)**: Inside the confirmation dialog, below the "CONFIRM EMERGENCY LAND" button, a smaller "KILL MOTORS" button is displayed in a darker, recessed style (`--bg-tertiary` background, `--danger` text, 12px font). This button requires a **3-second long-press** to activate (a progress ring fills around the button during the hold). Releasing early cancels. On activation, executes `emergency_stop()` which immediately kills all motors via force-disarm. A warning label is permanently visible next to the kill button: "Drones will fall from current altitude."
- **Audio**: Triggers a 500ms warning beep on first tap (dialog open), continuous alarm tone on either confirmation.

### Map Layer

- **Base map**: Mapbox GL JS with a dark satellite-hybrid style. Fallback: Leaflet with OpenStreetMap tiles + dark filter (`filter: brightness(0.6) contrast(1.2)`).
- **Render at**: z-index 0 (base layer).

#### Offline Map Support

Field operations often have limited or no internet connectivity. The map layer must work offline:

- **Pre-download tile caching**: Before going to the field, the operator downloads map tiles for the mission area at relevant zoom levels (typically z12-z18) using the mission planner interface. Tiles are stored in the browser's IndexedDB, typically 50-200MB for a mission area depending on zoom coverage.
- **Implementation**: Use Leaflet with the `leaflet-offline` plugin for tile caching and retrieval. Alternatively, use Mapbox's offline tile packs if using Mapbox GL JS. The tile cache is keyed by mission area bounding box.
- **Storage**: IndexedDB in the browser. A cache manager UI shows downloaded regions, storage used, and allows clearing old tiles.
- **Fallback**: When no cached tiles are available for the current viewport, render a blank canvas with a GPS coordinate grid overlay (graticule lines every 0.001 degrees, labeled) so operators still have spatial reference for drone positions.

#### Drone Position Markers -- Rich Drone Markers

Each marker visually encodes 4 dimensions at once -- operators can assess fleet status from the map alone without reading the feed.

1. **Core marker**: 40px circle, filled with drone role color (`--drone-recon`, `--drone-relay`, `--drone-strike`, `--drone-decoy`), white drone letter (A, B, C...) centered inside, 2px white border.
2. **Heading indicator**: Small directional triangle/arrow attached to the edge of the circle, pointing in the flight direction. Rotates with drone heading (0-359 degrees), updated every telemetry tick (100ms).
3. **Battery arc**: SVG ring around the marker (46px diameter, 3px stroke) showing battery level as a partial arc (clockwise from top). Colors: green (`--success`) > 50%, amber (`--warning`) 20-50%, red (`--danger`) < 20%. Below 10%: the red arc flashes (CSS animation, 0.5s on/off).
4. **Status halo**: Outer ring effect (54px diameter) that only appears during specific states:
   - Normal: no halo (default)
   - Executing waypoint: subtle white pulsing ring (opacity 0.3 to 0.6, 2s cycle)
   - Formation drift: amber pulsing ring (`--warning` at 40% opacity, 1.5s cycle)
   - Low battery (<20%): red pulsing ring (`--danger` at 50% opacity, 1s cycle)
   - Lost contact: marker desaturates to grey, "?" overlay replaces letter, dashed grey ring
   - RTL triggered: purple pulsing ring (`--status-rtl` at 40% opacity, 1.5s cycle)
   - Selected: solid white ring (2px, full opacity), marker scales to 48px
5. **Label pill**: Below the marker, drone ID in monospace (`JetBrains Mono 10px bold`), background `--bg-secondary` at 90% opacity, rounded 4px. Shows role as a tiny color dot to the left of the name.

##### Tap-to-Filter Interaction

When an operator taps a drone marker on the map:

1. The marker transitions to "selected" state (white ring, scale up).
2. All other markers dim to 50% opacity.
3. The Mission Feed panel auto-filters to only that drone's events.
4. A "Filtered: [DRONE_ID]" badge appears at top of feed with "x" to clear.
5. An expanded info card appears on the map anchored to the marker:
   - Background: `--bg-secondary`, border: `--border`, border-radius: 8px, shadow: `--shadow-popup`.
   - Content: coordinates, altitude, speed, heading, battery, waypoint progress.
   - Action buttons: Go To, RTL, Hold Position, Set Role (each 48px tall touch targets).
6. Tap anywhere else on the map to deselect -- feed returns to "All", info card closes.

##### Feed-Map Cross-Reference

When a new feed entry appears:

1. The corresponding drone's marker briefly glows (0.3s white flash at 60% opacity).
2. This creates a visual connection between the scrolling feed and the spatial map.
3. If the feed is filtered to one drone, only that drone's marker glows.

#### Role Execution Animations

Each drone's active role is visualized on the map with a role-specific animation layered on top of the drone marker. These animations communicate what the drone is doing at a glance.

- **Recon**: A radar cone rendered as a 60-degree arc emanating from the drone marker in the drone's heading direction. Filled with `--drone-recon` (blue) at pulsing opacity (0.15 to 0.35, 2s cycle). The cone extends 80px from the marker at default zoom and scales with the map.
- **Relay**: Dashed connection lines drawn from the relay drone to each drone it is bridging. Lines use `--drone-relay` color at 60% opacity, 2px dashed stroke. Animated "data dots" (4px circles, white) travel along the lines at a constant speed (one dot per second per link) to indicate active data flow.
- **Strike**: A dashed line from the drone to its assigned target, colored `--drone-strike` at 70% opacity. A distance readout (e.g., "342m") is displayed at the midpoint of the line in `Geist Mono 11px`. The target end of the line shows a pulsing crosshair animation (24px, 1.5s cycle, opacity 0.4 to 0.9).
- **Decoy**: A zigzag trail behind the drone (replacing the normal smooth breadcrumb trail) using `--drone-decoy` color. The drone marker itself has a flicker animation (opacity toggles between 0.5 and 1.0 at random intervals, 200-600ms) to visually suggest evasive, unpredictable movement.

#### Connection Type Indicators

Each drone marker displays a connection badge indicating its communication link type. The badge is positioned to the top-right of the core marker circle (offset +14px, -14px), sized 18x18px with `--bg-secondary` background and 1px `--border` border, rounded 4px.

- **Radio** (SiK): 📻 icon. Includes a 4-bar signal strength indicator (similar to cellular bars) rendered as four 2px-wide bars of increasing height. Bars fill from `--danger` (1 bar) through `--warning` (2-3 bars) to `--success` (4 bars) based on RSSI.
- **Fiber Optic**: 🔌 icon. Displays remaining spool length (e.g., "2.3/5km") in `Geist Mono 9px` below the badge. A tether line is drawn on the map from the drone to the spool anchor position using a solid 2px line in `--text-secondary` at 50% opacity. This tether line represents a physical constraint -- the mission planner must account for it when generating paths (no loops, max spool radius).
- **WiFi Mesh** (ESP32): 📶 icon. Signal strength shown as standard WiFi arcs (1-3 arcs filled).
- **LoRa**: 🏔 icon. No signal strength indicator (LoRa is either connected or not). A small "LR" label appears below the badge.

When a connection badge is tapped, a tooltip shows detailed connection diagnostics: link type, RSSI (dBm), packet loss %, latency (ms), and for fiber drones, the spool remaining and tether angle.

#### Drone Trails (Breadcrumbs)

- **Rendering**: Polyline of the last 60 seconds of GPS positions (roughly 600 points at 10Hz telemetry).
- **Style**: 3px line, color matches drone role color at 60% opacity. Applies a gradient from full opacity (current position) to 0% opacity (60 seconds ago).
- **Performance**: Use Mapbox GL `line-gradient` paint property. For Leaflet, use a Canvas renderer with custom gradient.
- **Toggle**: Trails can be toggled on/off via a map control button (top-left map corner, below zoom controls).

#### Waypoints and Mission Paths

- **Waypoint markers**: Numbered circles, 28px diameter, white border, filled with `--bg-tertiary`. The number inside uses `Geist Mono 14px bold`. A connecting dashed line (2px, white at 40% opacity) links sequential waypoints.
- **Active waypoint**: Solid white fill, slightly larger (32px), with a progress ring around it indicating ETA.
- **Completed waypoints**: Checkmark icon replaces the number. Fill becomes `--success` at 30% opacity.

#### Geofence Boundary

- **Rendering**: Polygon overlay.
- **Fill**: `--danger` at 5% opacity.
- **Border**: 3px dashed line, `--danger` at 80% opacity.
- **Edit mode**: Vertices become draggable circles (24px diameter, white fill). Midpoints of each edge show translucent add-vertex handles. Edit mode is activated from the Mission Planner, not from Mission Control.

#### Home/Launch Point Marker

- **Shape**: "H" inside a circle, 36px diameter.
- **Style**: White border, fill `--bg-secondary`, icon `--text-primary`.
- **Always visible**: Does not cluster or hide at any zoom level.

#### Map Controls (top-left cluster, below Mapbox defaults)

Rendered as a vertical stack of 48x48px square buttons with `--bg-secondary` background and `--border` border:

1. **Zoom In** (+)
2. **Zoom Out** (-)
3. **Fit All Drones** (expand arrows icon) -- adjusts map bounds to show all active drones with 10% padding.
4. **Toggle Trails** (route icon) -- on/off.
5. **Toggle Waypoints** (map pin icon) -- on/off.
6. **Toggle Geofence** (shield icon) -- on/off.
7. **Center on Selected** (crosshair icon) -- disabled when no drone is selected.

### Fleet Panel (Left Sidebar)

- **Width**: 300px expanded, 0px collapsed. Collapse toggle: 48x48px tab on the right edge of the panel (chevron icon).
- **Background**: `--bg-secondary`.
- **Header**: "Fleet" label + active count badge (`3/5`) + collapse chevron.
- **Transition**: Slides in/out, 300ms ease.

#### Drone Card (repeated per drone)

```
+------------------------------------------------------+
| [Role Color Bar 4px]                                  |
| ALPHA                           [Battery] 87%  [|||| ]|
| Role: Recon          GPS: 12 sats    RSSI: -42dBm    |
| Status: [AIRBORNE badge]        Alt: 45m              |
+------------------------------------------------------+
```

- **Dimensions**: Full width of panel (300px - 16px padding each side = 268px content), height approximately 88px.
- **Left edge**: 4px vertical color bar matching drone role color.
- **Row 1**: Drone ID (`Geist Mono 16px bold`, `--text-primary`), battery icon + percentage (color: green > 50%, amber 20-50%, red < 20%, flashing red < 10%).
- **Row 2**: Role label (`Geist Sans 13px`, `--text-secondary`), GPS satellite count with icon, RSSI signal strength with icon (4-bar indicator).
- **Row 3**: Status badge (pill, background matches `--status-*` colors, text white, `Geist Sans 12px bold`), altitude in meters.
- **Interaction**:
  - **Tap**: Selects the drone. Map smoothly pans and zooms to center on it. The card gains a 2px left border highlight in the role color, and the card background changes to `--bg-tertiary`. A detail telemetry expansion appears below the card (see below).
  - **Long press / drag handle**: Reorder cards in the list to set operator priority (purely cosmetic/organizational, does not affect orchestration).
- **States**:
  - Default: as described.
  - Selected: highlighted background, expanded telemetry.
  - Disconnected: card becomes 50% opacity, status badge shows "LOST" in `--status-lost`, GPS/RSSI show "--".
  - Not armed: status badge shows "IDLE" in gray.

#### Expanded Telemetry (shown below selected drone card)

When a drone card is tapped, a 200px tall expansion slides open below it:

```
+------------------------------------------------------+
|  Lat:  34.0522°N     Lon: -118.2437°W               |
|  Alt:  45.2m AGL     Speed: 8.3 m/s                 |
|  Hdg:  127°          Climb: 0.2 m/s                 |
|  Mode: AUTO          WP: 3/7                         |
|  Batt: 12.4V / 87%  Time remaining: ~12min          |
|  [Go To] [RTL] [Hold Position] [Set Role v]          |
+------------------------------------------------------+
```

- All values in `Geist Mono 14px`.
- Labels in `--text-secondary`, values in `--text-primary`.
- Bottom row: action buttons, each 48px tall, `--bg-tertiary` background, `--border` border. `[Go To]` opens a tap-on-map target mode. `[RTL]` sends return-to-launch for this single drone. `[Hold Position]` sends loiter-at-current-position. `[Set Role]` opens a dropdown to reassign role.

### Bottom Action Bar

- **Height**: 64px, sticky to bottom.
- **Background**: `--bg-secondary` with a top border of 1px `--border`.
- **Layout**: Centered row of action buttons with 12px gaps.

#### Action Buttons

Each button: height 48px, min-width 140px, border-radius 6px, `Geist Sans 14px 600`.

| Button          | Background       | Text Color | Icon (left) | Confirmation Required |
| --------------- | ---------------- | ---------- | ----------- | --------------------- |
| Takeoff All     | `--success`      | `#FFFFFF`  | `ArrowUp`   | Yes (modal)           |
| RTL All         | `--status-rtl`   | `#FFFFFF`  | `Home`      | Yes (modal)           |
| Land All        | `--status-armed` | `#000000`  | `ArrowDown` | Yes (modal)           |
| Pause Mission   | `--bg-tertiary`  | `--text-primary` | `Pause` | No (instant toggle)  |
| Resume Mission  | `--success`      | `#FFFFFF`  | `Play`      | No (instant toggle)   |

- `Pause Mission` and `Resume Mission` occupy the same slot and toggle based on mission state.
- Disabled state: 40% opacity, cursor not-allowed, tap does nothing.
- Buttons are disabled when contextually inappropriate (e.g., "Takeoff All" disabled when drones are already airborne).

### Live Camera Feed Views

#### Tap-to-View

Tapping a camera-equipped drone (Class B or higher) opens a video panel anchored to the marker showing a live FPV feed with HUD overlay (altitude, speed, heading). The panel appears below the expanded info card (or replaces it if already open). Class A drones (no camera) show a "No camera" telemetry-only card with the same layout but a static icon instead of video.

- **Panel size**: 320x180px (16:9), rounded 8px corners, `--bg-secondary` background, `--border` border.
- **HUD overlay**: Semi-transparent bar at the bottom of the video frame showing altitude (m), speed (m/s), and heading (degrees) in `Geist Mono 12px`.
- **Latency indicator**: Small colored dot in the top-right of the video frame -- green (<150ms), amber (150-500ms), red (>500ms).
- **Close**: "X" button top-right. Tapping another drone closes the current feed and opens the new one.

#### Picture-in-Picture (PiP)

The operator can pin camera feeds to corners of the map by tapping a "Pin" icon on any open video panel. Pinned feeds remain visible while navigating the map.

- **Max PiPs**: 4 simultaneous.
- **PiP size**: 200x112px (16:9).
- **Border**: 2px solid, colored with the drone's role color.
- **Label**: Drone ID in `Geist Mono 10px bold` at the bottom-left of each PiP.
- **Placement**: Auto-arranged in corners (top-left, top-right, bottom-left, bottom-right). Operator can drag to reorder.
- **Interaction**: Tap a PiP to expand it to full Tap-to-View panel. Long-press to unpin.

#### Multi-Feed Grid

A dedicated "Feeds" tab in the top navigation bar shows all active camera feeds in a grid layout.

- **Grid sizes**: 2x2 (up to 4 feeds) or 3x2 (5-6 feeds). Auto-selects based on active camera count.
- **Active feed**: Highlighted with a bright white 2px border. Tap to select (routes audio if applicable).
- **Inactive feeds**: `--border` border at 60% opacity.
- **No-camera drones**: Not shown in the grid (camera-equipped only).
- **Full-screen**: Double-tap any feed tile to expand to full-screen. Tap again or press `Esc` to return to grid.

### State Transitions (Mission Control)

```
IDLE ──[Start Mission]──> ACTIVE
ACTIVE ──[Pause]──> PAUSED
PAUSED ──[Resume]──> ACTIVE
ACTIVE ──[All WPs Complete]──> COMPLETE
ACTIVE ──[E-STOP]──> ABORTED
PAUSED ──[E-STOP]──> ABORTED
ACTIVE ──[RTL All]──> RTL_IN_PROGRESS ──[All Landed]──> COMPLETE
```

State is displayed in the top bar status badge. Each transition triggers a toast notification.

---

## Screen 2: Mission Planner (Pre-Flight)

Accessed via the `Planner` tab. This screen is used before a mission begins.

### Layout

```
+--------------------------------------------------------------+
| TOP BAR (same as Mission Control, "Planner" tab active)      |
+----------+---------------------------------------------------+
|          |                                                    |
| MISSION  |              MAP (interactive editing)             |
| CONFIG   |                                                    |
| PANEL    |   [Formation preview overlay]                      |
| (w:380px)|                                                    |
|          |                                                    |
|          |                                                    |
+----------+---------------------------------------------------+
| BOTTOM BAR: [Validate] [Save Profile] [Load Profile] [Clear] |
+--------------------------------------------------------------+
```

### Map (Editing Mode)

- Same base map as Mission Control.
- **Tap on map**: Places a waypoint at that location. Waypoints are numbered sequentially.
- **Drag waypoint**: Repositions it. Snaps to 1m grid when zoom > 18.
- **Tap existing waypoint**: Opens an inline editor popover (see below).
- **Right-click / long-press waypoint**: Context menu: `Delete`, `Insert Before`, `Insert After`.
- **Geofence editing**: Button in map controls activates polygon edit mode. Tap to add vertices, drag to move, tap vertex and press delete to remove.

#### Waypoint Popover (appears above the tapped waypoint)

```
+-----------------------------------+
| Waypoint 3                    [X] |
| Lat: 34.0522  Lon: -118.2437     |
| Altitude: [  45  ] m             |
| Speed:    [  8.0 ] m/s           |
| Loiter:   [  10  ] sec           |
| Action:   [None         v]       |
|           [Apply]                 |
+-----------------------------------+
```

- Input fields: 48px tall, `Geist Mono`, numeric-only with stepper arrows (increment: altitude 1m, speed 0.5m/s, loiter 5sec).
- Action dropdown: `None`, `Take Photo`, `Start Recording`, `Stop Recording`, `Drop Payload`.
- `[Apply]` saves and closes the popover.

#### Formation Preview Overlay

When a formation is selected (see config panel), translucent drone silhouettes appear on the map showing where each drone would be positioned relative to the first waypoint:

- Silhouettes use the drone role colors at 40% opacity.
- Lines connect each silhouette to its assigned drone label.
- The preview updates in real-time as the operator adjusts formation parameters.

### Mission Config Panel (Left, 380px)

Scrollable panel with the following sections, each in a collapsible accordion:

#### Section: Formation

- **Selector**: Row of 48x48px icon buttons, one per formation type:
  - `V Formation` (chevron icon)
  - `Line` (horizontal line icon)
  - `Orbit` (circle icon)
  - `Sweep` (zigzag icon)
  - `Custom` (pencil icon)
- Selected formation has `--drone-recon` border and background tint.
- Below the selector, formation-specific parameters:
  - **V Formation**: Angle (30-90 degrees, slider), Spacing (5-50m, slider).
  - **Line**: Spacing (5-50m), Orientation (0-359 degrees, rotary input or numeric).
  - **Orbit**: Radius (10-200m), Direction (CW/CCW toggle), Altitude offset between drones (0-20m).
  - **Sweep**: Lane width (10-100m), Overlap percentage (0-50%).
  - **Custom**: No parameters; operator manually assigns each drone's path.

#### Section: Drone Assignment

- Table of drones:

  | Drone  | Role   | Assigned Waypoints | Status    |
  | ------ | ------ | ------------------ | --------- |
  | alpha  | Recon  | 1, 2, 3, 4         | Ready     |
  | bravo  | Relay  | (relay position)    | Ready     |
  | charlie| Strike | 1, 3, 5            | Ready     |

- Each row has a clickable "Waypoints" cell that opens a multi-select dropdown of waypoint numbers.
- **Auto-Assign button**: Full-width, `--bg-tertiary`, text "Auto-Assign Based on Capabilities". On press, the orchestrator backend calculates optimal assignment considering each drone's hardware class, role, battery level, and current position. Results populate the table. A diff-highlight (green background flash) shows changes.

#### Section: Mission Parameters (Global Defaults)

- **Default Altitude**: Numeric input, 10-400m, step 5m. Default: 50m.
- **Default Speed**: Numeric input, 1-20 m/s, step 0.5. Default: 8 m/s.
- **Default Loiter Time**: Numeric input, 0-300 sec, step 5. Default: 0 sec.
- **RTL Altitude**: Numeric input, 20-500m, step 5m. Default: 60m.
- These are overridden by per-waypoint values when set.

#### Section: Geofence

- **Status indicator**: "Geofence SET" (green) or "No geofence defined" (amber warning).
- **Edit Geofence button**: Activates polygon editing mode on the map.
- **Max Altitude**: Numeric input, serves as a ceiling geofence.
- **Breach Action**: Dropdown: `RTL`, `Land`, `Hold Position`.

### Bottom Bar

| Button         | Style                  | Behavior                                                                                         |
| -------------- | ---------------------- | ------------------------------------------------------------------------------------------------ |
| Validate       | `--success` background | Runs validation checks (all waypoints within geofence, all drones have assignments, all drones capable of their assigned actions). Shows results in a modal (see below). |
| Save Profile   | `--bg-tertiary`        | Opens a save dialog: name input + optional description. Saves to local storage and optionally to the backend. |
| Load Profile   | `--bg-tertiary`        | Opens a modal listing saved profiles with name, date, drone count, waypoint count. Tap to load.  |
| Clear          | `--bg-tertiary`, red text | Confirmation dialog, then clears all waypoints, assignments, and formation selection.          |

### Validation Results Modal

```
+----------------------------------------------------+
|  MISSION VALIDATION                            [X]  |
|----------------------------------------------------|
|  [CHECK] All waypoints within geofence         OK   |
|  [CHECK] All drones assigned                   OK   |
|  [WARN]  bravo battery at 23% -- may not       !    |
|          complete mission                            |
|  [CHECK] No waypoint altitude exceeds ceiling  OK   |
|  [CHECK] All drones support assigned actions   OK   |
|----------------------------------------------------|
|  Result: PASS WITH WARNINGS                         |
|  [Proceed to Pre-Flight Check]  [Back to Edit]      |
+----------------------------------------------------+
```

- Each line: icon (green check, amber warning, red X), description, status.
- If any line is a red X (fail), the "Proceed" button is disabled.
- Warnings allow proceeding but are flagged.

---

## Screen 3: Fleet Manager

Accessed via the `Fleet` tab. Used for drone registration, configuration, and maintenance.

### Layout

```
+--------------------------------------------------------------+
| TOP BAR ("Fleet" tab active)                                  |
+--------------------------------------------------------------+
| [+ Add Drone]    [Search: ________]    [Filter: All Roles v] |
+--------------------------------------------------------------+
| TABLE                                                         |
| ID | HW Class | Role | Connection | Battery | GPS | Compass  |
|    |          |      |            |         |     | | Status  |
|....|..........|......|............|.........|.....|.|.........|
|    |          |      |            |         |     | |         |
+--------------------------------------------------------------+
```

### Table

- **Full-width**, horizontally scrollable on smaller screens.
- **Row height**: 56px for comfortable tap targets.
- **Columns**:

| Column       | Width   | Content                                                         |
| ------------ | ------- | --------------------------------------------------------------- |
| ID           | 100px   | Drone callsign in `Geist Mono 14px bold`. Tappable to open drone detail. |
| HW Class     | 80px    | Badge: `A` / `B` / `C` / `D`. Color-coded (A=gold, B=silver, C=bronze, D=gray). Tooltip on hover/long-press shows class capabilities. |
| Role         | 100px   | Pill badge, colored by role. Tappable to change role (inline dropdown). |
| Connection   | 100px   | Signal bars icon (0-4 bars) + label: `Strong` / `Weak` / `Lost`. Color: green/amber/red. |
| Battery      | 80px    | Percentage + mini bar graph. Color: green > 50%, amber 20-50%, red < 20%. |
| GPS          | 80px    | Satellite count + quality indicator (`3D Fix` green, `2D Fix` amber, `No Fix` red). |
| Compass      | 80px    | `Cal OK` (green) or `Needs Cal` (amber/red badge).              |
| Status       | 100px   | Status badge (same style as Mission Control).                    |
| Actions      | 160px   | Icon buttons: `Edit` (pencil), `Remove` (trash, red), `Firmware` (download), `Preflight` (clipboard check). Each icon is 24px inside a 40x40px tap target. |

- **Sorting**: Tap column header to sort. Arrow indicator shows sort direction.
- **Selection**: Checkbox column on the far left for bulk actions (bulk role change, bulk remove).
- **Empty state**: Centered illustration + "No drones registered. Tap + Add Drone to get started."

### Capability Badges

Displayed as a row of small icons below the HW Class badge in each row (or in the drone detail view):

| Icon             | Meaning          | Size  |
| ---------------- | ---------------- | ----- |
| `Camera`         | Has camera       | 16px  |
| `Cpu`            | Has onboard compute | 16px |
| `Package`        | Has payload bay  | 16px  |
| `Radio`          | Has mesh relay   | 16px  |
| `Thermometer`    | Has thermal sensor | 16px |

Icons are `--text-secondary` when absent (grayed), `--text-primary` when present.

### Add Drone Flow

Triggered by the `[+ Add Drone]` button (top-left, `--success` background, 48px tall).

#### Step 1: Scan QR

```
+----------------------------------------------------+
|  ADD DRONE                                     [X]  |
|----------------------------------------------------|
|                                                      |
|    [QR Scanner Viewport]                             |
|    (Uses device camera or USB webcam)                |
|                                                      |
|    -- or --                                          |
|                                                      |
|    Manual Entry:                                     |
|    Serial: [________________]                        |
|    [Next]                                            |
+----------------------------------------------------+
```

- QR code encodes a JSON payload: `{ "serial": "...", "hw_class": "B", "capabilities": [...] }`.
- On scan, auto-populates the confirmation form.

#### Step 2: Confirm and Configure

```
+----------------------------------------------------+
|  ADD DRONE                                     [X]  |
|----------------------------------------------------|
|  Serial:    DRN-2024-00847                          |
|  HW Class:  B (Auto-detected)                       |
|  Capabilities: Camera, Compute, Relay               |
|                                                      |
|  Callsign:  [ delta    ]  (editable)                |
|  Role:      [ Recon    v]  (dropdown)               |
|                                                      |
|  Connection: Scanning...  [Retry]                    |
|              FOUND on 915MHz -- RSSI: -38dBm         |
|                                                      |
|  [Cancel]                    [Add to Fleet]          |
+----------------------------------------------------+
```

- Callsign defaults to the next unused NATO phonetic alphabet name.
- Connection is attempted automatically. If found, shows signal info. If not found within 10 seconds, shows "Not Found" with a `[Retry]` button.
- `[Add to Fleet]` is disabled until connection is confirmed.

### Edit Drone (Inline or Modal)

Tapping the `Edit` icon on a row opens an inline edit panel below the row (pushes rows down):

- Editable fields: Callsign, Role.
- Read-only fields: Serial, HW Class, Capabilities.
- `[Save]` and `[Cancel]` buttons.

### Remove Drone

- Confirmation dialog: "Remove **delta** from fleet? This will not affect the physical drone."
- `[Cancel]` `[Remove]` (red button).

### Flash Firmware

- Opens a modal showing current firmware version and latest available version.
- `[Flash]` button starts the process. Progress bar shown. Drone must be on the ground and connected.
- On completion: "Firmware updated. Drone will reboot."

### Run Individual Preflight

- Runs the same checks as the Pre-Flight Check Screen (Screen 4) but only for the selected drone.
- Results shown inline below the drone row.

---

## Screen 4: Pre-Flight Check Screen

Accessed via the `Pre-Flight` tab, or by tapping "Proceed to Pre-Flight Check" from the Mission Planner validation modal.

### Layout

```
+--------------------------------------------------------------+
| TOP BAR ("Pre-Flight" tab active)                             |
+--------------------------------------------------------------+
|                                                                |
|  OVERALL STATUS BAR                                           |
|  [  3/3 DRONES READY  ]  or  [  BLOCKED: bravo GPS  ]        |
|                                                                |
+--------------------------------------------------------------+
|                                                                |
|  DRONE CHECK CARDS (vertical list, one per drone)             |
|                                                                |
|  +----------------------------------------------------------+ |
|  | ALPHA (Recon)                              [PASSED]       | |
|  | COMMS [====] GPS [====] BATTERY [====] COMPASS [====]     | |
|  | FAILSAFE [====] ARMING [====]                             | |
|  +----------------------------------------------------------+ |
|                                                                |
|  +----------------------------------------------------------+ |
|  | BRAVO (Relay)                              [CHECKING...]  | |
|  | COMMS [====] GPS [==  ] BATTERY [    ] COMPASS [    ]     | |
|  | FAILSAFE [    ] ARMING [    ]                             | |
|  +----------------------------------------------------------+ |
|                                                                |
+--------------------------------------------------------------+
| [Run All Checks]               [Proceed to Mission Control]  |
+--------------------------------------------------------------+
```

### Overall Status Bar

- **Height**: 64px, full-width.
- **States**:
  - All passed: `--success` background, white text: "3/3 DRONES READY".
  - In progress: `--status-armed` background, black text: "Checking... 1/3 complete".
  - Blocked: `--danger` background, white text: "BLOCKED: bravo GPS needs calibration". Includes a brief reason.

### Drone Check Card

One card per drone, stacked vertically with 12px gap.

- **Header row**: Drone ID + role badge (left), overall card status badge (right).
- **Check items row**: Horizontal sequence of check indicators.

#### Check Item Indicator

Each check is rendered as a labeled progress block:

```
COMMS
[========]  <- filled bar, 64px wide, 8px tall
     OK
```

- **States**:
  - Pending: Gray bar, no label below. Shown before the check runs.
  - Running: Animated indeterminate progress bar (stripe animation), label "...".
  - Passed: Green (`--success`) filled bar, checkmark icon, label "OK" in green.
  - Failed: Red (`--danger`) filled bar, X icon, label describing failure (e.g., "3 sats" for GPS).
  - Warning: Amber (`--warning`) filled bar, warning icon, label (e.g., "23%").

#### Check Sequence Per Drone

Checks run sequentially (each depends on prior):

1. **COMMS**: Ping the drone, confirm bidirectional communication. Timeout: 5 seconds.
2. **GPS**: Request GPS status. Pass: 3D fix with >= 6 satellites. Warn: 3D fix with 4-5 sats. Fail: 2D fix or no fix.
3. **BATTERY**: Request battery telemetry. Pass: >= 30%. Warn: 20-29%. Fail: < 20%.
4. **COMPASS**: Request compass calibration status. Pass: calibrated, heading deviation < 5 degrees. Fail: not calibrated or deviation >= 5 degrees.
5. **FAILSAFE**: Verify failsafe parameters are set (RTL altitude, battery failsafe threshold, geofence breach action). Pass: all set. Fail: any unset.
6. **ARMING**: Attempt a dry-arm (arm check without actually arming). Pass: arming checks pass. Fail: any arming check fails (report which one).

#### Animation

- Checks animate in left-to-right, 500ms per check for the animation transition.
- On pass, a brief green flash highlight on the bar.
- On fail, a brief red flash + shake animation (100ms, 3px horizontal oscillation).

#### Recheck Button

- Appears next to any failed check item: small `[Recheck]` pill button, `--bg-tertiary`, 36px tall.
- Reruns only that specific check for that specific drone.
- Also: a `[Recheck All]` button at the card level reruns all checks for that drone.

### Bottom Bar

| Button                       | Style                  | State                                               |
| ---------------------------- | ---------------------- | --------------------------------------------------- |
| Run All Checks               | `--bg-tertiary`        | Always enabled. Reruns all checks for all drones.   |
| Proceed to Mission Control   | `--success` background | Enabled only when all drones pass all checks.       |

When "Proceed to Mission Control" is tapped, the app switches to the Mission Control tab with the mission loaded and ready to arm.

---

## Screen 5: Telemetry Dashboard

Accessed via the `Telemetry` tab. Provides detailed real-time data visualization.

### Layout

```
+--------------------------------------------------------------+
| TOP BAR ("Telemetry" tab active)                              |
+--------------------------------------------------------------+
| CHART GRID (2x2)                              | MISSION FEED |
|                                                | (w: 320px)  |
| +-------------------------+------------------+ |              |
| | Battery Chart           | Altitude Chart   | | [scrolling  |
| | (line, per drone)       | (line, per drone)| |  real-time  |
| +-------------------------+------------------+ |  event log] |
| | Signal Strength Chart   | GPS Sats Chart   | |              |
| | (bar, per drone)        | (bar, per drone) | |              |
| +-------------------------+------------------+ |              |
|                                                |              |
+--------------------------------------------------------------+
| ALERT BAR (conditional, slides up when alert active)          |
+--------------------------------------------------------------+
```

### Chart Grid

Four charts in a 2x2 responsive grid. Each chart is a card with `--bg-secondary` background, 8px border-radius, 16px padding.

#### Battery Chart (Top Left)

- **Type**: Multi-line chart (one line per drone).
- **X axis**: Time (last 5 minutes by default, adjustable: 1min / 5min / 15min / 30min / All via toggle pills above chart).
- **Y axis**: Battery percentage (0-100%) on the left axis; voltage (V) on the right axis.
- **Line colors**: Match drone role colors.
- **Line style**: 2px solid, with a subtle glow effect matching the line color at 20% opacity.
- **Legend**: Below chart, showing drone ID + current value. Tapping a legend entry toggles that line's visibility.
- **Critical threshold**: Horizontal dashed red line at 20% with label "CRITICAL".
- **Warning threshold**: Horizontal dashed amber line at 30%.
- **Update rate**: Every 1 second (battery doesn't change fast enough to warrant 100ms).
- **Library**: Recharts (renders as SVG, supports responsive resizing).

#### Altitude Chart (Top Right)

- **Type**: Multi-line chart.
- **X axis**: Time (same range as battery chart, synced).
- **Y axis**: Altitude in meters AGL.
- **Line colors**: Match drone role colors.
- **Target altitude**: Thin dashed white line showing the commanded altitude.
- **Ceiling geofence**: Horizontal dashed red line at the max altitude from geofence settings.
- **Update rate**: Every 100ms.

#### Signal Strength Chart (Bottom Left)

- **Type**: Grouped bar chart (one bar per drone, grouped by current snapshot).
- **X axis**: Drone IDs.
- **Y axis**: RSSI in dBm (typical range: -30 to -90 dBm). Inverted so stronger signal appears taller.
- **Bar colors**: Match drone role colors.
- **Thresholds**: Green zone > -50 dBm, amber zone -50 to -70 dBm, red zone < -70 dBm. Background bands on chart.
- **Update rate**: Every 500ms.

#### GPS Satellite Count Chart (Bottom Right)

- **Type**: Grouped bar chart.
- **X axis**: Drone IDs.
- **Y axis**: Number of satellites (0-20).
- **Bar colors**: Match drone role colors.
- **Thresholds**: Green >= 8, amber 6-7, red < 6. Background bands on chart.
- **Update rate**: Every 1 second.

### Event Log (Right Panel) -- Now Powered by Mission Feed

- **Width**: 320px, full height of the chart area.
- **Background**: `--bg-secondary`.
- This panel renders the same Mission Feed component used on the Mission Control screen (see [Design Concept: Mission Feed](#design-concept-mission-feed)), filtered to the Telemetry tab context. On the Telemetry screen, the feed defaults to showing telemetry alerts and warnings rather than all events; the operator can widen the filter to see everything.
- **Header**: "Mission Feed" + count badge + filter dropdown (All / Critical / Warnings / Telemetry / Commands).
- **Entry format**: Same monospace, color-coded format as the Mission Feed (see above).
- **Scroll behavior**: Auto-scrolls to newest; scroll up pauses auto-scroll with a "Jump to latest" pill at the bottom.
- **Max entries**: 2000 displayed; older entries virtualized via `react-window`.

### Alert Bar

- **Position**: Fixed to the bottom of the screen, above the bottom action bar if present.
- **Height**: 56px.
- **Behavior**: Slides up from below when a critical alert triggers. Remains visible until dismissed or acknowledged.
- **Appearance**: `--danger` background, white text. Content: icon + message + `[Acknowledge]` button + `[Details]` button.
- **Audio**: On appearance, plays a 2-second alarm tone. Repeats every 10 seconds until acknowledged.
- **Types of critical alerts**:
  - **Drone lost**: "CONNECTION LOST: bravo -- last known position marked on map"
  - **Low battery emergency**: "CRITICAL BATTERY: charlie at 8% -- auto-RTL initiated"
  - **Fence breach**: "GEOFENCE BREACH: alpha has left the operational area"
  - **Crash detected**: "IMPACT DETECTED: delta -- rapid altitude loss"

Multiple simultaneous alerts stack vertically (max 3 visible, older ones queued).

---

## Screen 6: Mission Replay

Accessed via the `Replay` tab. Used for post-mission review and debriefing.

### Layout

```
+--------------------------------------------------------------+
| TOP BAR ("Replay" tab active)                                 |
+--------------------------------------------------------------+
| MAP REPLAY (left, 60% width)  | TELEMETRY CHARTS (right, 40%)|
|                                |                               |
| [Historical drone positions]   | Battery chart (synced)        |
| [Trail history]                | Altitude chart (synced)       |
| [Event markers on map]         | Signal chart (synced)         |
|                                |                               |
+--------------------------------------------------------------+
| TIMELINE SCRUBBER                                             |
| |--[T]---[W1]------[W2]--[R]------[W3]----[RTL]--[L]--|     |
| 00:00                                              12:34      |
| [|<] [<] [>||] [>] [>|]    Speed: [1x] [2x] [4x] [8x]      |
+--------------------------------------------------------------+
```

### Mission Selector

Before the replay view loads, a modal presents a list of recorded missions:

```
+----------------------------------------------------+
|  SELECT MISSION                                [X]  |
|----------------------------------------------------|
|  Mission "Alpha Sweep"                              |
|  2026-03-25 14:20 -- Duration: 12:34 -- 3 drones   |
|----------------------------------------------------|
|  Mission "Perimeter Check"                          |
|  2026-03-24 09:15 -- Duration: 08:22 -- 5 drones   |
|----------------------------------------------------|
|  Mission "Test Flight"                              |
|  2026-03-23 16:45 -- Duration: 03:11 -- 1 drone    |
+----------------------------------------------------+
```

Tap a mission to load it.

### Map Replay (Left, 60%)

- Same map renderer as Mission Control.
- Drone markers move along their recorded paths as the timeline plays.
- Trails show the full path up to the current playback time.
- Event markers appear on the map at the location where they occurred (e.g., a waypoint-reached icon at the waypoint location, a warning icon where a battery alert was triggered).
- The geofence boundary from the original mission is shown.
- Map can be panned and zoomed independently of playback.

### Telemetry Charts (Right, 40%)

- Smaller versions of the Battery, Altitude, and Signal Strength charts from the Telemetry Dashboard.
- A vertical cursor line on each chart tracks the current playback time.
- Charts show the full mission duration on the X axis.
- Tapping a point on any chart jumps the playback to that time.

### Timeline Scrubber

- **Position**: Bottom of the screen, 96px tall.
- **Background**: `--bg-secondary`.

#### Scrubber Bar

- Full-width horizontal bar, 8px tall, `--bg-tertiary` background.
- Played portion: `--drone-recon` fill.
- **Playhead**: 24px diameter circle, white, draggable.
- **Event markers**: Small icons positioned on the bar at the timestamp of each event:
  - `T` (green triangle): Takeoff
  - `Wn` (blue circle): Waypoint n reached
  - `R` (amber diamond): Replan event
  - `RTL` (purple square): Return to launch
  - `L` (green square): Landing
  - `!` (red triangle): Alert event
- Hovering/tapping an event marker shows a tooltip with the event detail and timestamp.

#### Transport Controls

Centered below the scrubber bar:

| Button   | Icon             | Size   | Action                     |
| -------- | ---------------- | ------ | -------------------------- |
| `|<`     | `SkipBack`       | 40x40  | Jump to start              |
| `<`      | `Rewind`         | 40x40  | Step back 10 seconds       |
| `>||`    | `Play` / `Pause` | 48x48  | Toggle play/pause          |
| `>`      | `FastForward`    | 40x40  | Step forward 10 seconds    |
| `>|`     | `SkipForward`    | 40x40  | Jump to end                |

#### Speed Selector

Row of pill buttons to the right of transport controls:

- `1x` (default), `2x`, `4x`, `8x`.
- Active speed pill: `--drone-recon` background, white text. Others: `--bg-tertiary`, `--text-secondary`.

### Data Export

- `[Export]` button in the top-right of the replay view.
- Options: Export as JSON (full telemetry log), Export as KML (flight paths for Google Earth), Export as CSV (tabular telemetry data).

---

## Screen 7: Tablet and Mobile Mode

Tablet Mode is activated automatically when the viewport width is <= 1200px or the User-Agent indicates a tablet/mobile device. It can also be toggled manually from a settings menu. Phone Mode activates below 600px.

### Key Differences from Desktop

| Aspect               | Desktop (>1200px)                | Tablet (600-1200px)                  | Phone (<600px)                       |
| -------------------- | -------------------------------- | ------------------------------------ | ------------------------------------ |
| Fleet panel           | Persistent left sidebar          | Swipe-in from left edge              | Accessible from hamburger menu       |
| Mission Feed          | Persistent right panel           | Swipe-in from right edge             | **Primary view** (full screen)       |
| Map                   | Center, ~60% width              | Full screen with overlays            | Collapsible thumbnail header         |
| Minimum touch target  | 40px                             | 48px                                 | 48px                                 |
| Font sizes            | As specified                     | +2px across the board                | +2px across the board                |
| Bottom action bar     | Buttons with text labels         | Buttons with icons + abbreviated text | Floating action button cluster       |
| Map controls          | Vertical stack                   | 2x grid for easier reach             | Minimal (zoom only)                  |
| Hover states          | Present (with mouse)             | Absent entirely                      | Absent entirely                      |
| Top bar               | Full navigation tabs             | Hamburger menu + current tab name    | Hamburger menu + status badge only   |

### Gesture Navigation

- **Swipe left from right edge**: Opens Mission Feed panel (overlays the map, 320px wide, semi-transparent `--bg-secondary` at 95% opacity).
- **Swipe right from left edge**: Opens fleet panel (same overlay style).
- **Tap outside panel**: Closes the panel.
- **Pinch**: Map zoom (native map gesture passthrough).
- **Two-finger drag**: Map pan (distinguishes from single-finger swipe gestures by requiring the touch to start in the map area, not from screen edges).

### Tablet Landscape (768-1200px)

```
+--------------------------------------------------------------+
| TOP BAR                                           [E-STOP]   |
+--------------------------------------------------------------+
|                                                                |
|                    MAP (full screen)                           |
|                                                                |
|   [<- swipe left edge: Fleet]   [swipe right edge: Feed ->]  |
|                                                                |
+--------------------------------------------------------------+
| BOTTOM BAR (quick actions, wider layout)                      |
+--------------------------------------------------------------+
```

Map is full screen. Swipe from left edge for Fleet panel, swipe from right edge for Mission Feed panel. Both overlay the map at 95% opacity. Notification overlays (streak alerts) still float over the map top.

### Tablet Portrait (600-768px)

```
+-------------------------------+
| TOP BAR (hamburger + status)  |
+-------------------------------+
|                               |
|         MAP (full width)      |
|         (~60% viewport height)|
|                               |
+-------------------------------+
| MISSION FEED (bottom drawer)  |
| (swipe up to expand,          |
|  40% viewport height default) |
+-------------------------------+
| BOTTOM BAR (quick actions)    |
| [E-STOP] always visible       |
+-------------------------------+
```

The Mission Feed appears as a bottom drawer that can be swiped up to expand (40% viewport height) or swiped down to collapse to a single-line summary showing the most recent event. Fleet panel is accessible via swipe from the left edge.

### Phone (<600px) -- Feed-First Layout

```
+-------------------------------+
| TOP BAR (hamburger + [E-STOP])|
+-------------------------------+
| MAP THUMBNAIL (collapsible)   |
| [tap to expand full screen]   |
| (120px height, shows drone    |
|  positions at a glance)       |
+-------------------------------+
|                               |
|     MISSION FEED              |
|     (full screen, scrolling)  |
|     [primary interface]       |
|                               |
|  14:23:07 alpha  [i] armed   |
|  14:23:08 bravo  [i] armed   |
|  14:23:12 SWARM  [i] started |
|  14:25:17 charlie[!!] LOST   |
|                               |
+-------------------------------+
| [Pause] [RTL All] [E-STOP]   |
+-------------------------------+
```

On phone, the **Mission Feed is the default and primary view**. The map is reduced to a collapsible 120px thumbnail at the top that shows drone positions at a minimal zoom level. Tapping the thumbnail expands the map to full screen (with a "back to feed" floating button to return). This design acknowledges that on a small screen, a text feed provides more actionable information per pixel than a map with tiny markers.

- **Quick actions**: Bottom bar shows only the 3 most critical actions as icon buttons: Pause/Resume, RTL All, and E-STOP. All other actions are in the hamburger menu.
- **Notification overlays**: On phone, critical alerts appear as a full-width banner at the top of the feed (below the map thumbnail), not on the map. Same 5-second auto-dismiss, same stacking rules.

### High Contrast Mode (Outdoor / Sunlight)

Activated via a toggle in settings (sun icon in top bar). Changes:

- Background shifts from `#0F1117` to `#000000` (pure black).
- Text shifts from `#F1F3F9` to `#FFFFFF` (pure white).
- All accent colors increase saturation by 20%.
- Map tiles switch to a high-contrast dark mode with bolder labels.
- UI element borders become 2px instead of 1px.
- Chart background changes to `#000000` with white gridlines.
- Minimum contrast ratio enforced: 10:1.

### Glove-Friendly Adaptations

- All buttons have a minimum tap target of 48x48px with at least 8px spacing between adjacent targets.
- No multi-touch gestures required for critical actions (except map pinch-zoom, which is non-critical).
- No swipe-to-delete or swipe-to-reveal patterns for destructive actions.
- Confirmation dialogs use large buttons (full-width, 56px tall).
- Text inputs have large clear buttons (X icon, 40x40px).
- Dropdown menus have 48px row height.

---

## Screen 8: Drone Loadout Builder

The Loadout Builder is a racing-game-inspired customization screen where the operator configures a drone's frame, motors, battery, payload, and connection type. Selecting any part instantly recalculates performance stats, with animated stat bars that slide left/right to give visceral "tuning" feedback -- the same feel as Gran Turismo or Need for Speed car customization screens.

### Layout (Three-Column)

```
+------------------------------+-------------------------------+-----------------------------+
|     DRONE SCHEMATIC          |       PARTS SELECTOR          |     PERFORMANCE STATS       |
|                              |                               |                             |
|   ┌────────────────────┐     |   Frame         [v Hex 550 ]  |   FLIGHT TIME  ████████░░  |
|   │      [TOP]         │     |   Motors        [v 2312 920]  |   28 min           green    |
|   │   ┌──────────┐     │     |   Battery       [v 6S 5000 ]  |                             |
|   │   │          │     │     |   Payload       [v LiDAR    ]  |   SPEED        ██████░░░░  |
|   │  [SIDE]  [SIDE]    │     |   Connection    [v SiK 915  ]  |   15 m/s            blue   |
|   │   │          │     │     |                               |                             |
|   │   └──────────┘     │     |   Each category is a         |   AGILITY      █████░░░░░  |
|   │   [BOTTOM_CENTER]  │     |   dropdown/card selector.     |   52 /100         yellow   |
|   │   [FRONT]          │     |   Selecting a part instantly  |                             |
|   └────────────────────┘     |   updates the stats panel.    |   STABILITY    ███████░░░  |
|                              |                               |   71 /100        purple    |
|   Mount points highlighted   |   Cards show: name, weight,   |                             |
|   with pulsing accent rings  |   thumbnail, key spec         |   RANGE        ████████░░  |
|   (top, bottom_center,       |                               |   4.2 km         orange    |
|    front, side)              |                               |                             |
|                              |                               |   WIND RESIST  ██████░░░░  |
|                              |                               |   38 km/h         white    |
+------------------------------+-------------------------------+-----------------------------+
|                                                                                           |
|   AUW: [██████████████████████████████░░░░░░░░] 2850g / 4000g max          T/W: 2.1:1    |
|   Compat: ✅ COMPATIBLE                                                                  |
|                                                                                           |
|   [Save Loadout]  [Compare]  | Presets: [Class A Standard] [Class B Recon]               |
|                               |          [Class C Compute]  [Class D Strike]              |
+------------------------------+-----------------------------------------------------------+
```

### Left Panel: Drone Schematic

- An SVG/Canvas representation of the selected frame, rendered top-down.
- **Mount points** are highlighted with pulsing accent-colored rings:
  - `top` -- top of airframe (e.g., GPS, antenna, upward-facing sensor)
  - `bottom_center` -- belly mount (e.g., camera gimbal, LiDAR, payload drop mechanism)
  - `front` -- forward-facing mount (e.g., FPV camera, obstacle avoidance sensor)
  - `side` -- lateral mounts (e.g., side-scan sensors, marker lights)
- When a payload is selected in the center panel, the corresponding mount point pulses brighter and the payload icon snaps to it.
- If a payload is incompatible with the selected frame's mount, the mount point turns red with a shake animation.

### Center Panel: Parts Selector

Five category selectors, each presented as a scrollable card list or dropdown:

| Category         | Example Options                                       | Key Stat Shown on Card     |
| ---------------- | ----------------------------------------------------- | -------------------------- |
| **Frame**        | Hex 550, Quad 450, X8 Heavy, Mini Racer               | Max AUW, mount points      |
| **Motors**       | 2312 920KV, 2814 700KV, 4010 370KV                    | Max thrust per motor       |
| **Battery**      | 4S 3300mAh, 6S 5000mAh, 6S 10000mAh, 12S 16000mAh   | Wh, weight                 |
| **Payload**      | None, FPV Camera, LiDAR, Multispectral, Compute Box, Drop Mechanism | Weight, mount point |
| **Connection**   | SiK 433MHz, SiK 915MHz, ESP32 Mesh, 4G LTE            | Range, latency             |

- Selecting any card triggers an immediate stat recalculation and animates the stat bars on the right.
- Cards that would exceed the frame's max AUW are shown with a red weight warning badge.
- Cards that are incompatible with the selected frame are shown dimmed with a lock icon.

### Right Panel: Performance Stat Bars

Six horizontal stat bars, styled like a racing game's vehicle stats. Each bar animates (slides left/right with easing) when a part changes.

| Stat              | Color    | Unit     | Source Calculation                                                       |
| ----------------- | -------- | -------- | ------------------------------------------------------------------------ |
| **FLIGHT TIME**   | Green    | minutes  | Battery Wh / estimated power draw (motors + payload + avionics)          |
| **SPEED**         | Blue     | m/s      | Max horizontal speed given thrust and AUW                                |
| **AGILITY**       | Yellow   | /100     | Score based on T/W ratio, frame geometry, moment of inertia              |
| **STABILITY**     | Purple   | /100     | Score based on frame symmetry, motor count, wind resistance, PID tuning  |
| **RANGE**         | Orange   | km       | Flight time x cruise speed, derated by connection range if radio-limited |
| **WIND RESIST**   | White    | km/h     | Max wind speed the loadout can hover in (based on excess thrust)         |

**Animation behavior:**
- When a part is changed, the previous bar width fades to 30% opacity and the new bar width slides in from the old position over 300ms with an ease-out curve.
- If the new value is worse, the delta zone (the gap between old and new) flashes red briefly.
- If the new value is better, the delta zone flashes green briefly.

### Below Stats: Weight and Compatibility

- **AUW (All-Up Weight) meter:** A horizontal progress bar showing current total weight vs. the frame's max AUW.
  - Green when under 70% of max.
  - Yellow from 70-90%.
  - Red above 90%.
  - Turns pulsing red with a warning icon if AUW exceeds max.
- **Thrust-to-weight ratio:** Displayed as a bold number (e.g., "T/W: 2.1:1"). Turns red if below 1.5:1 (unsafe margin).
- **Compatibility status:** One of three states:
  - `COMPATIBLE` -- all parts are compatible, AUW is within limits, T/W is safe.
  - `WARNINGS` -- the loadout will fly but has concerns (e.g., T/W below 2.0:1, flight time under 10 min).
  - `INCOMPATIBLE` -- the loadout cannot fly (e.g., AUW exceeds max, mount point conflict, missing required component).
- **Warning/error list:** Below the compatibility badge, a scrollable list of specific issues. Each item has a severity icon and a plain-English description (e.g., "Payload exceeds bottom_center mount capacity by 120g").

### Bottom Bar: Actions

| Button                  | Behavior                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| **Save Loadout**        | Saves the current configuration to the Fleet Registry for the selected drone. Confirmation dialog shows a summary diff if the loadout changed. |
| **Compare**             | Opens a side-by-side panel with another saved loadout. Both sets of stat bars are shown vertically aligned for easy comparison. |
| **Preset Quick-Load**   | Four buttons that load predefined loadout configurations:                                |
|                         | - **Class A Standard** -- heavy-lift hex, large battery, LiDAR, SiK 915MHz              |
|                         | - **Class B Recon** -- lightweight quad, medium battery, FPV camera, SiK 433MHz          |
|                         | - **Class C Compute** -- mid-size frame, large battery, compute box payload, ESP32 Mesh  |
|                         | - **Class D Strike** -- reinforced frame, high-KV motors, drop mechanism, 4G LTE         |

### Dark Theme Styling

- Background: `--color-bg-primary` (consistent with all other screens).
- Stat bar backgrounds: `--color-bg-tertiary` with 1px border in the stat's accent color at 30% opacity.
- Stat bar fills: solid accent color with a subtle gradient (left bright, right slightly darker).
- Cards: `--color-bg-secondary` with `--color-border-default` border. Selected card has a 2px accent border matching the stat it most affects.
- All text meets the WCAG AAA 7:1 contrast ratio requirement from the design principles.
- Touch targets are minimum 48x48px for glove operability.

---

## Component Architecture (Next.js)

### Technology Stack

| Layer            | Technology                                   |
| ---------------- | -------------------------------------------- |
| Framework        | Next.js 14+ (App Router)                     |
| Language         | TypeScript (strict mode)                     |
| State Management | Zustand (lightweight, no boilerplate)        |
| Real-time Data   | Native WebSocket (via custom hook)           |
| REST API         | fetch with React Query (TanStack Query v5)   |
| Map              | react-map-gl (Mapbox GL JS wrapper) or react-leaflet |
| Charts           | Recharts                                     |
| UI Components    | Radix UI primitives + custom styled components |
| Styling          | Tailwind CSS with custom design tokens       |
| Icons            | Lucide React                                 |
| Fonts            | next/font with Geist Sans + Geist Mono       |

### Component Tree

```
app/
  layout.tsx                    -- Root layout: font loading, theme provider, WebSocket provider
  page.tsx                      -- Redirects to /mission-control

  (screens)/
    mission-control/
      page.tsx                  -- MissionControlScreen
    planner/
      page.tsx                  -- MissionPlannerScreen
    fleet/
      page.tsx                  -- FleetManagerScreen
    preflight/
      page.tsx                  -- PreFlightCheckScreen
    telemetry/
      page.tsx                  -- TelemetryDashboardScreen
    replay/
      page.tsx                  -- MissionReplayScreen

components/
  layout/
    TopBar.tsx                  -- Navigation tabs, mission status, E-Stop button
    BottomActionBar.tsx         -- Quick action buttons (Takeoff, RTL, Land, Pause/Resume)
    Sidebar.tsx                 -- Collapsible panel wrapper
    TabletSwipePanel.tsx        -- Edge-swipe overlay panel for tablet mode
    MissionFeedPanel.tsx        -- Right sidebar wrapper for Mission Feed (collapse, resize)

  feed/
    MissionFeed.tsx             -- Core scrolling feed component (used in Mission Control + Telemetry)
    FeedEntry.tsx               -- Single feed entry (timestamp, drone ID, severity icon, message)
    FeedFilter.tsx              -- Filter dropdown (All / Critical / Warnings / Commands / Telemetry)
    NotificationOverlay.tsx     -- Map streak alert banner (slide-in, auto-dismiss, stacking)
    NotificationOverlayStack.tsx -- Manages stack of up to 3 overlays with dismiss logic

  map/
    MapContainer.tsx            -- Mapbox/Leaflet initialization, base layer
    DroneMarker.tsx             -- Single drone marker (position, heading, role color, selection state)
    DroneTrail.tsx              -- Breadcrumb trail polyline for a single drone
    WaypointMarker.tsx          -- Numbered waypoint circle
    MissionPath.tsx             -- Dashed line connecting waypoints
    GeofenceBoundary.tsx        -- Editable polygon overlay
    HomeLaunchMarker.tsx        -- "H" marker at launch point
    MapControls.tsx             -- Zoom, fit-all, toggles
    FormationPreview.tsx        -- Translucent drone formation preview (Planner only)

  fleet/
    FleetPanel.tsx              -- Sidebar fleet list (Mission Control)
    DroneCard.tsx               -- Per-drone summary card
    DroneCardExpanded.tsx       -- Expanded telemetry + action buttons
    FleetTable.tsx              -- Full fleet table (Fleet Manager)
    FleetTableRow.tsx           -- Single row with inline edit capability
    AddDroneModal.tsx           -- QR scan + manual entry flow
    CapabilityBadges.tsx        -- Camera, compute, payload, relay, thermal icons

  planner/
    FormationSelector.tsx       -- Formation type buttons + parameter controls
    DroneAssignmentTable.tsx    -- Waypoint assignment per drone
    MissionParametersForm.tsx   -- Global defaults (altitude, speed, loiter)
    GeofenceControls.tsx        -- Geofence settings
    WaypointPopover.tsx         -- Per-waypoint editor
    ValidationResultsModal.tsx  -- Validation pass/fail detail
    SaveLoadProfileModal.tsx    -- Save/load mission profiles

  preflight/
    PreFlightOverallStatus.tsx  -- "3/3 READY" or "BLOCKED" banner
    DroneCheckCard.tsx          -- Per-drone check card
    CheckIndicator.tsx          -- Single check item (animated bar + status)

  telemetry/
    BatteryChart.tsx            -- Multi-line battery chart
    AltitudeChart.tsx           -- Multi-line altitude chart
    SignalStrengthChart.tsx     -- Grouped bar chart
    GpsSatelliteChart.tsx       -- Grouped bar chart
    AlertBar.tsx                -- Critical alert slide-up banner (legacy, retained for Telemetry tab)

  replay/
    MissionSelector.tsx         -- List of recorded missions
    TimelineScrubber.tsx        -- Playback bar + event markers
    TransportControls.tsx       -- Play/pause/skip/speed buttons
    ReplaySyncedCharts.tsx      -- Smaller synced telemetry charts

  shared/
    EmergencyStopButton.tsx     -- The big red button (always rendered)
    ConfirmDialog.tsx           -- Confirmation modal for destructive actions
    Toast.tsx                   -- Non-critical notification toast
    ModalAlert.tsx              -- Critical alert modal
    StatusBadge.tsx             -- Pill-shaped status indicator
    RoleBadge.tsx               -- Drone role color pill
    BatteryIndicator.tsx        -- Battery percentage + color + mini bar
    SignalIndicator.tsx         -- RSSI bar icon
    GpsIndicator.tsx            -- Satellite count + fix quality

stores/
  useDroneStore.ts              -- Zustand store: all drone states
  useMissionStore.ts            -- Zustand store: mission state, waypoints, formation
  useAlertStore.ts              -- Zustand store: active alerts queue
  useFeedStore.ts               -- Zustand store: Mission Feed entries, filter state, overlay queue
  useReplayStore.ts             -- Zustand store: replay playback state
  useUIStore.ts                 -- Zustand store: panel visibility, selected drone, tablet mode

hooks/
  useWebSocket.ts               -- WebSocket connection, auto-reconnect, message parsing
  useTelemetry.ts               -- Subscribes to drone telemetry via WebSocket, updates droneStore
  useCommands.ts                -- REST API calls for commands (arm, takeoff, RTL, etc.)
  useMissionAPI.ts              -- REST API calls for mission CRUD (save, load, validate)
  usePreflightChecks.ts         -- Orchestrates preflight check sequence per drone
  useKeyboardShortcuts.ts       -- Global keyboard shortcut listener
  useTabletDetection.ts         -- Detects tablet viewport / user agent
  useHighContrast.ts            -- Toggles high contrast mode, persists to localStorage

lib/
  ws-client.ts                  -- WebSocket client class with reconnect logic
  api-client.ts                 -- REST API client (base URL, auth headers, error handling)
  drone-utils.ts                -- Utility functions (battery color, status label, role color)
  geo-utils.ts                  -- Geofence point-in-polygon, distance calculations
  format.ts                     -- Number formatting, coordinate formatting, time formatting
```

### Data Flow

```
                    Python Backend (MAVLink / Custom Protocol)
                           |                    ^
                    WebSocket (wss://)      REST API (https://)
                    (telemetry push)        (commands, CRUD)
                           |                    ^
                           v                    |
                    +------------------+   +------------------+
                    | useWebSocket.ts  |   | useCommands.ts   |
                    | (hook)           |   | useMissionAPI.ts |
                    +--------+---------+   +------------------+
                             |                    ^
                             v                    |
                    +------------------+          |
                    | useDroneStore.ts |          |
                    | (Zustand)        +----------+
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
         DroneMarker   DroneCard    BatteryChart
         (map layer)   (sidebar)   (telemetry)
```

#### WebSocket Protocol

The WebSocket connection at `wss://<host>/ws/telemetry` pushes JSON messages:

```typescript
// Incoming telemetry message (100ms interval per drone)
interface TelemetryMessage {
  type: "telemetry";
  drone_id: string;
  timestamp: number; // Unix ms
  lat: number;
  lon: number;
  alt_agl: number; // meters above ground level
  heading: number; // 0-359 degrees
  speed: number; // m/s ground speed
  climb_rate: number; // m/s vertical
  battery_pct: number; // 0-100
  battery_voltage: number; // volts
  gps_sats: number;
  gps_fix: "none" | "2d" | "3d";
  rssi: number; // dBm
  mode: string; // "STABILIZE", "AUTO", "RTL", "LAND", etc.
  armed: boolean;
  current_wp: number;
  wp_total: number;
}

// Incoming event message (on event occurrence)
interface EventMessage {
  type: "event";
  drone_id: string;
  timestamp: number;
  severity: "info" | "warning" | "critical";
  event: string; // "armed", "takeoff", "wp_reached", "rtl", "landed", "lost", "fence_breach", etc.
  detail: string; // Human-readable detail
}

// Incoming swarm status message (1s interval)
interface SwarmStatusMessage {
  type: "swarm_status";
  timestamp: number;
  mission_state: "idle" | "active" | "paused" | "complete" | "aborted";
  elapsed_seconds: number;
  drone_count: number;
  active_count: number;
}
```

#### REST API Endpoints

```
POST   /api/command/arm          { drone_id: string | "all" }
POST   /api/command/disarm       { drone_id: string | "all" }
POST   /api/command/takeoff      { drone_id: string | "all", altitude: number }
POST   /api/command/land         { drone_id: string | "all" }
POST   /api/command/rtl          { drone_id: string | "all" }
POST   /api/command/emergency    {}  -- stops all motors immediately
POST   /api/command/hold         { drone_id: string }
POST   /api/command/goto         { drone_id: string, lat: number, lon: number, alt: number }
POST   /api/command/set-mode     { drone_id: string, mode: string }
POST   /api/command/set-role     { drone_id: string, role: string }

GET    /api/mission/list                      -- list saved missions
GET    /api/mission/:id                       -- get mission detail
POST   /api/mission                           -- create/save mission
PUT    /api/mission/:id                       -- update mission
DELETE /api/mission/:id                       -- delete mission
POST   /api/mission/validate                  -- validate mission config
POST   /api/mission/auto-assign               -- auto-assign drones to waypoints

GET    /api/fleet                              -- list all drones
POST   /api/fleet/register                    -- register new drone
PUT    /api/fleet/:drone_id                   -- update drone config
DELETE /api/fleet/:drone_id                   -- remove drone
POST   /api/fleet/:drone_id/preflight         -- run preflight checks
POST   /api/fleet/:drone_id/firmware          -- flash firmware

GET    /api/replay/list                        -- list recorded missions
GET    /api/replay/:id                         -- get full replay data
GET    /api/replay/:id/export?format=json|kml|csv  -- export replay data
```

#### Zustand Store Structure

```typescript
// stores/useDroneStore.ts
interface DroneState {
  id: string;
  callsign: string;
  hw_class: "A" | "B" | "C" | "D";
  role: "recon" | "relay" | "strike" | "decoy";
  capabilities: string[];
  telemetry: TelemetryMessage | null; // Latest telemetry
  status: "idle" | "connected" | "armed" | "airborne" | "rtl" | "landed" | "lost";
  preflightResult: PreflightResult | null;
  lastSeen: number; // Unix ms timestamp of last telemetry
}

interface DroneStore {
  drones: Map<string, DroneState>;
  selectedDroneId: string | null;
  updateTelemetry: (msg: TelemetryMessage) => void;
  selectDrone: (id: string | null) => void;
  setRole: (id: string, role: DroneState["role"]) => void;
  addDrone: (drone: DroneState) => void;
  removeDrone: (id: string) => void;
  getDronesByRole: (role: DroneState["role"]) => DroneState[];
  getActiveDrones: () => DroneState[];
}

// stores/useMissionStore.ts
interface MissionStore {
  state: "idle" | "active" | "paused" | "complete" | "aborted";
  elapsedSeconds: number;
  waypoints: Waypoint[];
  formation: FormationType;
  formationParams: Record<string, number>;
  assignments: Map<string, number[]>; // drone_id -> waypoint indices
  geofence: GeoJSON.Polygon | null;
  globalParams: { altitude: number; speed: number; loiterTime: number; rtlAltitude: number };
  addWaypoint: (wp: Waypoint) => void;
  updateWaypoint: (index: number, wp: Partial<Waypoint>) => void;
  removeWaypoint: (index: number) => void;
  setFormation: (type: FormationType, params: Record<string, number>) => void;
  assignDrone: (droneId: string, waypointIndices: number[]) => void;
  autoAssign: () => Promise<void>;
  setGeofence: (polygon: GeoJSON.Polygon) => void;
  validate: () => Promise<ValidationResult>;
  saveMission: (name: string, description?: string) => Promise<void>;
  loadMission: (id: string) => Promise<void>;
}

// stores/useAlertStore.ts
interface Alert {
  id: string;
  severity: "warning" | "critical";
  message: string;
  droneId?: string;
  timestamp: number;
  acknowledged: boolean;
}

interface AlertStore {
  alerts: Alert[];
  addAlert: (alert: Omit<Alert, "id" | "acknowledged">) => void;
  acknowledge: (id: string) => void;
  acknowledgeAll: () => void;
  getUnacknowledged: () => Alert[];
}

// stores/useFeedStore.ts
interface FeedEntry {
  id: string;
  timestamp: number; // Unix ms
  type: "drone_event" | "swarm_event" | "telemetry_alert" | "critical_alert" | "system" | "operator_command";
  droneId?: string; // undefined for swarm/system/command entries
  severity: "info" | "warning" | "critical";
  message: string;
}

interface NotificationOverlay {
  id: string;
  entry: FeedEntry;
  createdAt: number;
  dismissed: boolean;
}

interface FeedStore {
  entries: FeedEntry[];
  filter: "all" | "critical" | "warnings" | "commands" | "telemetry";
  autoScroll: boolean;
  overlays: NotificationOverlay[]; // max 3 visible
  addEntry: (entry: Omit<FeedEntry, "id">) => void;
  setFilter: (filter: FeedStore["filter"]) => void;
  setAutoScroll: (val: boolean) => void;
  dismissOverlay: (id: string) => void;
  getFilteredEntries: () => FeedEntry[];
}

// stores/useUIStore.ts
interface UIStore {
  fleetPanelOpen: boolean;
  feedPanelOpen: boolean;
  isTabletMode: boolean;
  isPhoneMode: boolean;
  isHighContrast: boolean;
  activeTab: string;
  toggleFleetPanel: () => void;
  toggleFeedPanel: () => void;
  setTabletMode: (val: boolean) => void;
  setPhoneMode: (val: boolean) => void;
  setHighContrast: (val: boolean) => void;
  setActiveTab: (tab: string) => void;
}
```

### WebSocket Reconnection Strategy

```typescript
// lib/ws-client.ts
class WSClient {
  private url: string;
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = Infinity;
  private baseDelay = 1000; // 1 second
  private maxDelay = 30000; // 30 seconds

  connect(): void {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      // Show toast: "Connected to ground station"
    };
    this.ws.onclose = () => {
      // Show toast: "Connection lost. Reconnecting..."
      this.scheduleReconnect();
    };
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.dispatch(msg);
    };
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts),
      this.maxDelay
    );
    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  // Routes messages to the appropriate store
  private dispatch(msg: any): void {
    switch (msg.type) {
      case "telemetry":
        useDroneStore.getState().updateTelemetry(msg);
        break;
      case "event":
        // Add to Mission Feed
        useFeedStore.getState().addEntry({
          timestamp: msg.timestamp,
          type: msg.severity === "critical" ? "critical_alert" : "drone_event",
          droneId: msg.drone_id,
          severity: msg.severity,
          message: msg.detail,
        });
        // Also add to alert store for critical events (drives Alert Bar + Notification Overlays)
        if (msg.severity === "critical") {
          useAlertStore.getState().addAlert({
            severity: "critical",
            message: msg.detail,
            droneId: msg.drone_id,
            timestamp: msg.timestamp,
          });
        }
        break;
      case "swarm_status":
        useMissionStore.getState().updateSwarmStatus(msg);
        // Add swarm state changes to Mission Feed
        useFeedStore.getState().addEntry({
          timestamp: msg.timestamp,
          type: "swarm_event",
          severity: "info",
          message: `mission ${msg.mission_state} -- ${msg.active_count}/${msg.drone_count} drones active`,
        });
        break;
    }
  }
}
```

### Performance Considerations

- **Telemetry throttling**: The WebSocket delivers data at 10Hz per drone. For charts, downsample to 1Hz (1 data point per second). For map marker positions, use all 10Hz data with CSS/canvas interpolation for smooth movement.
- **React rendering**: Use `React.memo` on all drone card and marker components. Selector hooks from Zustand (`useStore(store, selector)`) prevent re-renders when unrelated state changes.
- **Map rendering**: Use Mapbox GL JS's built-in data-driven styling for drone markers (GeoJSON source + symbol layer) rather than React-rendered markers for better performance with many drones.
- **Virtual scrolling**: Mission Feed uses `react-window` for virtualized rendering of up to 2000 entries. The feed is rendered once and shared between Mission Control and Telemetry screens via `useFeedStore`.
- **Chart optimization**: Recharts with `isAnimationActive={false}` for real-time charts to prevent animation overhead. Use `shouldComponentUpdate` / memo to limit redraws.

---

## Interaction Patterns

### Confirmation Dialogs (Destructive Actions)

Used for: Arm All, Takeoff All, RTL All, Land All, Emergency Stop, Remove Drone.

```
+----------------------------------------------------+
|  CONFIRM TAKEOFF ALL                           [X]  |
|----------------------------------------------------|
|                                                      |
|  You are about to command ALL 3 drones to take off   |
|  to altitude 50m.                                    |
|                                                      |
|  Drones: alpha, bravo, charlie                       |
|                                                      |
|  [Cancel]              [CONFIRM TAKEOFF]             |
+----------------------------------------------------+
```

- Modal overlay with `--bg-primary` background at 80% opacity behind it.
- Dialog card: `--bg-secondary` background, 8px border-radius, max-width 480px, centered.
- Cancel button: `--bg-tertiary`, left aligned.
- Confirm button: colored by action type (green for takeoff, purple for RTL, red for emergency), right aligned.
- Keyboard: `Enter` confirms, `Escape` cancels.
- The dialog is focus-trapped (tab cycles within the dialog).

### Emergency Stop Confirmation

Special variant of the confirm dialog with two tiers of action:

```
+----------------------------------------------------+
|  !!! EMERGENCY LAND !!!                             |
|----------------------------------------------------|
|                                                      |
|  All drones will IMMEDIATELY begin a controlled      |
|  descent and land at their current position.         |
|                                                      |
|  [Cancel]            [CONFIRM EMERGENCY LAND]        |
|                                                      |
|  ................................................    |
|  KILL MOTORS (hold 3s)                               |
|  ⚠ Drones will fall from current altitude            |
+----------------------------------------------------+
```

- Dialog background: `--danger-bg` border (4px solid `--danger`).
- Cancel button: Standard `--bg-tertiary`, no countdown. The operator explicitly confirms or cancels.
- Confirm E-Land button: Full `--danger` background, white bold text. Full width on tablet mode. Executes `emergency_land()`.
- Kill Motors button: Below a visual separator. Smaller text (12px), recessed style (`--bg-tertiary` background, `--danger` text). Requires a **3-second long-press** -- a circular progress indicator fills during the hold. Releasing early cancels. Executes `emergency_stop()` (force-disarm, motors cut immediately).
- Warning label: "Drones will fall from current altitude" is always visible next to the Kill Motors button in `--danger` color, 11px italic.
- Audio: Warning alarm plays while dialog is open.

### Toast Notifications

For non-critical, informational events:

- Position: Top-center, below the top bar.
- Appearance: `--bg-secondary` background, `--border` border, 8px border-radius, shadow.
- Content: Icon (type-colored) + message text. Max 1 line.
- Duration: 4 seconds, then fade out (300ms).
- Stack: Up to 3 toasts visible, newest on top, older ones shift down.
- Types:
  - Info (blue icon): "Mission saved", "Drone alpha connected".
  - Success (green icon): "All preflight checks passed".
  - Warning (amber icon): "bravo battery at 28%".
- Dismissible: Swipe right or tap X.

### Modal Alerts (Critical Events)

For events requiring immediate attention:

- Full-screen overlay, `--bg-primary` at 85% opacity.
- Centered card, `--bg-secondary`, max-width 520px.
- Top border: 4px solid in severity color (red for critical).
- Audio: Alarm tone (distinct from E-Stop alarm).
- Content: Large icon, bold title, detail text, affected drone info, recommended action.
- Actions: `[Acknowledge]` dismisses the modal. `[RTL <drone>]` if applicable. `[View on Map]` centers map on the affected drone and switches to Mission Control tab.

Example:

```
+----------------------------------------------------+
|  [!] CONNECTION LOST                                 |
|----------------------------------------------------|
|                                                      |
|  Drone: bravo (Relay)                                |
|  Last seen: 14:25:17 (12 seconds ago)                |
|  Last position: 34.0522°N, -118.2437°W, 45m AGL    |
|                                                      |
|  Failsafe action: RTL (automatic)                    |
|                                                      |
|  [Acknowledge]  [View on Map]                        |
+----------------------------------------------------+
```

### Tap-to-Filter (Map Marker Selection)

The tap-to-filter interaction on map drone markers (see [Drone Position Markers](#drone-position-markers----rich-drone-markers)) is the **primary way operators investigate individual drone status**. This replaces the old "expanded telemetry" concept as the detailed inspection flow. The fleet sidebar drone cards still exist for quick reference and at-a-glance fleet overview, but the map info card (triggered by tapping a marker) is now the canonical detailed view. This design prioritizes spatial context -- operators see the drone's telemetry anchored to its position on the map, rather than in a disconnected sidebar panel.

---

## Keyboard Shortcuts

All shortcuts are global (active regardless of focused element, except when a text input has focus).

| Key           | Action                          | Context              |
| ------------- | ------------------------------- | -------------------- |
| `T`           | Takeoff All (opens confirm)     | Mission Control      |
| `R`           | RTL All (opens confirm)         | Mission Control      |
| `L`           | Land All (opens confirm)        | Mission Control      |
| `E`           | Emergency Land (opens confirm)  | Global               |
| `Space`       | Pause / Resume mission          | Mission Control      |
| `1` - `9`     | Select drone 1-9                | Mission Control      |
| `0`           | Deselect drone                  | Mission Control      |
| `F`           | Fit all drones on map           | Mission Control      |
| `Escape`      | Close any open modal/panel      | Global               |
| `Ctrl+S`      | Save mission profile            | Planner              |
| `Ctrl+Z`      | Undo last waypoint placement    | Planner              |
| `Ctrl+Shift+Z`| Redo waypoint placement         | Planner              |
| `Delete`      | Delete selected waypoint        | Planner              |
| `[`           | Toggle fleet panel              | Mission Control      |
| `]`           | Toggle Mission Feed panel       | Mission Control          |
| `+` / `-`     | Zoom map in / out               | Any map view         |

Shortcuts are displayed in a help overlay triggered by `?` key.

### Keyboard Shortcut Implementation

```typescript
// hooks/useKeyboardShortcuts.ts
// Uses a global keydown listener on the document.
// Ignores key events when the active element is an input, textarea, or select.
// Maps key codes to action functions from stores.
// Handles modifier keys (Ctrl, Shift) for compound shortcuts.
```

---

## Accessibility and Field Ergonomics

### ARIA Roles and Labels

- All interactive elements have descriptive `aria-label` attributes.
- Status badges use `role="status"` and `aria-live="polite"` (or `"assertive"` for critical alerts).
- Map is marked with `role="application"` with a descriptive `aria-label="Drone swarm map view"`.
- Drone list uses `role="listbox"` with `role="option"` per drone card.
- Charts include `aria-label` describing the data (e.g., "Battery percentage over time for all drones").

### Screen Reader Announcements

- Critical alerts trigger `aria-live="assertive"` announcements.
- Preflight check results are announced as they complete: "alpha communications check passed".
- Mission state changes are announced: "Mission is now active".

### Color Blindness Considerations

All status-conveying colors are paired with a shape or icon:
- Connected: green + solid circle.
- Armed: amber + triangle.
- Airborne: blue + upward arrow.
- Lost: red + question mark.
- RTL: purple + home icon.

Charts use both color and pattern (dashed vs solid lines) to distinguish drones. A colorblind mode (accessible from settings) shifts the palette to a deuteranopia-safe set.

### Field-Specific Considerations

- **Rain on screen**: Large touch targets and generous spacing reduce accidental taps from water droplets. No gesture-only interactions for critical functions.
- **Vibration (vehicle-mounted)**: UI elements have generous padding. No precision-required interactions (e.g., no drag targets smaller than 48px).
- **Noise**: All audio alerts are accompanied by visual alerts. Audio is supplementary, not primary.
- **Stress**: The most critical action (Emergency Stop) is the most visually prominent and easiest to reach. Confirmation dialogs prevent accidental activation but are fast enough (under 4 seconds) for real emergencies.

---

## Responsive Breakpoints

| Breakpoint       | Width        | Layout                                                                 |
| ---------------- | ------------ | ---------------------------------------------------------------------- |
| Desktop XL       | >= 1440px    | 3-column: Fleet (300px) | Map (~60%) | Mission Feed (320px)            |
| Desktop          | 1200-1439px  | 3-column with reduced padding, feed may collapse to 280px              |
| Tablet Landscape | 768-1199px   | Map full screen + overlay panels (swipe left: fleet, swipe right: feed)|
| Tablet Portrait  | 600-767px    | Map (top ~60%) + Mission Feed bottom drawer (40% viewport height)      |
| Phone            | < 600px      | **Feed-first**: Mission Feed full screen, map as collapsible thumbnail |

Phone mode is now fully supported with the feed-first layout. The old "not supported" warning is removed -- the Mission Feed makes phone-sized screens viable for field monitoring.

---

## File and Directory Conventions

```
src/
  app/                      -- Next.js App Router pages
  components/               -- All React components (as listed in component tree)
  stores/                   -- Zustand stores
  hooks/                    -- Custom React hooks
  lib/                      -- Utility functions and API clients
  types/                    -- TypeScript type definitions
    drone.ts                -- DroneState, TelemetryMessage, etc.
    mission.ts              -- Waypoint, Formation, ValidationResult, etc.
    api.ts                  -- API request/response types
  styles/
    globals.css             -- Tailwind imports + CSS custom properties (design tokens)
    high-contrast.css       -- High contrast mode overrides
```

---

## Summary of Key Design Decisions

1. **Zustand over Redux/Context**: Minimal boilerplate, supports selectors for performance, works naturally with WebSocket-driven updates outside React lifecycle.
2. **Mapbox GL JS over Leaflet**: Better performance with real-time marker updates, built-in support for data-driven styling and line gradients. Leaflet fallback for offline/self-hosted deployments.
3. **Dark theme only (no light mode)**: Outdoor use in bright sunlight is better served by dark backgrounds that reduce glare. High contrast mode handles the worst-case sunlight scenarios.
4. **No hover-dependent interactions**: Field operators use tablets with gloves. Every interaction that has a hover state also has a tap/click equivalent.
5. **Confirmation dialogs for all destructive actions**: In a safety-critical application, accidental taps must never cause drone commands. The E-Stop confirmation has a 3-second cancel cooldown to prevent panic-double-tap cancellation.
6. **100ms telemetry for map, 1s for charts**: Map smoothness requires high-frequency updates; chart readability does not benefit from sub-second updates and the render cost is not justified.
7. **WebSocket for telemetry, REST for commands**: Telemetry is high-frequency push data (WebSocket is ideal). Commands are infrequent request-response interactions (REST is simpler and provides clear success/error semantics).
8. **Mission Feed over traditional event log**: A persistent scrolling text feed (styled like a terminal/radio log) is faster for field operators to parse under stress than navigating to a separate telemetry tab. Military operators are trained on radio logs -- the feed leverages that instinct.
9. **Feed-first on phone**: On screens below 600px, the Mission Feed becomes the primary interface instead of the map. A text feed provides more actionable information per pixel than a map with tiny markers on a small screen.
10. **Notification overlays (streak alerts)**: Critical events need to interrupt the operator's attention even when they are focused on the map. Livestream-style slide-in banners provide a non-modal interrupt that auto-dismisses, avoiding alert fatigue from persistent modals.

---

## Related Documents

- [[API_DESIGN]] -- API endpoints that back each UI action
- [[SYSTEM_ARCHITECTURE]] -- Backend architecture powering the ground station
- [[PRODUCT_SPEC]] -- Feature requirements driving UI design
- [[INTEGRATION_AUDIT]] -- UI-to-API alignment audit results
- [[DECISION_LOG]] -- Feed-first design decision rationale
