"""
dso -- CLI for the drone-swarm SDK.

Commands:
    dso version                       Print version
    dso simulate --drones N           Launch N SITL instances
    dso status --connection <conn>    Print drone status
    dso preflight --connection <conn> Run preflight checks
    dso init                          Create swarm.yaml template
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from ._version import __version__

# ---------------------------------------------------------------------------
# ANSI colour helpers (only when stdout is a TTY)
# ---------------------------------------------------------------------------

_USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m" if _USE_COLOR else text


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m" if _USE_COLOR else text


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m" if _USE_COLOR else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _USE_COLOR else text


# ---------------------------------------------------------------------------
# swarm.yaml template
# ---------------------------------------------------------------------------

_SWARM_YAML_TEMPLATE = """\
# drone-swarm configuration file
# Docs: https://github.com/yuyongju/drone-swarm-orchestrator#readme

swarm:
  # -- Telemetry thresholds --
  heartbeat_timeout_s: 15.0
  battery_rtl_threshold_pct: 20.0

  # -- Preflight check thresholds --
  preflight_min_battery_pct: 80.0
  preflight_min_satellites: 6
  preflight_vibration_threshold: 30.0

  # -- Mission defaults --
  default_altitude_m: 10.0
  waypoint_reach_threshold_m: 2.0

  # -- Simulation --
  sitl_speedup: 1

# Drone fleet (used by swarm orchestrator)
drones:
  - id: alpha
    connection: udp:127.0.0.1:14550
    role: RECON
  - id: bravo
    connection: udp:127.0.0.1:14560
    role: RELAY
