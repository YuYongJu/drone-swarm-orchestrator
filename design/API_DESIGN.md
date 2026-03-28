---
title: API Design Specification
type: design
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, api, backend]
---

# Drone Swarm Orchestrator -- API Design Specification

**Version:** 1.0.0
**Last Updated:** 2026-03-26
**Status:** Draft

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Authentication](#3-authentication)
4. [Versioning](#4-versioning)
5. [Rate Limiting](#5-rate-limiting)
6. [Error Handling](#6-error-handling)
7. [REST API Endpoints](#7-rest-api-endpoints)
   - 7.1 Swarm Control
   - 7.2 Fleet Management
   - 7.3 Mission Planning
   - 7.4 Geofencing
   - 7.5 Telemetry History
   - 7.6 Replay
   - 7.7 Configuration
8. [WebSocket Protocol](#8-websocket-protocol)
   - 8.1 Connection Lifecycle
   - 8.2 Telemetry Stream
   - 8.3 Swarm Events
   - 8.4 Alerts
   - 8.5 Command Acknowledgments
   - 8.6 Connection Status
9. [Appendix](#9-appendix)

---

## 1. Overview

This document specifies the API layer between the Next.js ground station UI and the Python orchestration backend for the drone swarm platform. The API is split into two transports:

- **REST API** (HTTP/1.1 over TLS) -- Command-and-control operations, CRUD, queries.
- **WebSocket** (WSS) -- Real-time telemetry streaming, event notifications, command acknowledgments.

All payloads are JSON. All timestamps are ISO 8601 in UTC. All distances are in meters, speeds in m/s, angles in degrees, altitudes in meters MSL unless stated otherwise.

---

## 2. Architecture

```
+-------------------+         HTTPS / WSS          +---------------------+
|  Next.js Ground   | <--------------------------> |  Python Backend     |
|  Station UI       |    REST: /api/v1/*           |  (FastAPI + uvicorn)|
|                   |    WS:   /ws/v1/stream       |                     |
+-------------------+                               +---------------------+
                                                           |
                                                    MAVLink / DroneKit
                                                           |
                                                    +------v------+
                                                    |  Drone Fleet |
                                                    +--------------+
```

The backend exposes a single HTTP server. REST endpoints handle discrete operations. A persistent WebSocket connection delivers real-time data to each connected ground station.

---

## 3. Authentication

### 3.1 Token Format

The platform uses JWT (JSON Web Tokens) signed with RS256.

```json
{
  "sub": "operator-uuid",
  "role": "pilot" | "observer" | "admin",
  "fleet_ids": ["fleet-uuid-1"],
  "iat": 1711411200,
  "exp": 1711414800
}
```

### 3.2 Obtaining a Token

```
POST /api/v1/auth/login
```

**Request Body:**

```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### 3.3 Refreshing a Token

```
POST /api/v1/auth/refresh
```

**Request Body:**

```json
{
  "refresh_token": "string"
}
```

**Response (200):** Same shape as login response with new tokens.

### 3.4 Using the Token

Include the token in every REST request:

```
Authorization: Bearer <access_token>
```

For WebSocket, pass the token as a query parameter on the initial handshake:

```
wss://host/ws/v1/stream?token=<access_token>
```

### 3.5 Roles and Permissions

| Role       | Can read telemetry | Can issue commands | Can manage fleet | Can manage operators |
|------------|--------------------|--------------------|------------------|----------------------|
| `observer` | Yes                | No                 | No               | No                   |
| `pilot`    | Yes                | Yes                | No               | No                   |
| `admin`    | Yes                | Yes                | Yes              | Yes                  |

### 3.6 Multi-Operator Mode

When multiple operators connect to the same fleet, the backend enforces a **command lock** model:

- Only one operator can hold the command lock for a given fleet at a time.
- Other operators with `pilot` role are downgraded to `observer` until the lock is released or transferred.
- Lock acquisition is via `POST /api/v1/fleets/{fleet_id}/lock`.
- Lock state is broadcast over WebSocket so all connected clients update their UI.

---

## 4. Versioning

### 4.1 Strategy

All endpoints are prefixed with `/api/v{major}`. The current version is `v1`.

- **Major version bump** -- Breaking changes (removed fields, changed semantics). Old version supported for 6 months after deprecation notice.
- **Minor/patch changes** -- Additive changes (new optional fields, new endpoints) happen within the current version without a bump.

### 4.2 Version Negotiation

Clients must specify the version in the URL path. There is no header-based negotiation. If a client requests a version that no longer exists, the server returns:

```json
{
  "error": {
    "code": "VERSION_UNSUPPORTED",
    "message": "API version v0 is no longer supported. Use v1.",
    "supported_versions": ["v1"]
  }
}
```

### 4.3 Deprecation Headers

When a version is deprecated but still functional, responses include:

```
Sunset: Sat, 01 Nov 2026 00:00:00 GMT
Deprecation: true
Link: </api/v2/docs>; rel="successor-version"
```

---

## 5. Rate Limiting

### 5.1 Limits

| Category            | Limit              | Window   | Scope       |
|---------------------|--------------------|----------|-------------|
| Read endpoints      | 300 requests       | 1 minute | Per token   |
| Write endpoints     | 60 requests        | 1 minute | Per token   |
| Command endpoints   | 10 requests        | 1 second | Per fleet   |
| Auth endpoints      | 5 requests         | 1 minute | Per IP      |
| WebSocket messages  | 20 messages        | 1 second | Per connection |

**Command endpoints** include any endpoint that issues a MAVLink command to the drones (swarm control, emergency stop, mission start/abort). The per-fleet limit prevents accidental command floods from crashing the flight controller.

### 5.2 Response Headers

Every response includes:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1711411260
```

### 5.3 Exceeded Limit Response

```
HTTP/1.1 429 Too Many Requests
Retry-After: 12
```

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Command rate limit exceeded for fleet abc-123. Retry after 12 seconds.",
    "retry_after_seconds": 12
  }
}
```

---

## 6. Error Handling

### 6.1 Standard Error Response Format

Every error response follows this structure:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {} | null,
    "request_id": "string",
    "timestamp": "ISO 8601 string"
  }
}
```

| Field        | Type              | Description                                        |
|--------------|-------------------|----------------------------------------------------|
| `code`       | `string`          | Machine-readable error code (UPPER_SNAKE_CASE)     |
| `message`    | `string`          | Human-readable description                         |
| `details`    | `object` or `null`| Additional context (validation errors, etc.)       |
| `request_id` | `string`          | UUID for correlating with server logs              |
| `timestamp`  | `string`          | When the error occurred                            |

### 6.2 Error Codes

| HTTP Status | Code                        | Meaning                                           |
|-------------|-----------------------------|----------------------------------------------------|
| 400         | `VALIDATION_ERROR`          | Request body failed schema validation              |
| 400         | `INVALID_COORDINATES`       | Lat/lon out of valid range                         |
| 400         | `MISSION_CONFLICT`          | Mission cannot start; another is active            |
| 401         | `AUTHENTICATION_REQUIRED`   | Missing or expired token                           |
| 403         | `INSUFFICIENT_PERMISSIONS`  | Role does not allow this operation                 |
| 403         | `COMMAND_LOCK_HELD`         | Another operator holds the command lock            |
| 404         | `DRONE_NOT_FOUND`           | Drone ID does not exist in the fleet               |
| 404         | `FLEET_NOT_FOUND`           | Fleet ID does not exist                            |
| 404         | `MISSION_NOT_FOUND`         | Mission ID does not exist                          |
| 404         | `GEOFENCE_NOT_FOUND`        | Geofence ID does not exist                         |
| 409         | `DRONE_ALREADY_REGISTERED`  | Drone with this sys_id already exists in fleet     |
| 409         | `GEOFENCE_OVERLAP`          | New geofence conflicts with existing exclusion zone|
| 422         | `PREFLIGHT_FAILED`          | One or more drones failed preflight checks         |
| 500         | `INTERNAL_ERROR`            | Unexpected server error                            |
| 502         | `DRONE_COMMS_ERROR`         | Backend cannot reach one or more drones            |
| 503         | `ORCHESTRATOR_UNAVAILABLE`  | Orchestration engine not ready                     |
| 504         | `COMMAND_TIMEOUT`           | Drone did not acknowledge command in time          |

### 6.3 Retry Behavior

| Error Code                 | Client Should Retry? | Strategy                                     |
|----------------------------|----------------------|----------------------------------------------|
| `RATE_LIMIT_EXCEEDED`      | Yes                  | Wait `retry_after_seconds`, then retry once  |
| `COMMAND_TIMEOUT`          | Yes                  | Exponential backoff, max 3 retries           |
| `DRONE_COMMS_ERROR`        | Yes                  | Wait 2s, retry up to 3 times                |
| `ORCHESTRATOR_UNAVAILABLE` | Yes                  | Exponential backoff starting at 1s, max 30s  |
| `INTERNAL_ERROR`           | Maybe                | Retry once after 1s; if repeated, stop       |
| `VALIDATION_ERROR`         | No                   | Fix the request payload                      |
| `AUTHENTICATION_REQUIRED`  | No (refresh token)   | Refresh the token, then retry original request|
| All other 4xx              | No                   | Do not retry                                 |

### 6.4 Validation Error Details

When `code` is `VALIDATION_ERROR`, the `details` field contains per-field errors:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "fields": [
        {
          "field": "waypoints[2].altitude",
          "reason": "Must be between 2 and 120 meters",
          "value": 150
        },
        {
          "field": "speed",
          "reason": "Required field missing",
          "value": null
        }
      ]
    },
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "timestamp": "2026-03-26T14:30:00Z"
  }
}
```

---

## 7. REST API Endpoints

### Common Types

The following types are referenced throughout the endpoint definitions.

**Coordinate:**
```json
{
  "lat": "number (float64, -90 to 90)",
  "lon": "number (float64, -180 to 180)",
  "alt": "number (float64, meters MSL)"
}
```

**DroneStatus enum:** `"disconnected"` | `"connected"` | `"armed"` | `"airborne"` | `"returning"` | `"landed"` | `"lost"`

**MissionState enum:** `"draft"` | `"validated"` | `"active"` | `"paused"` | `"completed"` | `"aborted"` | `"failed"`

**FormationType enum:** `"line"` | `"v_shape"` | `"diamond"` | `"grid"` | `"circle"` | `"custom"`

---

### 7.1 Swarm Control

#### 7.1.1 Arm All Drones

Arms all drones in the fleet that passed preflight checks.

```
POST /api/v1/fleets/{fleet_id}/swarm/arm
```

**Path Parameters:**

| Param      | Type   | Description       |
|------------|--------|-------------------|
| `fleet_id` | `uuid` | Target fleet ID   |

**Request Body:** None

**Response (200):**

```json
{
  "command_id": "uuid",
  "armed_drones": ["drone-uuid-1", "drone-uuid-2"],
  "failed_drones": [
    {
      "drone_id": "drone-uuid-3",
      "reason": "GPS fix insufficient (hdop=4.2, required<=2.0)"
    }
  ],
  "timestamp": "2026-03-26T14:30:00Z"
}
```

**Error Responses:** 403 `COMMAND_LOCK_HELD`, 404 `FLEET_NOT_FOUND`, 502 `DRONE_COMMS_ERROR`

---

#### 7.1.2 Takeoff

Commands the swarm to take off to a specified altitude.

```
POST /api/v1/fleets/{fleet_id}/swarm/takeoff
```

**Request Body:**

```json
{
  "target_altitude": "number (meters AGL, 2-120, required)",
  "drone_ids": "string[] | null (null = all armed drones)"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "estimated_completion_seconds": 15,
  "timestamp": "2026-03-26T14:30:05Z"
}
```

**Example Request:**

```bash
curl -X POST https://gcs.example.com/api/v1/fleets/f1a2b3c4/swarm/takeoff \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"target_altitude": 20}'
```

**Error Responses:** 400 `VALIDATION_ERROR`, 400 `MISSION_CONFLICT`, 403 `COMMAND_LOCK_HELD`, 422 `PREFLIGHT_FAILED`

---

#### 7.1.3 Land

Commands the swarm to land at current positions or at designated landing coordinates.

```
POST /api/v1/fleets/{fleet_id}/swarm/land
```

**Request Body:**

```json
{
  "mode": "\"in_place\" | \"home\" | \"coordinates\" (required)",
  "coordinates": "Coordinate[] | null (required if mode=coordinates, one per drone)",
  "drone_ids": "string[] | null (null = all airborne drones)"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "estimated_completion_seconds": 25,
  "timestamp": "2026-03-26T14:35:00Z"
}
```

**Error Responses:** 400 `VALIDATION_ERROR`, 403 `COMMAND_LOCK_HELD`, 404 `FLEET_NOT_FOUND`

---

#### 7.1.4 Return to Launch (RTL)

```
POST /api/v1/fleets/{fleet_id}/swarm/rtl
```

**Request Body:**

```json
{
  "drone_ids": "string[] | null (null = all airborne drones)"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "timestamp": "2026-03-26T14:35:00Z"
}
```

**Error Responses:** 403 `COMMAND_LOCK_HELD`, 404 `FLEET_NOT_FOUND`

---

#### 7.1.5 Emergency Land

Commands all drones to switch to LAND mode (controlled descent). This is the preferred emergency action -- drones descend under flight controller control, which is safer than a motor kill.

```
POST /api/v1/fleets/{fleet_id}/swarm/emergency-land
```

**Request Body:** None

**Special Behavior:**
- Bypasses the command lock -- any `pilot` or `admin` can trigger it.
- Bypasses rate limiting.
- Sends SET_MODE(LAND) to all drones that are airborne, returning, or armed.
- Cancels all running missions.

**Response (200):**

```json
{
  "command_id": "uuid",
  "mode": "land",
  "affected_drones": ["drone-uuid-1", "drone-uuid-2", "drone-uuid-3"],
  "timestamp": "2026-03-26T14:36:00Z"
}
```

**Error Responses:** 404 `FLEET_NOT_FOUND`, 502 `DRONE_COMMS_ERROR`

---

#### 7.1.6 Emergency Kill

Force disarm all motors immediately. Drones will fall from the sky. This is a LAST RESORT -- use only when controlled landing is impossible (e.g., flyaway, software failure).

```
POST /api/v1/fleets/{fleet_id}/swarm/emergency-kill
```

**Request Body:**

```json
{
  "confirm": "boolean (required, must be true)"
}
```

**Special Behavior:**
- Bypasses the command lock -- any `pilot` or `admin` can trigger it.
- Bypasses rate limiting.
- Requires explicit confirmation (`"confirm": true`) to prevent accidental invocation.
- Sends MAV_CMD_COMPONENT_ARM_DISARM with `force=21196` to all drones.

**Response (200):**

```json
{
  "command_id": "uuid",
  "mode": "kill",
  "affected_drones": ["drone-uuid-1", "drone-uuid-2", "drone-uuid-3"],
  "timestamp": "2026-03-26T14:36:00Z"
}
```

**Error Responses:** 400 `CONFIRMATION_REQUIRED` (if confirm is false or missing), 404 `FLEET_NOT_FOUND`, 502 `DRONE_COMMS_ERROR`

---

#### 7.1.7 Set Formation

Commands the swarm to adopt a formation shape.

```
POST /api/v1/fleets/{fleet_id}/swarm/formation
```

**Request Body:**

```json
{
  "type": "FormationType (required)",
  "spacing": "number (meters between drones, 3-100, required)",
  "heading": "number (degrees 0-360, formation heading, required)",
  "center": "Coordinate (center point of formation, required)",
  "custom_offsets": "Coordinate[] | null (required if type=custom, relative offsets from center)"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "target_positions": [
    {"drone_id": "drone-uuid-1", "position": {"lat": 37.7749, "lon": -122.4194, "alt": 20}},
    {"drone_id": "drone-uuid-2", "position": {"lat": 37.7750, "lon": -122.4193, "alt": 20}}
  ],
  "timestamp": "2026-03-26T14:31:00Z"
}
```

**Example Request:**

```bash
curl -X POST https://gcs.example.com/api/v1/fleets/f1a2b3c4/swarm/formation \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "type": "v_shape",
    "spacing": 10,
    "heading": 90,
    "center": {"lat": 37.7749, "lon": -122.4194, "alt": 20}
  }'
```

**Error Responses:** 400 `VALIDATION_ERROR`, 403 `COMMAND_LOCK_HELD`, 404 `FLEET_NOT_FOUND`

---

#### 7.1.7 Goto Waypoint

Commands the swarm to fly to a single waypoint while maintaining current formation.

```
POST /api/v1/fleets/{fleet_id}/swarm/goto
```

**Request Body:**

```json
{
  "waypoint": "Coordinate (required)",
  "speed": "number (m/s, 0.5-15, required)",
  "maintain_formation": "boolean (default true)"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "estimated_arrival_seconds": 45,
  "timestamp": "2026-03-26T14:32:00Z"
}
```

**Error Responses:** 400 `VALIDATION_ERROR`, 400 `INVALID_COORDINATES`, 403 `COMMAND_LOCK_HELD`

---

#### 7.1.8 Pause / Resume

```
POST /api/v1/fleets/{fleet_id}/swarm/pause
POST /api/v1/fleets/{fleet_id}/swarm/resume
```

**Request Body:** None

**Response (200):**

```json
{
  "command_id": "uuid",
  "status": "accepted",
  "swarm_state": "paused" | "active",
  "timestamp": "2026-03-26T14:33:00Z"
}
```

**Error Responses:** 400 `MISSION_CONFLICT` (nothing to pause/resume), 403 `COMMAND_LOCK_HELD`

---

### 7.2 Fleet Management

#### 7.2.1 List Fleets

```
GET /api/v1/fleets
```

**Query Parameters:**

| Param    | Type     | Default | Description                 |
|----------|----------|---------|-----------------------------|
| `page`   | `int`    | 1       | Page number                 |
| `limit`  | `int`    | 20      | Items per page (max 100)    |
| `status` | `string` | null    | Filter by fleet status      |

**Response (200):**

```json
{
  "fleets": [
    {
      "id": "uuid",
      "name": "Survey Team Alpha",
      "drone_count": 3,
      "status": "idle",
      "created_at": "2026-03-20T10:00:00Z",
      "updated_at": "2026-03-26T14:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 3,
    "total_pages": 1
  }
}
```

---

#### 7.2.2 Create Fleet

```
POST /api/v1/fleets
```

**Request Body:**

```json
{
  "name": "string (1-100 chars, required)",
  "description": "string (0-500 chars, optional)",
  "default_altitude": "number (meters AGL, 2-120, optional, default 20)",
  "default_speed": "number (m/s, 0.5-15, optional, default 5)",
  "max_drones": "integer (1-50, optional, default 10)"
}
```

**Response (201):**

```json
{
  "id": "uuid",
  "name": "Survey Team Alpha",
  "description": "Three-drone survey configuration",
  "default_altitude": 20,
  "default_speed": 5,
  "max_drones": 10,
  "drone_count": 0,
  "status": "idle",
  "created_at": "2026-03-26T14:00:00Z",
  "updated_at": "2026-03-26T14:00:00Z"
}
```

**Error Responses:** 400 `VALIDATION_ERROR`

---

#### 7.2.3 Get Fleet Details

```
GET /api/v1/fleets/{fleet_id}
```

**Response (200):**

```json
{
  "id": "uuid",
  "name": "Survey Team Alpha",
  "description": "Three-drone survey configuration",
  "default_altitude": 20,
  "default_speed": 5,
  "max_drones": 10,
  "status": "idle",
  "command_lock": {
    "held_by": "operator-uuid" | null,
    "acquired_at": "ISO 8601" | null
  },
  "drones": [
    {
      "id": "uuid",
      "name": "Drone-01",
      "sys_id": 1,
      "model": "Holybro X500 V2",
      "status": "idle",
      "battery_percent": 95,
      "position": {"lat": 37.7749, "lon": -122.4194, "alt": 0},
      "firmware_version": "ArduCopter 4.5.1",
      "last_heartbeat": "2026-03-26T14:29:55Z"
    }
  ],
  "created_at": "2026-03-26T14:00:00Z",
  "updated_at": "2026-03-26T14:00:00Z"
}
```

**Error Responses:** 404 `FLEET_NOT_FOUND`

---

#### 7.2.4 Update Fleet

```
PATCH /api/v1/fleets/{fleet_id}
```

**Request Body:** Any subset of fields from the create request.

**Response (200):** Full fleet object.

**Error Responses:** 400 `VALIDATION_ERROR`, 404 `FLEET_NOT_FOUND`

---

#### 7.2.5 Delete Fleet

```
DELETE /api/v1/fleets/{fleet_id}
```

**Preconditions:** Fleet must have no active missions. All drones must be in `idle` or `offline` status.

**Response (204):** No content.

**Error Responses:** 400 `MISSION_CONFLICT`, 404 `FLEET_NOT_FOUND`

---

#### 7.2.6 Register Drone to Fleet

```
POST /api/v1/fleets/{fleet_id}/drones
```

**Request Body:**

```json
{
  "name": "string (1-50 chars, required)",
  "sys_id": "integer (1-255, MAVLink system ID, required)",
  "model": "string (optional)",
  "connection_string": "string (e.g. 'udp:127.0.0.1:14550', required)",
  "home_position": "Coordinate (optional)"
}
```

**Response (201):**

```json
{
  "id": "uuid",
  "fleet_id": "uuid",
  "name": "Drone-01",
  "sys_id": 1,
  "model": "Holybro X500 V2",
  "connection_string": "udp:127.0.0.1:14550",
  "status": "offline",
  "home_position": {"lat": 37.7749, "lon": -122.4194, "alt": 0},
  "registered_at": "2026-03-26T14:00:00Z"
}
```

**Error Responses:** 400 `VALIDATION_ERROR`, 404 `FLEET_NOT_FOUND`, 409 `DRONE_ALREADY_REGISTERED`

---

#### 7.2.7 Remove Drone from Fleet

```
DELETE /api/v1/fleets/{fleet_id}/drones/{drone_id}
```

**Preconditions:** Drone must be `idle` or `offline`.

**Response (204):** No content.

**Error Responses:** 400 `MISSION_CONFLICT` (drone is in flight), 404 `DRONE_NOT_FOUND`

---

#### 7.2.8 Run Preflight Checks

```
POST /api/v1/fleets/{fleet_id}/preflight
```

**Request Body:**

```json
{
  "drone_ids": "string[] | null (null = all drones in fleet)"
}
```

**Response (200):**

```json
{
  "fleet_id": "uuid",
  "results": [
    {
      "drone_id": "uuid",
      "drone_name": "Drone-01",
      "passed": true,
      "checks": {
        "gps_fix": {"passed": true, "detail": "3D fix, hdop=1.2, sats=14"},
        "battery": {"passed": true, "detail": "96%, voltage=16.4V"},
        "ekf": {"passed": true, "detail": "EKF variance within limits"},
        "compass": {"passed": true, "detail": "Calibrated, no interference"},
        "rc_link": {"passed": true, "detail": "RSSI -45dBm"},
        "geofence": {"passed": true, "detail": "Active geofence loaded"},
        "motors": {"passed": true, "detail": "All motors responsive"}
      }
    },
    {
      "drone_id": "uuid",
      "drone_name": "Drone-03",
      "passed": false,
      "checks": {
        "gps_fix": {"passed": false, "detail": "2D fix only, hdop=5.1, sats=4"},
        "battery": {"passed": true, "detail": "94%, voltage=16.3V"},
        "ekf": {"passed": false, "detail": "EKF variance high: 0.8 (limit 0.5)"},
        "compass": {"passed": true, "detail": "Calibrated"},
        "rc_link": {"passed": true, "detail": "RSSI -52dBm"},
        "geofence": {"passed": true, "detail": "Active geofence loaded"},
        "motors": {"passed": true, "detail": "All motors responsive"}
      }
    }
  ],
  "timestamp": "2026-03-26T14:29:00Z"
}
```

**Error Responses:** 404 `FLEET_NOT_FOUND`, 502 `DRONE_COMMS_ERROR`

---

#### 7.2.9 Acquire Command Lock

```
POST /api/v1/fleets/{fleet_id}/lock
```

**Request Body:** None

**Response (200):**

```json
{
  "fleet_id": "uuid",
  "locked_by": "operator-uuid",
  "acquired_at": "2026-03-26T14:30:00Z"
}
```

**Error Responses:** 403 `COMMAND_LOCK_HELD`, 404 `FLEET_NOT_FOUND`

---

#### 7.2.10 Release Command Lock

```
DELETE /api/v1/fleets/{fleet_id}/lock
```

**Response (204):** No content.

**Error Responses:** 403 `INSUFFICIENT_PERMISSIONS` (not the lock holder), 404 `FLEET_NOT_FOUND`

---

### 7.3 Mission Planning

#### 7.3.1 Create Mission

```
POST /api/v1/fleets/{fleet_id}/missions
```

**Request Body:**

```json
{
  "name": "string (1-100 chars, required)",
  "type": "\"waypoint\" | \"survey\" | \"formation_flight\" | \"search_pattern\" (required)",
  "parameters": {
    "altitude": "number (meters AGL, 2-120, required)",
    "speed": "number (m/s, 0.5-15, required)",
    "formation": "FormationType | null",
    "formation_spacing": "number (meters) | null",
    "rtl_on_complete": "boolean (default true)"
  },
  "waypoints": [
    {
      "index": "integer (sequential, starting at 0)",
      "position": "Coordinate (required)",
      "hold_time": "number (seconds at waypoint, default 0)",
      "acceptance_radius": "number (meters, how close to count as reached, default 2)",
      "action": "\"none\" | \"photo\" | \"video_start\" | \"video_stop\" | \"change_formation\" | \"hover\" (default \"none\")",
      "action_params": "object | null"
    }
  ],
  "survey_area": {
    "polygon": "Coordinate[] (for survey missions, the area boundary)",
    "overlap_percent": "number (0-95, for photo surveys)",
    "cross_hatch": "boolean (double-pass survey)"
  } | null,
  "assigned_drones": "string[] | null (drone IDs; null = all drones in fleet)"
}
```

**Response (201):**

```json
{
  "id": "uuid",
  "fleet_id": "uuid",
  "name": "Perimeter Survey",
  "type": "survey",
  "state": "draft",
  "parameters": { "..." },
  "waypoints": [ "..." ],
  "estimated_duration_seconds": 340,
  "estimated_distance_meters": 2400,
  "assigned_drones": ["drone-uuid-1", "drone-uuid-2"],
  "created_at": "2026-03-26T14:30:00Z",
  "updated_at": "2026-03-26T14:30:00Z"
}
```

**Example Request:**

```bash
curl -X POST https://gcs.example.com/api/v1/fleets/f1a2b3c4/missions \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Park Survey",
    "type": "waypoint",
    "parameters": {
      "altitude": 25,
      "speed": 5,
      "formation": "line",
      "formation_spacing": 8,
      "rtl_on_complete": true
    },
    "waypoints": [
      {"index": 0, "position": {"lat": 37.7750, "lon": -122.4180, "alt": 25}, "hold_time": 0},
      {"index": 1, "position": {"lat": 37.7755, "lon": -122.4175, "alt": 25}, "hold_time": 5, "action": "photo"},
      {"index": 2, "position": {"lat": 37.7760, "lon": -122.4180, "alt": 25}, "hold_time": 0}
    ]
  }'
```

**Error Responses:** 400 `VALIDATION_ERROR`, 400 `INVALID_COORDINATES`, 404 `FLEET_NOT_FOUND`

---

#### 7.3.2 List Missions

```
GET /api/v1/fleets/{fleet_id}/missions
```

**Query Parameters:**

| Param   | Type     | Default | Description                          |
|---------|----------|---------|--------------------------------------|
| `page`  | `int`    | 1       | Page number                          |
| `limit` | `int`    | 20      | Items per page                       |
| `state` | `string` | null    | Filter by MissionState               |

**Response (200):**

```json
{
  "missions": [
    {
      "id": "uuid",
      "name": "Park Survey",
      "type": "waypoint",
      "state": "draft",
      "estimated_duration_seconds": 340,
      "assigned_drone_count": 2,
      "created_at": "2026-03-26T14:30:00Z"
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 5, "total_pages": 1 }
}
```

---

#### 7.3.3 Get Mission Details

```
GET /api/v1/fleets/{fleet_id}/missions/{mission_id}
```

**Response (200):** Full mission object (same shape as create response, plus execution data if active/completed).

**Error Responses:** 404 `MISSION_NOT_FOUND`

---

#### 7.3.4 Update Mission

```
PATCH /api/v1/fleets/{fleet_id}/missions/{mission_id}
```

**Preconditions:** Mission must be in `draft` or `validated` state.

**Request Body:** Any subset of the create mission fields.

**Response (200):** Full mission object.

**Error Responses:** 400 `MISSION_CONFLICT` (mission already active), 404 `MISSION_NOT_FOUND`

---

#### 7.3.5 Validate Mission

Dry-run validation: checks waypoints against geofences, verifies drone battery sufficiency, checks airspace constraints.

```
POST /api/v1/fleets/{fleet_id}/missions/{mission_id}/validate
```

**Request Body:** None

**Response (200):**

```json
{
  "mission_id": "uuid",
  "valid": true,
  "warnings": [
    {
      "type": "battery_margin_low",
      "message": "Drone-02 estimated to return with 18% battery (threshold 20%)",
      "drone_id": "uuid"
    }
  ],
  "errors": [],
  "estimated_duration_seconds": 340,
  "estimated_battery_usage_percent": {
    "drone-uuid-1": 62,
    "drone-uuid-2": 68
  }
}
```

**Error Responses:** 404 `MISSION_NOT_FOUND`

---

#### 7.3.6 Start Mission

```
POST /api/v1/fleets/{fleet_id}/missions/{mission_id}/start
```

**Preconditions:** Mission must be in `validated` state. All assigned drones must pass preflight.

**Request Body:** None

**Response (202):**

```json
{
  "command_id": "uuid",
  "mission_id": "uuid",
  "state": "active",
  "started_at": "2026-03-26T14:35:00Z"
}
```

**Error Responses:** 400 `MISSION_CONFLICT`, 403 `COMMAND_LOCK_HELD`, 422 `PREFLIGHT_FAILED`

---

#### 7.3.7 Abort Mission

```
POST /api/v1/fleets/{fleet_id}/missions/{mission_id}/abort
```

**Request Body:**

```json
{
  "action": "\"rtl\" | \"hover\" | \"land_in_place\" (default \"rtl\")"
}
```

**Response (202):**

```json
{
  "command_id": "uuid",
  "mission_id": "uuid",
  "state": "aborted",
  "abort_action": "rtl",
  "timestamp": "2026-03-26T14:40:00Z"
}
```

**Error Responses:** 400 `MISSION_CONFLICT` (no active mission), 403 `COMMAND_LOCK_HELD`

---

#### 7.3.8 Delete Mission

```
DELETE /api/v1/fleets/{fleet_id}/missions/{mission_id}
```

**Preconditions:** Mission must not be in `active` state.

**Response (204):** No content.

**Error Responses:** 400 `MISSION_CONFLICT`, 404 `MISSION_NOT_FOUND`

---

### 7.4 Geofencing

#### 7.4.1 Create Geofence

```
POST /api/v1/fleets/{fleet_id}/geofences
```

**Request Body:**

```json
{
  "name": "string (1-100 chars, required)",
  "type": "\"inclusion\" | \"exclusion\" (required)",
  "geometry": {
    "type": "\"polygon\" | \"circle\" (required)",
    "vertices": "Coordinate[] (required if polygon, min 3 vertices)",
    "center": "Coordinate (required if circle)",
    "radius": "number (meters, required if circle)"
  },
  "altitude_min": "number (meters MSL, optional, default 0)",
  "altitude_max": "number (meters MSL, optional, default 120)",
  "breach_action": "\"rtl\" | \"land\" | \"hover\" | \"report_only\" (default \"rtl\")",
  "enabled": "boolean (default true)"
}
```

**Response (201):**

```json
{
  "id": "uuid",
  "fleet_id": "uuid",
  "name": "Operating Area",
  "type": "inclusion",
  "geometry": { "..." },
  "altitude_min": 0,
  "altitude_max": 120,
  "breach_action": "rtl",
  "enabled": true,
  "created_at": "2026-03-26T14:00:00Z"
}
```

**Example Request:**

```bash
curl -X POST https://gcs.example.com/api/v1/fleets/f1a2b3c4/geofences \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Flight Zone A",
    "type": "inclusion",
    "geometry": {
      "type": "polygon",
      "vertices": [
        {"lat": 37.7740, "lon": -122.4200, "alt": 0},
        {"lat": 37.7760, "lon": -122.4200, "alt": 0},
        {"lat": 37.7760, "lon": -122.4170, "alt": 0},
        {"lat": 37.7740, "lon": -122.4170, "alt": 0}
      ]
    },
    "altitude_max": 50,
    "breach_action": "rtl"
  }'
```

**Error Responses:** 400 `VALIDATION_ERROR`, 404 `FLEET_NOT_FOUND`, 409 `GEOFENCE_OVERLAP`

---

#### 7.4.2 List Geofences

```
GET /api/v1/fleets/{fleet_id}/geofences
```

**Response (200):**

```json
{
  "geofences": [
    {
      "id": "uuid",
      "name": "Flight Zone A",
      "type": "inclusion",
      "geometry": { "..." },
      "enabled": true,
      "breach_action": "rtl"
    }
  ]
}
```

---

#### 7.4.3 Get Geofence

```
GET /api/v1/fleets/{fleet_id}/geofences/{geofence_id}
```

**Response (200):** Full geofence object.

**Error Responses:** 404 `GEOFENCE_NOT_FOUND`

---

#### 7.4.4 Update Geofence

```
PATCH /api/v1/fleets/{fleet_id}/geofences/{geofence_id}
```

**Request Body:** Any subset of create geofence fields.

**Response (200):** Full geofence object.

**Error Responses:** 400 `VALIDATION_ERROR`, 404 `GEOFENCE_NOT_FOUND`, 409 `GEOFENCE_OVERLAP`

---

#### 7.4.5 Delete Geofence

```
DELETE /api/v1/fleets/{fleet_id}/geofences/{geofence_id}
```

**Preconditions:** Geofence should not be the only inclusion zone while a mission is active.

**Response (204):** No content.

**Error Responses:** 400 `MISSION_CONFLICT`, 404 `GEOFENCE_NOT_FOUND`

---

#### 7.4.6 Check Point Against Geofences

Utility endpoint to test whether a coordinate is inside all inclusion zones and outside all exclusion zones.

```
POST /api/v1/fleets/{fleet_id}/geofences/check
```

**Request Body:**

```json
{
  "position": "Coordinate (required)"
}
```

**Response (200):**

```json
{
  "position": {"lat": 37.7750, "lon": -122.4185, "alt": 25},
  "inside_inclusion": true,
  "inside_exclusion": false,
  "allowed": true,
  "nearest_boundary_meters": 42.3,
  "details": [
    {"geofence_id": "uuid", "name": "Flight Zone A", "type": "inclusion", "inside": true},
    {"geofence_id": "uuid", "name": "No-Fly Building", "type": "exclusion", "inside": false}
  ]
}
```

---

### 7.5 Telemetry History

#### 7.5.1 Get Drone Telemetry History

```
GET /api/v1/fleets/{fleet_id}/drones/{drone_id}/telemetry
```

**Query Parameters:**

| Param       | Type     | Default          | Description                           |
|-------------|----------|------------------|---------------------------------------|
| `start`     | `string` | 1 hour ago       | ISO 8601 start time                   |
| `end`       | `string` | now              | ISO 8601 end time                     |
| `interval`  | `string` | `"1s"`           | Downsample interval (`100ms`, `1s`, `5s`, `30s`, `1m`) |
| `fields`    | `string` | all              | Comma-separated field names           |
| `format`    | `string` | `"json"`         | `"json"` or `"csv"`                   |

**Response (200):**

```json
{
  "drone_id": "uuid",
  "start": "2026-03-26T14:00:00Z",
  "end": "2026-03-26T14:30:00Z",
  "interval": "1s",
  "point_count": 1800,
  "fields": ["timestamp", "lat", "lon", "alt", "speed", "heading", "battery_percent", "battery_voltage", "rssi", "gps_hdop", "satellites"],
  "data": [
    {
      "timestamp": "2026-03-26T14:00:00Z",
      "lat": 37.77490,
      "lon": -122.41940,
      "alt": 20.3,
      "speed": 4.8,
      "heading": 92.1,
      "battery_percent": 95,
      "battery_voltage": 16.4,
      "rssi": -48,
      "gps_hdop": 1.1,
      "satellites": 14
    }
  ]
}
```

**Error Responses:** 400 `VALIDATION_ERROR` (invalid time range), 404 `DRONE_NOT_FOUND`

---

#### 7.5.2 Get Fleet Telemetry Summary

Aggregated telemetry for the entire fleet over a time window.

```
GET /api/v1/fleets/{fleet_id}/telemetry/summary
```

**Query Parameters:**

| Param   | Type     | Default    | Description         |
|---------|----------|------------|---------------------|
| `start` | `string` | 1 hour ago | ISO 8601 start time |
| `end`   | `string` | now        | ISO 8601 end time   |

**Response (200):**

```json
{
  "fleet_id": "uuid",
  "period": {
    "start": "2026-03-26T14:00:00Z",
    "end": "2026-03-26T14:30:00Z"
  },
  "drones": [
    {
      "drone_id": "uuid",
      "drone_name": "Drone-01",
      "distance_traveled_meters": 1250.4,
      "max_speed_ms": 6.2,
      "avg_speed_ms": 4.1,
      "max_altitude_m": 25.8,
      "battery_start_percent": 95,
      "battery_end_percent": 71,
      "min_rssi": -62,
      "position_error_avg_m": 0.8,
      "position_error_max_m": 2.1
    }
  ]
}
```

---

#### 7.5.3 Get Flight Path

Returns the position track for a drone, optimized for map rendering.

```
GET /api/v1/fleets/{fleet_id}/drones/{drone_id}/telemetry/path
```

**Query Parameters:**

| Param         | Type     | Default    | Description                                    |
|---------------|----------|------------|------------------------------------------------|
| `start`       | `string` | 1 hour ago | ISO 8601 start time                            |
| `end`         | `string` | now        | ISO 8601 end time                              |
| `simplify`    | `boolean`| true       | Apply Ramer-Douglas-Peucker simplification     |
| `tolerance`   | `number` | 1.0        | Simplification tolerance in meters              |

**Response (200):**

```json
{
  "drone_id": "uuid",
  "point_count": 142,
  "path": [
    {"lat": 37.77490, "lon": -122.41940, "alt": 20.3, "timestamp": "2026-03-26T14:00:00Z"},
    {"lat": 37.77495, "lon": -122.41935, "alt": 20.5, "timestamp": "2026-03-26T14:00:01Z"}
  ]
}
```

---

### 7.6 Replay

#### 7.6.1 List Recorded Sessions

```
GET /api/v1/fleets/{fleet_id}/recordings
```

**Response (200):**

```json
{
  "recordings": [
    {
      "id": "uuid",
      "fleet_id": "uuid",
      "mission_id": "uuid" | null,
      "start_time": "2026-03-25T10:00:00Z",
      "end_time": "2026-03-25T10:15:00Z",
      "duration_seconds": 900,
      "drone_count": 3,
      "event_count": 4520,
      "size_bytes": 2340000
    }
  ]
}
```

---

#### 7.6.2 Get Recording Details

```
GET /api/v1/fleets/{fleet_id}/recordings/{recording_id}
```

**Response (200):**

```json
{
  "id": "uuid",
  "fleet_id": "uuid",
  "mission_id": "uuid",
  "start_time": "2026-03-25T10:00:00Z",
  "end_time": "2026-03-25T10:15:00Z",
  "duration_seconds": 900,
  "drone_count": 3,
  "drones": [
    {"drone_id": "uuid", "drone_name": "Drone-01", "telemetry_points": 1800}
  ],
  "events": [
    {"timestamp": "2026-03-25T10:00:00Z", "type": "mission_start", "detail": "Mission 'Park Survey' started"},
    {"timestamp": "2026-03-25T10:12:30Z", "type": "battery_warning", "drone_id": "uuid", "detail": "Battery at 22%"}
  ],
  "size_bytes": 2340000
}
```

---

#### 7.6.3 Start Replay Session

Creates a server-side replay session that streams recorded telemetry over the WebSocket.

```
POST /api/v1/fleets/{fleet_id}/recordings/{recording_id}/replay
```

**Request Body:**

```json
{
  "speed": "number (0.25-10, playback speed multiplier, default 1.0)",
  "start_offset_seconds": "number (skip into the recording, default 0)"
}
```

**Response (201):**

```json
{
  "replay_session_id": "uuid",
  "recording_id": "uuid",
  "speed": 1.0,
  "state": "playing",
  "current_time": "2026-03-25T10:00:00Z",
  "websocket_channel": "replay:uuid"
}
```

---

#### 7.6.4 Control Replay

```
POST /api/v1/fleets/{fleet_id}/replay/{replay_session_id}/control
```

**Request Body:**

```json
{
  "action": "\"play\" | \"pause\" | \"seek\" | \"set_speed\" | \"stop\" (required)",
  "seek_to": "ISO 8601 (required if action=seek)",
  "speed": "number (required if action=set_speed)"
}
```

**Response (200):**

```json
{
  "replay_session_id": "uuid",
  "state": "playing" | "paused" | "stopped",
  "current_time": "2026-03-25T10:05:30Z",
  "speed": 2.0
}
```

---

### 7.7 Configuration

#### 7.7.1 Get System Configuration

```
GET /api/v1/config
```

**Response (200):**

```json
{
  "telemetry": {
    "stream_rate_hz": 10,
    "history_retention_days": 30,
    "recording_enabled": true
  },
  "safety": {
    "min_battery_percent": 20,
    "max_altitude_m": 120,
    "max_speed_ms": 15,
    "max_distance_from_home_m": 2000,
    "comms_loss_timeout_seconds": 5,
    "comms_loss_action": "rtl",
    "low_battery_action": "rtl",
    "emergency_stop_enabled": true
  },
  "formation": {
    "min_spacing_m": 3,
    "position_hold_tolerance_m": 2.0,
    "heading_tolerance_deg": 10
  },
  "orchestrator": {
    "replan_on_drone_loss": true,
    "replan_timeout_seconds": 5,
    "heartbeat_interval_seconds": 1,
    "command_timeout_seconds": 10
  },
  "network": {
    "mavlink_protocol": "udp",
    "backend_port": 8000,
    "websocket_ping_interval_seconds": 5
  }
}
```

---

#### 7.7.2 Update System Configuration

```
PATCH /api/v1/config
```

**Request Body:** Any subset of the configuration fields (nested merge).

**Response (200):** Full updated configuration object.

**Preconditions:** Requires `admin` role. Some fields (like `max_altitude_m`) cannot be changed while a mission is active.

**Error Responses:** 400 `VALIDATION_ERROR`, 400 `MISSION_CONFLICT`, 403 `INSUFFICIENT_PERMISSIONS`

---

#### 7.7.3 Get Drone Configuration

```
GET /api/v1/fleets/{fleet_id}/drones/{drone_id}/config
```

**Response (200):**

```json
{
  "drone_id": "uuid",
  "parameters": {
    "WPNAV_SPEED": {"value": 500, "unit": "cm/s", "description": "Waypoint navigation speed"},
    "WPNAV_SPEED_UP": {"value": 250, "unit": "cm/s", "description": "Waypoint climb speed"},
    "WPNAV_SPEED_DN": {"value": 150, "unit": "cm/s", "description": "Waypoint descent speed"},
    "RTL_ALT": {"value": 1500, "unit": "cm", "description": "RTL altitude"},
    "FENCE_ENABLE": {"value": 1, "unit": "", "description": "Geofence enable"},
    "BATT_LOW_VOLT": {"value": 14.4, "unit": "V", "description": "Low battery voltage threshold"}
  }
}
```

---

#### 7.7.4 Set Drone Parameters

```
PATCH /api/v1/fleets/{fleet_id}/drones/{drone_id}/config
```

**Request Body:**

```json
{
  "parameters": {
    "WPNAV_SPEED": 600,
    "RTL_ALT": 2000
  }
}
```

**Response (200):**

```json
{
  "drone_id": "uuid",
  "updated_parameters": {
    "WPNAV_SPEED": {"old_value": 500, "new_value": 600},
    "RTL_ALT": {"old_value": 1500, "new_value": 2000}
  },
  "requires_reboot": false
}
```

**Error Responses:** 400 `VALIDATION_ERROR`, 404 `DRONE_NOT_FOUND`, 502 `DRONE_COMMS_ERROR`

---

## 8. WebSocket Protocol

### 8.1 Connection Lifecycle

**Endpoint:** `wss://host/ws/v1/stream?token=<jwt>&fleet_id=<uuid>`

**Handshake:**

1. Client opens WebSocket with token and fleet_id as query parameters.
2. Server validates the JWT and fleet access.
3. On success, server sends a `connection_ack` message.
4. On failure, server closes the connection with an appropriate close code.

**Close Codes:**

| Code | Meaning                        |
|------|--------------------------------|
| 1000 | Normal closure                |
| 4001 | Authentication failed          |
| 4002 | Fleet not found                |
| 4003 | Token expired                  |
| 4004 | Rate limit exceeded            |
| 4005 | Server shutting down           |

**Keepalive:** Server sends a WebSocket ping frame every 5 seconds. Client must respond with a pong. If no pong is received within 15 seconds, the server closes the connection.

**Reconnection:** Clients should implement exponential backoff reconnection: 1s, 2s, 4s, 8s, 16s, max 30s. On reconnect, the server replays any missed critical events (mission state changes, alerts) from the last 60 seconds.

### 8.2 Message Envelope

Every WebSocket message (both directions) follows this envelope format:

```json
{
  "type": "string (message type identifier)",
  "seq": "integer (monotonically increasing sequence number)",
  "timestamp": "ISO 8601",
  "payload": {}
}
```

---

### 8.3 Telemetry Stream

**Direction:** Server -> Client
**Frequency:** 10 Hz per drone (configurable via system config)
**Trigger:** Continuous while any drone in the fleet is online

**Type:** `telemetry`

**Payload Schema:**

```json
{
  "drone_id": "uuid",
  "drone_name": "string",
  "position": {
    "lat": "number",
    "lon": "number",
    "alt": "number (MSL)",
    "alt_relative": "number (AGL)"
  },
  "velocity": {
    "vx": "number (m/s, North)",
    "vy": "number (m/s, East)",
    "vz": "number (m/s, Down)"
  },
  "attitude": {
    "roll": "number (degrees)",
    "pitch": "number (degrees)",
    "yaw": "number (degrees)"
  },
  "speed_ground": "number (m/s)",
  "heading": "number (degrees, 0-360)",
  "battery": {
    "percent": "integer (0-100)",
    "voltage": "number (V)",
    "current": "number (A)",
    "remaining_mah": "integer"
  },
  "gps": {
    "fix_type": "integer (0-6)",
    "satellites": "integer",
    "hdop": "number",
    "vdop": "number"
  },
  "rssi": "integer (dBm)",
  "status": "DroneStatus",
  "armed": "boolean",
  "flight_mode": "string (e.g. 'GUIDED', 'AUTO', 'RTL')",
  "mission_progress": {
    "current_waypoint": "integer",
    "total_waypoints": "integer",
    "distance_to_next_m": "number"
  } | null
}
```

**Example:**

```json
{
  "type": "telemetry",
  "seq": 14523,
  "timestamp": "2026-03-26T14:30:05.100Z",
  "payload": {
    "drone_id": "d1a2b3c4-e5f6-7890-abcd-111111111111",
    "drone_name": "Drone-01",
    "position": {
      "lat": 37.774921,
      "lon": -122.419385,
      "alt": 45.3,
      "alt_relative": 20.1
    },
    "velocity": {"vx": 4.2, "vy": 0.8, "vz": -0.1},
    "attitude": {"roll": 2.1, "pitch": -1.3, "yaw": 91.5},
    "speed_ground": 4.8,
    "heading": 92.1,
    "battery": {
      "percent": 82,
      "voltage": 15.9,
      "current": 12.4,
      "remaining_mah": 3280
    },
    "gps": {"fix_type": 6, "satellites": 14, "hdop": 1.1, "vdop": 1.8},
    "rssi": -48,
    "status": "in_flight",
    "armed": true,
    "flight_mode": "GUIDED",
    "mission_progress": {
      "current_waypoint": 2,
      "total_waypoints": 5,
      "distance_to_next_m": 34.2
    }
  }
}
```

---

### 8.4 Swarm State

**Direction:** Server -> Client
**Frequency:** 2 Hz
**Trigger:** Continuous while fleet has active drones

**Type:** `swarm_state`

**Payload Schema:**

```json
{
  "fleet_id": "uuid",
  "formation": {
    "type": "FormationType",
    "center": "Coordinate",
    "heading": "number",
    "spacing": "number"
  },
  "mission_state": "MissionState | null",
  "mission_id": "uuid | null",
  "drone_count_total": "integer",
  "drone_count_airborne": "integer",
  "drone_count_error": "integer",
  "formation_accuracy": {
    "avg_error_m": "number",
    "max_error_m": "number",
    "within_tolerance": "boolean"
  }
}
```

**Example:**

```json
{
  "type": "swarm_state",
  "seq": 7800,
  "timestamp": "2026-03-26T14:30:05.000Z",
  "payload": {
    "fleet_id": "f1a2b3c4-e5f6-7890-abcd-000000000001",
    "formation": {
      "type": "v_shape",
      "center": {"lat": 37.7750, "lon": -122.4190, "alt": 20},
      "heading": 90,
      "spacing": 10
    },
    "mission_state": "active",
    "mission_id": "m1a2b3c4-0000-0000-0000-000000000001",
    "drone_count_total": 3,
    "drone_count_airborne": 3,
    "drone_count_error": 0,
    "formation_accuracy": {
      "avg_error_m": 0.8,
      "max_error_m": 1.4,
      "within_tolerance": true
    }
  }
}
```

---

### 8.5 Swarm Events

**Direction:** Server -> Client
**Frequency:** On occurrence
**Trigger:** State transitions and significant events

**Type:** `event`

**Payload Schema:**

```json
{
  "event_id": "uuid",
  "event_type": "string (see table below)",
  "severity": "\"info\" | \"warning\" | \"critical\"",
  "source": {
    "type": "\"drone\" | \"fleet\" | \"mission\" | \"system\"",
    "id": "uuid"
  },
  "message": "string",
  "data": "object (event-specific data)"
}
```

**Event Types:**

| Event Type               | Severity   | Description                                      |
|--------------------------|------------|--------------------------------------------------|
| `drone_connected`        | info       | Drone established MAVLink heartbeat              |
| `drone_disconnected`     | critical   | Drone heartbeat lost                             |
| `drone_armed`            | info       | Drone armed                                      |
| `drone_disarmed`         | info       | Drone disarmed                                   |
| `drone_status_changed`   | info       | Drone transitioned to a new status               |
| `mission_started`        | info       | Mission execution began                          |
| `mission_completed`      | info       | Mission completed successfully                   |
| `mission_aborted`        | warning    | Mission was aborted by operator                  |
| `mission_failed`         | critical   | Mission failed due to error                      |
| `waypoint_reached`       | info       | Drone reached a mission waypoint                 |
| `formation_changed`      | info       | Formation type or parameters changed             |
| `formation_degraded`     | warning    | Formation accuracy exceeded tolerance            |
| `replan_triggered`       | warning    | Orchestrator is replanning due to drone loss     |
| `replan_completed`       | info       | New plan computed and being executed             |
| `battery_warning`        | warning    | Battery below warning threshold                  |
| `battery_critical`       | critical   | Battery below critical threshold                 |
| `geofence_warning`       | warning    | Drone approaching geofence boundary              |
| `geofence_breach`        | critical   | Drone crossed geofence boundary                  |
| `comms_degraded`         | warning    | RSSI below threshold                             |
| `comms_lost`             | critical   | No heartbeat from drone                          |
| `failsafe_triggered`     | critical   | A failsafe action was automatically executed     |
| `command_lock_acquired`  | info       | An operator acquired the command lock            |
| `command_lock_released`  | info       | The command lock was released                    |
| `operator_connected`     | info       | A ground station connected                       |
| `operator_disconnected`  | info       | A ground station disconnected                    |

**Example:**

```json
{
  "type": "event",
  "seq": 423,
  "timestamp": "2026-03-26T14:32:15.000Z",
  "payload": {
    "event_id": "e1a2b3c4-0000-0000-0000-000000000001",
    "event_type": "geofence_breach",
    "severity": "critical",
    "source": {"type": "drone", "id": "d1a2b3c4-0000-0000-0000-111111111111"},
    "message": "Drone-02 breached inclusion geofence 'Flight Zone A'. RTL initiated.",
    "data": {
      "drone_name": "Drone-02",
      "geofence_id": "g1a2b3c4-0000-0000-0000-000000000001",
      "geofence_name": "Flight Zone A",
      "breach_position": {"lat": 37.7761, "lon": -122.4201, "alt": 22},
      "action_taken": "rtl"
    }
  }
}
```

---

### 8.6 Alerts

**Direction:** Server -> Client
**Frequency:** On occurrence
**Trigger:** Conditions requiring operator attention

**Type:** `alert`

Alerts differ from events in that they require acknowledgment and persist until resolved.

**Payload Schema:**

```json
{
  "alert_id": "uuid",
  "alert_type": "string",
  "severity": "\"warning\" | \"critical\" | \"emergency\"",
  "message": "string",
  "source": {
    "type": "\"drone\" | \"fleet\" | \"system\"",
    "id": "uuid"
  },
  "requires_ack": "boolean",
  "auto_action": "string | null (action the system will take if not acknowledged)",
  "auto_action_timeout_seconds": "integer | null",
  "data": "object"
}
```

**Alert Types:**

| Alert Type               | Severity    | Auto-Action        | Timeout |
|--------------------------|-------------|--------------------|---------|
| `battery_critical`       | critical    | `rtl`              | 30s     |
| `comms_lost`             | critical    | `rtl`              | 5s      |
| `geofence_imminent`      | warning     | none               | -       |
| `geofence_breach`        | emergency   | `rtl` or `land`    | 0s      |
| `ekf_failure`            | critical    | `land`             | 10s     |
| `gps_lost`               | critical    | `land`             | 10s     |
| `motor_failure`          | emergency   | `land`             | 0s      |
| `collision_warning`      | emergency   | `hover`            | 2s      |
| `weather_warning`        | warning     | none               | -       |

**Example:**

```json
{
  "type": "alert",
  "seq": 85,
  "timestamp": "2026-03-26T14:33:00.000Z",
  "payload": {
    "alert_id": "a1a2b3c4-0000-0000-0000-000000000001",
    "alert_type": "battery_critical",
    "severity": "critical",
    "message": "Drone-01 battery at 18% (critical threshold: 20%). RTL will trigger in 30 seconds if not acknowledged.",
    "source": {"type": "drone", "id": "d1a2b3c4-0000-0000-0000-111111111111"},
    "requires_ack": true,
    "auto_action": "rtl",
    "auto_action_timeout_seconds": 30,
    "data": {
      "drone_name": "Drone-01",
      "battery_percent": 18,
      "battery_voltage": 14.2,
      "estimated_flight_time_seconds": 120,
      "distance_to_home_m": 450
    }
  }
}
```

---

### 8.7 Command Acknowledgments

**Direction:** Server -> Client
**Frequency:** In response to every REST command that targets drones
**Trigger:** When a command is accepted, in progress, completed, or failed

**Type:** `command_ack`

**Payload Schema:**

```json
{
  "command_id": "uuid (matches the command_id from the REST response)",
  "status": "\"accepted\" | \"in_progress\" | \"completed\" | \"failed\" | \"timeout\"",
  "progress_percent": "integer (0-100) | null",
  "drone_statuses": [
    {
      "drone_id": "uuid",
      "drone_name": "string",
      "status": "\"pending\" | \"executing\" | \"completed\" | \"failed\"",
      "detail": "string | null"
    }
  ],
  "error": "string | null"
}
```

**Example -- In Progress:**

```json
{
  "type": "command_ack",
  "seq": 424,
  "timestamp": "2026-03-26T14:30:08.000Z",
  "payload": {
    "command_id": "c1a2b3c4-0000-0000-0000-000000000001",
    "status": "in_progress",
    "progress_percent": 66,
    "drone_statuses": [
      {"drone_id": "d1", "drone_name": "Drone-01", "status": "completed", "detail": "Reached 20m"},
      {"drone_id": "d2", "drone_name": "Drone-02", "status": "completed", "detail": "Reached 20m"},
      {"drone_id": "d3", "drone_name": "Drone-03", "status": "executing", "detail": "Climbing, currently 14m"}
    ],
    "error": null
  }
}
```

**Example -- Failed:**

```json
{
  "type": "command_ack",
  "seq": 426,
  "timestamp": "2026-03-26T14:30:20.000Z",
  "payload": {
    "command_id": "c1a2b3c4-0000-0000-0000-000000000001",
    "status": "failed",
    "progress_percent": 66,
    "drone_statuses": [
      {"drone_id": "d1", "drone_name": "Drone-01", "status": "completed", "detail": null},
      {"drone_id": "d2", "drone_name": "Drone-02", "status": "completed", "detail": null},
      {"drone_id": "d3", "drone_name": "Drone-03", "status": "failed", "detail": "Command timeout after 10s"}
    ],
    "error": "One or more drones failed to complete the command"
  }
}
```

---

### 8.8 Client-to-Server Messages

#### 8.8.1 Alert Acknowledgment

**Direction:** Client -> Server
**Trigger:** Operator acknowledges an alert in the UI

**Type:** `alert_ack`

```json
{
  "type": "alert_ack",
  "seq": 12,
  "timestamp": "2026-03-26T14:33:15.000Z",
  "payload": {
    "alert_id": "uuid",
    "action": "\"acknowledge\" | \"override\" | \"execute_auto_action\"",
    "override_action": "string | null (e.g. 'land' instead of auto 'rtl')"
  }
}
```

**Server responds with a confirmation event.**

---

#### 8.8.2 Telemetry Subscription

**Direction:** Client -> Server
**Trigger:** Client wants to change which data it receives (e.g., reduce bandwidth)

**Type:** `subscribe`

```json
{
  "type": "subscribe",
  "seq": 1,
  "timestamp": "2026-03-26T14:30:00.000Z",
  "payload": {
    "telemetry_rate_hz": "number (1-50, default 10)",
    "drone_ids": "string[] | null (null = all drones)",
    "fields": "string[] | null (null = all fields)",
    "include_events": "boolean (default true)",
    "include_alerts": "boolean (default true)",
    "include_command_acks": "boolean (default true)"
  }
}
```

---

#### 8.8.3 Ping

**Direction:** Client -> Server
**Trigger:** Client measures round-trip latency

**Type:** `ping`

```json
{
  "type": "ping",
  "seq": 100,
  "timestamp": "2026-03-26T14:30:00.000Z",
  "payload": {}
}
```

Server responds with:

**Type:** `pong`

```json
{
  "type": "pong",
  "seq": 100,
  "timestamp": "2026-03-26T14:30:00.005Z",
  "payload": {
    "client_seq": 100,
    "server_time": "2026-03-26T14:30:00.005Z"
  }
}
```

---

### 8.9 Connection Status

**Direction:** Server -> Client
**Frequency:** On connection state change
**Trigger:** Initial connection, reconnection, server status changes

**Type:** `connection_status`

```json
{
  "type": "connection_status",
  "seq": 0,
  "timestamp": "2026-03-26T14:30:00.000Z",
  "payload": {
    "status": "\"connected\" | \"reconnected\" | \"degraded\"",
    "operator_id": "uuid",
    "operator_role": "string",
    "fleet_id": "uuid",
    "connected_operators": "integer",
    "command_lock_holder": "uuid | null",
    "server_version": "string",
    "missed_events": [
      {
        "type": "event",
        "seq": 420,
        "timestamp": "...",
        "payload": { "..." }
      }
    ]
  }
}
```

**Example -- Initial Connection:**

```json
{
  "type": "connection_status",
  "seq": 0,
  "timestamp": "2026-03-26T14:30:00.000Z",
  "payload": {
    "status": "connected",
    "operator_id": "op-uuid-1",
    "operator_role": "pilot",
    "fleet_id": "f1a2b3c4",
    "connected_operators": 2,
    "command_lock_holder": "op-uuid-1",
    "server_version": "1.0.0",
    "missed_events": []
  }
}
```

**Example -- Reconnection with Missed Events:**

```json
{
  "type": "connection_status",
  "seq": 0,
  "timestamp": "2026-03-26T14:30:30.000Z",
  "payload": {
    "status": "reconnected",
    "operator_id": "op-uuid-1",
    "operator_role": "pilot",
    "fleet_id": "f1a2b3c4",
    "connected_operators": 2,
    "command_lock_holder": "op-uuid-1",
    "server_version": "1.0.0",
    "missed_events": [
      {
        "type": "event",
        "seq": 425,
        "timestamp": "2026-03-26T14:30:18.000Z",
        "payload": {
          "event_id": "...",
          "event_type": "waypoint_reached",
          "severity": "info",
          "source": {"type": "drone", "id": "d1"},
          "message": "Drone-01 reached waypoint 3",
          "data": {"waypoint_index": 3}
        }
      }
    ]
  }
}
```

---

## 9. Appendix

### 9.1 Full Endpoint Summary

| Method   | Path                                                        | Description                     | Auth Role        |
|----------|-------------------------------------------------------------|---------------------------------|------------------|
| POST     | `/api/v1/auth/login`                                        | Obtain JWT tokens               | None             |
| POST     | `/api/v1/auth/refresh`                                      | Refresh JWT tokens              | None             |
| GET      | `/api/v1/fleets`                                            | List fleets                     | observer+        |
| POST     | `/api/v1/fleets`                                            | Create fleet                    | admin            |
| GET      | `/api/v1/fleets/{fleet_id}`                                 | Get fleet details               | observer+        |
| PATCH    | `/api/v1/fleets/{fleet_id}`                                 | Update fleet                    | admin            |
| DELETE   | `/api/v1/fleets/{fleet_id}`                                 | Delete fleet                    | admin            |
| POST     | `/api/v1/fleets/{fleet_id}/drones`                          | Register drone                  | admin            |
| DELETE   | `/api/v1/fleets/{fleet_id}/drones/{drone_id}`               | Remove drone                    | admin            |
| POST     | `/api/v1/fleets/{fleet_id}/preflight`                       | Run preflight checks            | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/lock`                            | Acquire command lock            | pilot+           |
| DELETE   | `/api/v1/fleets/{fleet_id}/lock`                            | Release command lock            | pilot+ (holder)  |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/arm`                       | Arm all drones                  | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/takeoff`                   | Takeoff                         | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/land`                      | Land                            | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/rtl`                       | Return to launch                | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/emergency-land`            | Emergency land (controlled)     | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/emergency-kill`            | Emergency kill (force disarm)   | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/formation`                 | Set formation                   | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/goto`                      | Go to waypoint                  | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/pause`                     | Pause swarm                     | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/swarm/resume`                    | Resume swarm                    | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/missions`                        | Create mission                  | pilot+           |
| GET      | `/api/v1/fleets/{fleet_id}/missions`                        | List missions                   | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/missions/{mission_id}`           | Get mission details             | observer+        |
| PATCH    | `/api/v1/fleets/{fleet_id}/missions/{mission_id}`           | Update mission                  | pilot+           |
| DELETE   | `/api/v1/fleets/{fleet_id}/missions/{mission_id}`           | Delete mission                  | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/missions/{mission_id}/validate`  | Validate mission                | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/missions/{mission_id}/start`     | Start mission                   | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/missions/{mission_id}/abort`     | Abort mission                   | pilot+ (lock)    |
| POST     | `/api/v1/fleets/{fleet_id}/geofences`                       | Create geofence                 | pilot+           |
| GET      | `/api/v1/fleets/{fleet_id}/geofences`                       | List geofences                  | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/geofences/{geofence_id}`         | Get geofence                    | observer+        |
| PATCH    | `/api/v1/fleets/{fleet_id}/geofences/{geofence_id}`         | Update geofence                 | pilot+           |
| DELETE   | `/api/v1/fleets/{fleet_id}/geofences/{geofence_id}`         | Delete geofence                 | pilot+           |
| POST     | `/api/v1/fleets/{fleet_id}/geofences/check`                 | Check point in geofences        | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/drones/{drone_id}/telemetry`     | Get telemetry history           | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/telemetry/summary`               | Get fleet telemetry summary     | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/drones/{drone_id}/telemetry/path`| Get flight path                 | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/recordings`                      | List recordings                 | observer+        |
| GET      | `/api/v1/fleets/{fleet_id}/recordings/{recording_id}`       | Get recording details           | observer+        |
| POST     | `/api/v1/fleets/{fleet_id}/recordings/{recording_id}/replay`| Start replay session            | observer+        |
| POST     | `/api/v1/fleets/{fleet_id}/replay/{replay_session_id}/control` | Control replay               | observer+        |
| GET      | `/api/v1/config`                                            | Get system configuration        | observer+        |
| PATCH    | `/api/v1/config`                                            | Update system configuration     | admin            |
| GET      | `/api/v1/fleets/{fleet_id}/drones/{drone_id}/config`        | Get drone configuration         | observer+        |
| PATCH    | `/api/v1/fleets/{fleet_id}/drones/{drone_id}/config`        | Set drone parameters            | admin            |

### 9.2 WebSocket Message Summary

| Type                | Direction         | Frequency        | Description                          |
|---------------------|-------------------|------------------|--------------------------------------|
| `telemetry`         | Server -> Client  | 10 Hz per drone  | Real-time drone state                |
| `swarm_state`       | Server -> Client  | 2 Hz             | Aggregate swarm status               |
| `event`             | Server -> Client  | On occurrence     | State transitions and events         |
| `alert`             | Server -> Client  | On occurrence     | Conditions requiring attention       |
| `command_ack`       | Server -> Client  | On command update | Command execution progress           |
| `connection_status` | Server -> Client  | On state change   | Connection and session info          |
| `pong`              | Server -> Client  | On ping           | Latency measurement response         |
| `alert_ack`         | Client -> Server  | On user action    | Acknowledge or override an alert     |
| `subscribe`         | Client -> Server  | On user action    | Change telemetry subscription        |
| `ping`              | Client -> Server  | Periodic          | Latency measurement request          |

---

## Related Documents

- [[UI_DESIGN]] -- Ground station UI that consumes these API endpoints
- [[SYSTEM_ARCHITECTURE]] -- Backend architecture implementing this API
- [[COMMS_PROTOCOL]] -- MAVLink protocol underlying swarm commands
- [[INTEGRATION_AUDIT]] -- API-to-UI alignment audit results
- [[DECISION_LOG]] -- Key API design decisions
