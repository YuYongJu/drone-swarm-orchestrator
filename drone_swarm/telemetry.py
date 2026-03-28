"""
Telemetry reader and aggregator.

Extracted from the SwarmOrchestrator's telemetry methods to keep the swarm
module focused on orchestration. Provides synchronous telemetry reading
(designed to run in a thread executor) and an async telemetry loop.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .collision import CollisionAvoidance
from .drone import Drone, DroneStatus
from .geofence import Geofence, GeofenceStatus
from .health import compute_health_score

logger = logging.getLogger("drone_swarm.telemetry")

if TYPE_CHECKING:
    from .swarm import SwarmOrchestrator


def read_telemetry(drone: Drone) -> None:
    """
    Synchronous telemetry reader for a single drone.

    Drains up to 50 buffered MAVLink messages per call, updating the
    drone's position, heading, battery, and heartbeat timestamp.

    Designed to be called from ``asyncio.loop.run_in_executor()`` so it
    does not block the event loop on serial I/O.
    """
    conn = drone.connection
    if conn is None:
        return
    try:
        for _ in range(50):
            msg = conn.recv_match(blocking=False)
            if msg is None:
                break
            msg_type = msg.get_type()
            if msg_type == "HEARTBEAT":
                drone.last_heartbeat = time.time()
                # Track armed state from heartbeat base_mode flag
                drone._armed_from_heartbeat = bool(
                    msg.base_mode & 0x80  # MAV_MODE_FLAG_SAFETY_ARMED
                )
            elif msg_type == "GLOBAL_POSITION_INT":
                drone.lat = msg.lat / 1e7
                drone.lon = msg.lon / 1e7
                drone.alt = msg.relative_alt / 1000.0
                drone.heading = msg.hdg / 100.0
            elif msg_type == "SYS_STATUS":
                if msg.battery_remaining >= 0:
                    drone.battery_pct = msg.battery_remaining
                # Track communication quality from drop_rate_comm (0-10000 = 0%-100%)
                if hasattr(msg, "drop_rate_comm"):
                    drone.message_loss_rate = msg.drop_rate_comm / 10000.0
                # Extract voltage (mV -> V) and current (cA -> A)
                if hasattr(msg, "voltage_battery") and msg.voltage_battery > 0:
                    drone.voltage = msg.voltage_battery / 1000.0
                if hasattr(msg, "current_battery") and msg.current_battery >= 0:
                    drone.current_a = msg.current_battery / 100.0
            elif msg_type == "GPS_RAW_INT":
                if hasattr(msg, "satellites_visible"):
                    drone.gps_satellite_count = msg.satellites_visible
            elif msg_type == "ATTITUDE":
                drone.roll = msg.roll
                drone.pitch = msg.pitch
                drone.yaw = msg.yaw
            elif msg_type == "VIBRATION":
                vx = getattr(msg, "vibration_x", 0.0)
                vy = getattr(msg, "vibration_y", 0.0)
                vz = getattr(msg, "vibration_z", 0.0)
                drone.vibration_level = max(vx, vy, vz)
    except Exception:
        logger.debug("Telemetry read error for '%s'", drone.drone_id, exc_info=True)


async def telemetry_loop(orchestrator: "SwarmOrchestrator") -> None:
    """
    Async coroutine that continuously reads telemetry from all drones.

    Handles heartbeat-timeout detection (marks drones as LOST) and
    auto-RTL on low battery. Yields control via ``asyncio.sleep`` so
    other coroutines run freely.
    """
    loop = asyncio.get_running_loop()
    while orchestrator._running:
        for drone in list(orchestrator.drones.values()):
            if drone.connection is None:
                continue

            await loop.run_in_executor(None, read_telemetry, drone)

            # Heartbeat timeout -- only in-flight drones can go LOST
            in_flight = (DroneStatus.AIRBORNE, DroneStatus.RETURNING, DroneStatus.LANDING)
            if (
                time.time() - drone.last_heartbeat > orchestrator.HEARTBEAT_TIMEOUT
                and drone.status in in_flight
            ):
                transitioned = await orchestrator._transition(
                    drone.drone_id, DroneStatus.LOST
                )
                if transitioned:
                    logger.error("LOST contact with '%s'!", drone.drone_id)
                    orchestrator.replan_on_loss(drone.drone_id)

            # Auto-RTL on low battery (skip 0% -- SITL artefact)
            if (
                0 < drone.battery_pct < orchestrator.BATTERY_RTL_THRESHOLD
                and drone.status == DroneStatus.AIRBORNE
                and drone.takeoff_time > 0
                and time.time() - drone.takeoff_time > orchestrator.BATTERY_CHECK_GRACE_PERIOD
            ):
                logger.warning("Low battery on '%s' (%.0f%%) -- RTL",
                               drone.drone_id, drone.battery_pct)
                await orchestrator.return_to_launch(drone.drone_id)

            # -- Health score update -------------------------------------------
            drone.health_score = compute_health_score(drone)
            if drone.health_score < 25:
                logger.error(
                    "CRITICAL health on '%s': score=%.1f",
                    drone.drone_id, drone.health_score,
                )
            elif drone.health_score < 50:
                logger.warning(
                    "Low health on '%s': score=%.1f",
                    drone.drone_id, drone.health_score,
                )

        # -- Geofence enforcement hook -----------------------------------------
        geofence: Geofence | None = getattr(orchestrator, "_geofence", None)
        geofence_action: str = getattr(orchestrator, "_geofence_action", "warn")
        if geofence is not None:
            airborne_drones = [
                d for d in orchestrator.drones.values()
                if d.status == DroneStatus.AIRBORNE
            ]
            for drone in airborne_drones:
                gf_status = geofence.check_drone(drone)
                if gf_status == GeofenceStatus.BREACH:
                    logger.error(
                        "GEOFENCE BREACH: '%s' at (%.6f, %.6f, %.1fm)",
                        drone.drone_id, drone.lat, drone.lon, drone.alt,
                    )
                    if geofence_action == "rtl":
                        try:
                            await orchestrator.return_to_launch(drone.drone_id)
                        except Exception:
                            logger.debug(
                                "Geofence RTL failed for '%s'",
                                drone.drone_id, exc_info=True,
                            )
                    elif geofence_action == "land":
                        try:
                            await orchestrator.land(drone.drone_id)
                        except Exception:
                            logger.debug(
                                "Geofence LAND failed for '%s'",
                                drone.drone_id, exc_info=True,
                            )
                    # "warn" action just logs (already done above)
                elif gf_status == GeofenceStatus.WARNING:
                    logger.warning(
                        "GEOFENCE WARNING: '%s' near boundary at (%.6f, %.6f, %.1fm)",
                        drone.drone_id, drone.lat, drone.lon, drone.alt,
                    )

        # -- Collision avoidance hook ------------------------------------------
        ca: CollisionAvoidance | None = getattr(orchestrator, "_collision_avoidance", None)
        if ca is not None:
            airborne = {
                did: d
                for did, d in orchestrator.drones.items()
                if d.status == DroneStatus.AIRBORNE
            }
            # Log any risks for monitoring
            risks = ca.check_all_pairs(airborne)
            for risk in risks:
                logger.warning(
                    "COLLISION RISK: '%s' <-> '%s' distance %.1fm (min %.1fm)",
                    risk.drone_a_id,
                    risk.drone_b_id,
                    risk.distance_m,
                    risk.min_distance_m,
                )

            # Use whole-swarm ORCA to compute globally safe velocities
            # (one goto per drone, not per-pair — avoids conflicting commands)
            override_until = time.time() + ca.dt
            if risks and ca.method == "orca" and len(airborne) >= 2:
                orca_results = ca.compute_orca_velocities(airborne)
                for orca_vel in orca_results:
                    did = orca_vel.drone_id
                    if did not in airborne:
                        continue
                    drone_obj = airborne[did]
                    if abs(orca_vel.vn) > 1e-6 or abs(orca_vel.ve) > 1e-6:
                        try:
                            from .collision import _offset_gps
                            wp = _offset_gps(
                                drone_obj.lat, drone_obj.lon, drone_obj.alt,
                                orca_vel.vn * ca.dt, orca_vel.ve * ca.dt,
                            )
                            drone_obj._collision_override_until = override_until
                            await orchestrator.goto(did, wp)
                        except Exception:
                            logger.debug(
                                "ORCA goto failed for '%s'",
                                did, exc_info=True,
                            )
            elif risks and ca.method == "repulsive":
                # Fallback: per-pair repulsive avoidance
                for risk in risks:
                    drone_a = orchestrator.drones[risk.drone_a_id]
                    drone_b = orchestrator.drones[risk.drone_b_id]
                    wp_a, wp_b = ca.compute_avoidance(
                        drone_a, drone_b, ca.min_distance_m,
                    )
                    try:
                        drone_a._collision_override_until = override_until
                        drone_b._collision_override_until = override_until
                        await orchestrator.goto(risk.drone_a_id, wp_a)
                        await orchestrator.goto(risk.drone_b_id, wp_b)
                    except Exception:
                        logger.debug(
                            "Avoidance goto failed for '%s'/'%s'",
                            risk.drone_a_id, risk.drone_b_id,
                            exc_info=True,
                        )

        # -- Formation hold correction hook ------------------------------------
        fc = getattr(orchestrator, "_formation_controller", None)
        leader_id = getattr(orchestrator, "_formation_leader_id", None)
        if fc is not None and leader_id is not None:
            leader = orchestrator.drones.get(leader_id)
            if leader is not None and leader.status == DroneStatus.AIRBORNE:
                followers = {
                    did: d
                    for did, d in orchestrator.drones.items()
                    if did != leader_id and d.status == DroneStatus.AIRBORNE
                }
                if followers:
                    corrections = fc.compute_corrections(leader, followers)
                    for drone_id, wp in corrections.items():
                        try:
                            await orchestrator.goto(drone_id, wp)
                        except Exception:
                            logger.debug(
                                "Formation hold goto failed for '%s'",
                                drone_id, exc_info=True,
                            )

        # -- Anomaly detection hook ---------------------------------------------
        anomaly_det = getattr(orchestrator, "_anomaly_detector", None)
        if anomaly_det is not None:
            for drone in orchestrator.drones.values():
                metrics = {
                    "battery_pct": drone.battery_pct,
                    "lat": drone.lat,
                    "lon": drone.lon,
                    "alt": drone.alt,
                    "vibration_level": drone.vibration_level,
                    "message_loss_rate": drone.message_loss_rate,
                }
                anomaly_det.update(drone.drone_id, metrics)
                for anomaly in anomaly_det.check_individual(drone.drone_id):
                    if anomaly.severity >= 0.5:
                        logger.warning(
                            "ANOMALY [%s] %s: %s (severity=%.2f)",
                            anomaly.drone_id, anomaly.anomaly_type,
                            anomaly.message, anomaly.severity,
                        )
                    else:
                        logger.info(
                            "ANOMALY [%s] %s: %s (severity=%.2f)",
                            anomaly.drone_id, anomaly.anomaly_type,
                            anomaly.message, anomaly.severity,
                        )
            # Swarm-level comparison
            swarm_anomalies = anomaly_det.check_swarm(orchestrator.drones)
            for anomaly in swarm_anomalies:
                logger.warning(
                    "SWARM ANOMALY [%s] %s: %s (severity=%.2f)",
                    anomaly.drone_id, anomaly.anomaly_type,
                    anomaly.message, anomaly.severity,
                )

        await asyncio.sleep(0.1)