"""


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_version(args: argparse.Namespace) -> int:
    """Print the SDK version."""
    print(f"dso {__version__}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Create a swarm.yaml template in the current directory."""
    target = Path.cwd() / "swarm.yaml"
    if target.exists() and not getattr(args, "force", False):
        print(_yellow(f"swarm.yaml already exists in {Path.cwd()}"))
        print("Use --force to overwrite.")
        return 1
    target.write_text(_SWARM_YAML_TEMPLATE, encoding="utf-8")
    print(_green(f"Created {target}"))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Launch N SITL instances and keep running until Ctrl+C."""
    from .simulation import SimulationHarness

    num = args.drones
    speedup = args.speedup
    visualize = getattr(args, "visualize", False)

    print(_bold(f"Launching {num} SITL drone(s) (speedup={speedup})..."))

    harness = SimulationHarness(n_drones=num, speedup=speedup)

    async def _run() -> None:
        await harness.start()
        print()
        print(_green("All SITL instances running:"))
        for inst in harness.instances:
            print(f"  Drone {inst.sysid}: {_bold(inst.connection_string)}")
        print()

        map_stop = None
        if visualize:
            from .swarm import SwarmOrchestrator
            from .viz import start_map_server

            swarm = SwarmOrchestrator()
            for inst in harness.instances:
                swarm.register_drone(
                    f"sim-{inst.sysid}", inst.connection_string,
                )
            await swarm.connect_all()
            map_stop = await start_map_server(swarm, port=8080, open_browser=True)
            print(_green("Map visualization: http://localhost:8080"))
            print()

        print("Press Ctrl+C to stop all instances.")

        # Wait forever until interrupted
        stop_event = asyncio.Event()

        def _on_signal() -> None:
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _on_signal)
            except NotImplementedError:
                pass

        try:
            await stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            print()
            print("Shutting down...")
            if map_stop:
                map_stop()
            await harness.stop()
            print(_green("All instances stopped."))

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        asyncio.run(harness.stop())
        print(_green("\nAll instances stopped."))

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Connect to a drone and print its status."""
    try:
        from pymavlink import mavutil
    except ImportError:
        print(_red("pymavlink is required. Install with: pip install pymavlink"))
        return 1

    conn_str = args.connection
    print(f"Connecting to {_bold(conn_str)}...")

    try:
        conn = mavutil.mavlink_connection(conn_str, baud=57600)
        conn.wait_heartbeat(timeout=10)
    except Exception as e:
        print(_red(f"Connection failed: {e}"))
        return 1

    print(_green("Connected."))
    print()

    # Mode and armed state
    mode = conn.flightmode
    armed = bool(conn.motors_armed())
    print(f"  Mode:   {_bold(mode)}")
    print(f"  Armed:  {_green('YES') if armed else _yellow('NO')}")

    # GPS
    gps = conn.recv_match(type="GPS_RAW_INT", blocking=True, timeout=5)
    if gps:
        fix_names = {
            0: "No GPS", 1: "No Fix", 2: "2D", 3: "3D",
            4: "DGPS", 5: "RTK Float", 6: "RTK Fixed",
        }
        fix_str = fix_names.get(gps.fix_type, f"Unknown({gps.fix_type})")
        print(f"  GPS:    {fix_str}, {gps.satellites_visible} sats")
        lat = gps.lat / 1e7
        lon = gps.lon / 1e7
        print(f"  Pos:    {lat:.7f}, {lon:.7f}")
    else:
        print(f"  GPS:    {_yellow('No data')}")

    # Battery
    bat = conn.recv_match(type="SYS_STATUS", blocking=True, timeout=5)
    if bat:
        pct = bat.battery_remaining
        volts = bat.voltage_battery / 1000.0
        pct_str = f"{pct}%" if pct >= 0 else "N/A"
        color = _green if pct >= 50 else (_yellow if pct >= 20 else _red)
        print(f"  Battery: {color(pct_str)} ({volts:.2f}V)")
    else:
        print(f"  Battery: {_yellow('No data')}")

    conn.close()
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    """Run preflight checks on a single drone."""
    try:
        from pymavlink import mavutil  # noqa: F401
    except ImportError:
        print(_red("pymavlink is required. Install with: pip install pymavlink"))
        return 1

    from .safety import preflight_ok, run_preflight_checks

    conn_str = args.connection
    drone_id = args.id
    print(f"Running preflight checks on {_bold(drone_id)} ({conn_str})...")
    print()

    try:
        results = run_preflight_checks(conn_str, drone_id)
    except Exception as e:
        print(_red(f"Preflight failed: {e}"))
        return 1

    for r in results:
        icon = _green("PASS") if r.passed else _red("FAIL")
        print(f"  [{icon}] {r.check:12s}  {r.detail}")

    print()
    if preflight_ok(results):
        print(_green("All preflight checks passed."))
        return 0
    else:
        failed = sum(1 for r in results if not r.passed)
        print(_red(f"{failed} check(s) failed. Resolve issues before flight."))
        return 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="dso",
        description="drone-swarm orchestrator CLI",
    )
    parser.add_argument(
        "--version", action="version", version=f"dso {__version__}",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- version ---------------------------------------------------------------
    sub.add_parser("version", help="Print version")

    # -- init ------------------------------------------------------------------
    p_init = sub.add_parser("init", help="Create a swarm.yaml config template")
    p_init.add_argument(
        "--force", action="store_true", help="Overwrite existing swarm.yaml",
    )

    # -- simulate --------------------------------------------------------------
    p_sim = sub.add_parser("simulate", help="Launch SITL drone simulation")
    p_sim.add_argument(
        "--drones", "-n", type=int, default=3,
        help="Number of simulated drones (default: 3)",
    )
    p_sim.add_argument(
        "--speedup", "-s", type=int, default=1,
        help="SITL speedup factor (default: 1)",
    )
    p_sim.add_argument(
        "--visualize", "-v", action="store_true", default=False,
        help="Open a live map in the browser showing drone positions",
    )

    # -- status ----------------------------------------------------------------
    p_status = sub.add_parser("status", help="Print drone status")
    p_status.add_argument(
        "--connection", "-c", required=True,
        help="MAVLink connection string (e.g. tcp:127.0.0.1:5760)",
    )

    # -- preflight -------------------------------------------------------------
    p_pre = sub.add_parser("preflight", help="Run preflight checks")
    p_pre.add_argument(
        "--connection", "-c", required=True,
        help="MAVLink connection string (e.g. tcp:127.0.0.1:5760)",
    )
    p_pre.add_argument(
        "--id", default="drone-1",
        help="Drone identifier for reporting (default: drone-1)",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "version": cmd_version,
    "init": cmd_init,
    "simulate": cmd_simulate,
    "status": cmd_status,
    "preflight": cmd_preflight,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
