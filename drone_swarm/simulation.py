"""
SITL multi-drone simulation harness.

Provides helpers to launch multiple ArduPilot SITL (Software-In-The-Loop)
instances for testing swarm logic without any hardware.

Usage::

    # Context-manager style (recommended)
    async with SimulationHarness(n_drones=3) as sim:
        swarm = Swarm()
        for inst in sim.instances:
            swarm.add(f"sim-{inst.sysid - 1}", inst.connection_string)
        await swarm.connect()

    # One-liner factory
    swarm, sim = await Swarm.simulate(n_drones=3)
    # ... fly ...
    await sim.stop()

Requires ``arducopter`` SITL binary and ``mavproxy.py``.  On Windows the
harness runs both through WSL automatically.

Connection flow (per drone)::

    SDK  -->  udp:127.0.0.1:{mavproxy_port}
                    |
               MAVProxy (--daemon)
                    |
         tcp:127.0.0.1:{tcp_port}
                    |
            ArduCopter SITL

See https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html
"""

from __future__ import annotations

import asyncio
import logging
import platform
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SITLNotFoundError(RuntimeError):
    """Raised when the ArduPilot SITL binary cannot be located."""

    def __init__(self, searched: list[str] | None = None):
        locations = ""
        if searched:
            locations = "\n  Searched: " + ", ".join(searched)
        super().__init__(
            "ArduPilot SITL (arducopter) not found.\n"
            "  Install it: https://ardupilot.org/dev/docs/building-setup-linux.html"
            + locations
        )


class MAVProxyNotFoundError(RuntimeError):
    """Raised when ``mavproxy.py`` cannot be located."""

    def __init__(self) -> None:
        super().__init__(
            "MAVProxy not found.\n"
            "  MAVProxy is required to provide simulated RC input to SITL.\n"
            "  Install it:  pip install MAVProxy   (or inside WSL on Windows)\n"
            "  Docs: https://ardupilot.org/mavproxy/"
        )


class SITLStartupError(RuntimeError):
    """Raised when a SITL instance fails to become ready."""


# ---------------------------------------------------------------------------
# SITLInstance dataclass
# ---------------------------------------------------------------------------

@dataclass
class SITLInstance:
    """Tracks a single SITL ArduCopter process and its MAVProxy sidecar."""

    sysid: int
    tcp_port: int
    mavproxy_port: int
    home_lat: float
    home_lon: float
    home_alt: float = 0.0
    home_heading: float = 0.0
    process: subprocess.Popen | None = field(default=None, repr=False)
    mavproxy_process: subprocess.Popen | None = field(default=None, repr=False)

    @property
    def connection_string(self) -> str:
        """MAVLink connection string for this instance (via MAVProxy UDP)."""
        return f"udp:127.0.0.1:{self.mavproxy_port}"


# ---------------------------------------------------------------------------
# SimulationHarness
# ---------------------------------------------------------------------------

class SimulationHarness:
    """
    Launch and manage multiple ArduPilot SITL instances with MAVProxy.

    Works on Linux natively and on Windows via WSL.  Each SITL instance gets a
    unique ``sysid`` and a TCP port separated by ``port_step`` (default 10).
    A MAVProxy daemon bridges each SITL TCP port to a UDP port that the SDK
    connects to.

    Parameters
    ----------
    n_drones:
        Number of ArduCopter instances to launch.
    sitl_path:
        Explicit path to the ``arducopter`` binary.  Detected automatically if
        omitted.
    base_port:
        TCP port for the first instance.  Subsequent instances use
        ``base_port + i * port_step``.
    port_step:
        Port increment between instances.
    mavproxy_base_port:
        UDP port for the first MAVProxy output.  Subsequent instances use
        ``mavproxy_base_port + i * port_step``.
    home:
        ``(lat, lon)`` home position for the first drone.
    home_alt:
        Home altitude in meters.
    spacing_m:
        Meters between drones along latitude.
    speedup:
        SITL clock speed multiplier (1 = real-time).
    startup_timeout:
        Seconds to wait for each instance TCP port to become reachable.
    mavproxy_settle_s:
        Seconds to wait after launching MAVProxy for it to connect to SITL.
    wipe:
        Pass ``--wipe`` on the first instance to reset parameters.
    """

    SITL_BINARY = "arducopter"
    MAVPROXY_BINARY = "mavproxy.py"

    # Common locations for the SITL binary (Linux / WSL paths)
    _COMMON_PATHS: list[str] = [
        str(Path.home() / "ardupilot" / "build" / "sitl" / "bin" / "arducopter"),
        "/usr/local/bin/arducopter",
    ]

    # When running on Windows, the WSL-side home is typically /home/<user>
    _WSL_PATHS: list[str] = [
        "/root/ardupilot/build/sitl/bin/arducopter",
    ]

    # Default offset from SITL base_port to MAVProxy UDP base_port
    _MAVPROXY_PORT_OFFSET = 4000

    def __init__(
        self,
        n_drones: int = 3,
        *,
        sitl_path: str | None = None,
        base_port: int = 5760,
        port_step: int = 10,
        mavproxy_base_port: int | None = None,
        home: tuple[float, float] = (35.363261, -117.669056),
        home_alt: float = 0.0,
        spacing_m: float = 5.0,
        speedup: int = 1,
        startup_timeout: float = 30.0,
        mavproxy_settle_s: float = 3.0,
        wipe: bool = True,
    ):
        self.n_drones = n_drones
        self.base_port = base_port
        self.port_step = port_step
        self.mavproxy_base_port = (
            mavproxy_base_port
            if mavproxy_base_port is not None
            else base_port + self._MAVPROXY_PORT_OFFSET
        )
        self.home = home
        self.home_alt = home_alt
        self.spacing_m = spacing_m
        self.speedup = speedup
        self.startup_timeout = startup_timeout
        self.mavproxy_settle_s = mavproxy_settle_s
        self.wipe = wipe
        self.instances: list[SITLInstance] = []
        self._use_wsl = self._should_use_wsl()

        # Resolve SITL binary path (raises SITLNotFoundError if missing)
        self.sitl_path = sitl_path or self._find_sitl()

        # Verify MAVProxy is available (raises MAVProxyNotFoundError if missing)
        self._find_mavproxy()

    # -- Async context manager ------------------------------------------------

    async def __aenter__(self) -> SimulationHarness:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.stop()

    # -- Public API -----------------------------------------------------------

    async def start(self) -> list[SITLInstance]:
        """
        Launch all SITL instances with MAVProxy sidecars and wait until ready.

        Returns the list of :class:`SITLInstance` objects with populated
        ``connection_string`` attributes (UDP via MAVProxy).
        """
        for i in range(self.n_drones):
            sysid = i + 1
            tcp_port = self.base_port + i * self.port_step
            mavproxy_port = self.mavproxy_base_port + i * self.port_step
            lat = self.home[0] + (i * self.spacing_m / 111_320.0)
            lon = self.home[1]

            instance = SITLInstance(
                sysid=sysid,
                tcp_port=tcp_port,
                mavproxy_port=mavproxy_port,
                home_lat=lat,
                home_lon=lon,
                home_alt=self.home_alt,
            )

            cmd = self._build_command(instance, wipe=(self.wipe and i == 0))
            logger.info(
                "Launching SITL sysid=%d on port %d: %s",
                sysid, tcp_port, " ".join(cmd),
            )

            instance.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.instances.append(instance)
            logger.info(
                "[SIM] Launched SITL sysid=%d on port %d (pid=%d)",
                sysid, tcp_port, instance.process.pid,
            )

        # Wait for every SITL instance to become reachable on TCP
        try:
            await self._wait_for_all_ready()
        except Exception:
            # If any instance fails to start, kill everything
            await self.stop()
            raise

        # Now launch a MAVProxy daemon for each instance
        for inst in self.instances:
            mavproxy_cmd = self._build_mavproxy_command(inst)
            logger.info(
                "[SIM] Launching MAVProxy for sysid=%d: "
                "tcp:%d -> udp:%d: %s",
                inst.sysid, inst.tcp_port, inst.mavproxy_port,
                " ".join(mavproxy_cmd),
            )
            inst.mavproxy_process = subprocess.Popen(
                mavproxy_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(
                "[SIM] MAVProxy sysid=%d started (pid=%d)",
                inst.sysid, inst.mavproxy_process.pid,
            )

        # Give MAVProxy time to connect to each SITL instance
        if self.mavproxy_settle_s > 0:
            logger.info(
                "[SIM] Waiting %.1fs for MAVProxy to settle...",
                self.mavproxy_settle_s,
            )
            await asyncio.sleep(self.mavproxy_settle_s)

        return self.instances

    async def stop(self) -> None:
        """Terminate all running SITL and MAVProxy processes and clean up."""
        for inst in self.instances:
            # Stop MAVProxy first
            self._kill_process(inst.mavproxy_process, "MAVProxy", inst.sysid)
            inst.mavproxy_process = None

            # Then stop SITL
            self._kill_process(inst.process, "SITL", inst.sysid)
            inst.process = None

        self.instances.clear()

    def connection_strings(self) -> list[str]:
        """Return MAVLink connection strings for all running instances."""
        return [inst.connection_string for inst in self.instances]

    # -- Internals ------------------------------------------------------------

    @staticmethod
    def _kill_process(
        proc: subprocess.Popen | None,
        label: str,
        sysid: int,
    ) -> None:
        """Terminate a subprocess gracefully, then kill if needed."""
        if proc is None:
            return
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            logger.info("[SIM] Stopped %s sysid=%d", label, sysid)
        except OSError as exc:
            logger.warning(
                "[SIM] Error stopping %s sysid=%d: %s", label, sysid, exc,
            )

    @staticmethod
    def _should_use_wsl() -> bool:
        """Detect if we are on Windows and need to proxy through WSL."""
        return platform.system() == "Windows"

    def _find_sitl(self) -> str:
        """
        Locate the ``arducopter`` SITL binary.

        Search order:
        1. ``$PATH`` (or WSL ``which``)
        2. Well-known build locations
        3. Raise :class:`SITLNotFoundError`
        """
        searched: list[str] = []

        if self._use_wsl:
            return self._find_sitl_wsl(searched)

        # Native Linux / macOS
        found = shutil.which(self.SITL_BINARY)
        if found:
            return found
        searched.append("$PATH")

        for p in self._COMMON_PATHS:
            searched.append(p)
            if Path(p).exists():
                return p

        raise SITLNotFoundError(searched)

    def _find_sitl_wsl(self, searched: list[str]) -> str:
        """Locate arducopter inside WSL."""
        # Try ``wsl which arducopter``
        try:
            result = subprocess.run(
                ["wsl", "which", self.SITL_BINARY],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        searched.append("wsl which arducopter")

        # Try well-known WSL paths
        wsl_user = self._get_wsl_username()
        candidate_paths = list(self._WSL_PATHS)
        if wsl_user:
            candidate_paths.insert(
                0,
                f"/home/{wsl_user}/ardupilot/build/sitl/bin/arducopter",
            )

        for wsl_path in candidate_paths:
            searched.append(f"wsl:{wsl_path}")
            try:
                result = subprocess.run(
                    ["wsl", "test", "-f", wsl_path],
                    capture_output=True, timeout=10,
                )
                if result.returncode == 0:
                    return wsl_path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        raise SITLNotFoundError(searched)

    def _find_mavproxy(self) -> None:
        """
        Verify that ``mavproxy.py`` is available.

        On Windows/WSL, checks ``wsl which mavproxy.py``.
        On native Linux/macOS, checks ``$PATH``.

        Raises :class:`MAVProxyNotFoundError` if not found.
        """
        if self._use_wsl:
            try:
                result = subprocess.run(
                    ["wsl", "which", self.MAVPROXY_BINARY],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            raise MAVProxyNotFoundError()

        if shutil.which(self.MAVPROXY_BINARY):
            return
        raise MAVProxyNotFoundError()

    @staticmethod
    def _get_wsl_username() -> str | None:
        """Get the default WSL username."""
        try:
            result = subprocess.run(
                ["wsl", "whoami"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _build_command(self, instance: SITLInstance, *, wipe: bool) -> list[str]:
        """Build the subprocess command list for one SITL instance."""
        home_str = (
            f"{instance.home_lat},{instance.home_lon},"
            f"{instance.home_alt},{instance.home_heading}"
        )

        sitl_args = [
            self.sitl_path,
            f"--sysid={instance.sysid}",
            f"--home={home_str}",
            f"--speedup={self.speedup}",
            f"--base-port={instance.tcp_port}",
            "--model=+",
        ]
        if wipe:
            sitl_args.append("--wipe")

        if self._use_wsl:
            return ["wsl", *sitl_args]

        return sitl_args

    def _build_mavproxy_command(self, instance: SITLInstance) -> list[str]:
        """Build the subprocess command list for one MAVProxy daemon."""
        mavproxy_args = [
            self.MAVPROXY_BINARY,
            f"--master=tcp:127.0.0.1:{instance.tcp_port}",
            f"--out=udp:127.0.0.1:{instance.mavproxy_port}",
            "--daemon",
        ]

        if self._use_wsl:
            return ["wsl", *mavproxy_args]

        return mavproxy_args

    async def _wait_for_all_ready(self) -> None:
        """Poll TCP ports until every SITL instance is accepting connections."""
        tasks = [
            self._wait_for_port(inst.tcp_port, inst.sysid)
            for inst in self.instances
        ]
        await asyncio.gather(*tasks)

    async def _wait_for_port(
        self, port: int, sysid: int, poll_interval: float = 0.5,
    ) -> None:
        """
        Wait until *port* on localhost accepts a TCP connection, or raise
        :class:`SITLStartupError` after ``startup_timeout`` seconds.
        """
        deadline = asyncio.get_event_loop().time() + self.startup_timeout
        while asyncio.get_event_loop().time() < deadline:
            if self._port_open(port):
                logger.info(
                    "[SIM] SITL sysid=%d ready on port %d", sysid, port,
                )
                return
            # Also check that the process hasn't crashed
            inst = next((i for i in self.instances if i.sysid == sysid), None)
            if inst and inst.process and inst.process.poll() is not None:
                raise SITLStartupError(
                    f"SITL sysid={sysid} exited with code "
                    f"{inst.process.returncode} before becoming ready"
                )
            await asyncio.sleep(poll_interval)

        raise SITLStartupError(
            f"SITL sysid={sysid} did not become ready on port {port} "
            f"within {self.startup_timeout}s"
        )

    @staticmethod
    def _port_open(port: int, host: str = "127.0.0.1") -> bool:
        """Return True if a TCP connection to *host*:*port* succeeds."""
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False
