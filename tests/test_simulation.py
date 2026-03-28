"""
Tests for the SITL simulation harness.

All tests mock the subprocess / network layer so they run without an actual
ArduPilot installation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from drone_swarm.simulation import (
    MAVProxyNotFoundError,
    SimulationHarness,
    SITLInstance,
    SITLNotFoundError,
    SITLStartupError,
)
from drone_swarm.swarm import SwarmOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_popen(*args, **kwargs):
    """Return a mock Popen whose poll() returns None (still running)."""
    proc = MagicMock()
    proc.pid = 12345
    proc.poll.return_value = None  # process is alive
    proc.returncode = None
    proc.wait.return_value = 0
    return proc


def _fake_popen_dead(*args, **kwargs):
    """Return a mock Popen whose poll() returns 1 (crashed immediately)."""
    proc = MagicMock()
    proc.pid = 99999
    proc.poll.return_value = 1
    proc.returncode = 1
    return proc


# Patch target for both _find_sitl and _find_mavproxy (the two checks in __init__)
_FIND_SITL = patch.object(SimulationHarness, "_find_sitl", return_value="/fake/arducopter")
_FIND_MAVPROXY = patch.object(SimulationHarness, "_find_mavproxy", return_value=None)


# ---------------------------------------------------------------------------
# SITLInstance
# ---------------------------------------------------------------------------

class TestSITLInstance:
    def test_connection_string(self):
        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        assert inst.connection_string == "udp:127.0.0.1:9760"

    def test_connection_string_different_port(self):
        inst = SITLInstance(
            sysid=2, tcp_port=5770, mavproxy_port=9770,
            home_lat=35.0, home_lon=-117.0,
        )
        assert inst.connection_string == "udp:127.0.0.1:9770"

    def test_default_alt_and_heading(self):
        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        assert inst.home_alt == 0.0
        assert inst.home_heading == 0.0

    def test_process_default_none(self):
        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        assert inst.process is None

    def test_mavproxy_process_default_none(self):
        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        assert inst.mavproxy_process is None


# ---------------------------------------------------------------------------
# Connection string generation
# ---------------------------------------------------------------------------

class TestConnectionStrings:
    """Verify the harness generates correct connection strings for N drones."""

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_three_drones_ports(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=3, base_port=5760, port_step=10)
        await sim.start()

        strings = sim.connection_strings()
        assert strings == [
            "udp:127.0.0.1:9760",
            "udp:127.0.0.1:9770",
            "udp:127.0.0.1:9780",
        ]
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_custom_base_port(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=2, base_port=6000, port_step=20)
        await sim.start()

        strings = sim.connection_strings()
        assert strings == [
            "udp:127.0.0.1:10000",
            "udp:127.0.0.1:10020",
        ]
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_single_drone(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=1)
        await sim.start()

        assert len(sim.instances) == 1
        assert sim.instances[0].sysid == 1
        assert sim.instances[0].connection_string == "udp:127.0.0.1:9760"
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_custom_mavproxy_base_port(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(
            n_drones=2, base_port=5760, port_step=10,
            mavproxy_base_port=14550,
        )
        await sim.start()

        strings = sim.connection_strings()
        assert strings == [
            "udp:127.0.0.1:14550",
            "udp:127.0.0.1:14560",
        ]
        await sim.stop()


# ---------------------------------------------------------------------------
# SimulationHarness init / SITL detection
# ---------------------------------------------------------------------------

class TestHarnessInit:

    @_FIND_SITL
    @_FIND_MAVPROXY
    def test_default_init(self, mock_mavproxy, mock_find):
        sim = SimulationHarness(n_drones=3)
        assert sim.n_drones == 3
        assert sim.base_port == 5760
        assert sim.port_step == 10
        assert sim.mavproxy_base_port == 9760  # 5760 + 4000
        assert sim.sitl_path == "/fake/arducopter"
        assert sim.instances == []

    @_FIND_MAVPROXY
    def test_explicit_sitl_path_skips_find(self, mock_mavproxy):
        sim = SimulationHarness(n_drones=1, sitl_path="/my/custom/arducopter")
        assert sim.sitl_path == "/my/custom/arducopter"

    @patch("shutil.which", return_value=None)
    @patch("pathlib.Path.exists", return_value=False)
    @patch.object(SimulationHarness, "_should_use_wsl", return_value=False)
    def test_sitl_not_found_raises(self, mock_wsl, mock_exists, mock_which):
        with pytest.raises(SITLNotFoundError, match="arducopter.*not found"):
            SimulationHarness(n_drones=1)

    @_FIND_MAVPROXY
    @patch("shutil.which", return_value="/usr/local/bin/arducopter")
    @patch.object(SimulationHarness, "_should_use_wsl", return_value=False)
    def test_finds_on_path(self, mock_wsl, mock_which, mock_mavproxy):
        sim = SimulationHarness(n_drones=1)
        assert sim.sitl_path == "/usr/local/bin/arducopter"


# ---------------------------------------------------------------------------
# MAVProxyNotFoundError
# ---------------------------------------------------------------------------

class TestMAVProxyNotFoundError:

    def test_message_contains_install_instructions(self):
        err = MAVProxyNotFoundError()
        msg = str(err)
        assert "MAVProxy" in msg
        assert "pip install" in msg

    @_FIND_SITL
    @patch("shutil.which", return_value=None)
    @patch.object(SimulationHarness, "_should_use_wsl", return_value=False)
    def test_mavproxy_not_found_raises(self, mock_wsl, mock_which, mock_find):
        with pytest.raises(MAVProxyNotFoundError, match="MAVProxy not found"):
            SimulationHarness(n_drones=1)


# ---------------------------------------------------------------------------
# SITLNotFoundError message quality
# ---------------------------------------------------------------------------

class TestSITLNotFoundError:

    def test_message_contains_install_url(self):
        err = SITLNotFoundError()
        assert "https://ardupilot.org" in str(err)
        assert "arducopter" in str(err)

    def test_message_lists_searched_locations(self):
        err = SITLNotFoundError(searched=["/a/b/c", "$PATH"])
        msg = str(err)
        assert "/a/b/c" in msg
        assert "$PATH" in msg


# ---------------------------------------------------------------------------
# Launching instances (mocked subprocess)
# ---------------------------------------------------------------------------

class TestLaunch:

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_launch_creates_instances(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=3)
        instances = await sim.start()

        assert len(instances) == 3
        for i, inst in enumerate(instances):
            assert inst.sysid == i + 1
            assert inst.tcp_port == 5760 + i * 10
            assert inst.mavproxy_port == 9760 + i * 10
            assert inst.process is not None
            assert inst.mavproxy_process is not None

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_launch_staggered_home_positions(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=3, home=(35.0, -117.0), spacing_m=5.0)
        await sim.start()

        lats = [inst.home_lat for inst in sim.instances]
        assert lats[0] == pytest.approx(35.0)
        assert lats[1] > lats[0]
        assert lats[2] > lats[1]
        # Spacing should be ~5m / 111320 degrees apart
        assert lats[1] - lats[0] == pytest.approx(5.0 / 111_320.0)
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_popen_called_for_sitl_and_mavproxy(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=1, speedup=2, wipe=True)
        sim._use_wsl = False
        await sim.start()

        # 1 SITL Popen + 1 MAVProxy Popen = 2 total
        assert mock_popen.call_count == 2

        # First call is SITL
        sitl_cmd = mock_popen.call_args_list[0][0][0]
        assert sitl_cmd[0] == "/fake/arducopter"
        assert "--sysid=1" in sitl_cmd
        assert "--speedup=2" in sitl_cmd
        assert "--model=+" in sitl_cmd
        assert "--wipe" in sitl_cmd

        # Second call is MAVProxy
        mavproxy_cmd = mock_popen.call_args_list[1][0][0]
        assert mavproxy_cmd[0] == "mavproxy.py"
        assert "--master=tcp:127.0.0.1:5760" in mavproxy_cmd
        assert "--out=udp:127.0.0.1:9760" in mavproxy_cmd
        assert "--daemon" in mavproxy_cmd

        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_wipe_only_on_first_instance(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=2, wipe=True)
        sim._use_wsl = False
        await sim.start()

        # 2 SITL + 2 MAVProxy = 4 Popen calls
        assert mock_popen.call_count == 4
        first_sitl_cmd = mock_popen.call_args_list[0][0][0]
        second_sitl_cmd = mock_popen.call_args_list[1][0][0]
        assert "--wipe" in first_sitl_cmd
        assert "--wipe" not in second_sitl_cmd
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_mavproxy_settle_wait(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=1, mavproxy_settle_s=5.0)
        await sim.start()

        # asyncio.sleep should be called with the settle time
        mock_sleep.assert_awaited_with(5.0)
        await sim.stop()


# ---------------------------------------------------------------------------
# WSL command building
# ---------------------------------------------------------------------------

class TestWSLCommand:

    @_FIND_SITL
    @_FIND_MAVPROXY
    def test_wsl_prefixes_command(self, mock_mavproxy, mock_find):
        sim = SimulationHarness(n_drones=1)
        sim._use_wsl = True

        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        cmd = sim._build_command(inst, wipe=False)

        assert cmd[0] == "wsl"
        assert cmd[1] == sim.sitl_path

    @_FIND_SITL
    @_FIND_MAVPROXY
    def test_wsl_prefixes_mavproxy_command(self, mock_mavproxy, mock_find):
        sim = SimulationHarness(n_drones=1)
        sim._use_wsl = True

        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        cmd = sim._build_mavproxy_command(inst)

        assert cmd[0] == "wsl"
        assert cmd[1] == "mavproxy.py"
        assert "--master=tcp:127.0.0.1:5760" in cmd
        assert "--out=udp:127.0.0.1:9760" in cmd
        assert "--daemon" in cmd

    @_FIND_SITL
    @_FIND_MAVPROXY
    def test_native_no_wsl_prefix(self, mock_mavproxy, mock_find):
        sim = SimulationHarness(n_drones=1)
        sim._use_wsl = False

        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        cmd = sim._build_command(inst, wipe=False)

        assert cmd[0] == "/fake/arducopter"
        assert "wsl" not in cmd

    @_FIND_SITL
    @_FIND_MAVPROXY
    def test_native_no_wsl_prefix_mavproxy(self, mock_mavproxy, mock_find):
        sim = SimulationHarness(n_drones=1)
        sim._use_wsl = False

        inst = SITLInstance(
            sysid=1, tcp_port=5760, mavproxy_port=9760,
            home_lat=35.0, home_lon=-117.0,
        )
        cmd = sim._build_mavproxy_command(inst)

        assert cmd[0] == "mavproxy.py"
        assert "wsl" not in cmd


# ---------------------------------------------------------------------------
# Cleanup on error
# ---------------------------------------------------------------------------

class TestCleanup:

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_stop_terminates_all(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=2)
        await sim.start()
        sitl_procs = [inst.process for inst in sim.instances]
        mavproxy_procs = [inst.mavproxy_process for inst in sim.instances]

        await sim.stop()

        for proc in sitl_procs:
            proc.terminate.assert_called_once()
        for proc in mavproxy_procs:
            proc.terminate.assert_called_once()
        assert sim.instances == []

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_context_manager_cleanup(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        async with SimulationHarness(n_drones=2) as sim:
            sitl_procs = [inst.process for inst in sim.instances]
            mavproxy_procs = [inst.mavproxy_process for inst in sim.instances]
            assert len(sitl_procs) == 2
            assert len(mavproxy_procs) == 2

        # After exit, instances should be cleared
        assert sim.instances == []
        for proc in sitl_procs:
            proc.terminate.assert_called_once()
        for proc in mavproxy_procs:
            proc.terminate.assert_called_once()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_context_manager_cleanup_on_exception(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        procs = []
        mavproxy_procs = []
        with pytest.raises(ValueError, match="boom"):
            async with SimulationHarness(n_drones=2) as sim:
                procs = [inst.process for inst in sim.instances]
                mavproxy_procs = [inst.mavproxy_process for inst in sim.instances]
                raise ValueError("boom")

        assert sim.instances == []
        for proc in procs:
            proc.terminate.assert_called_once()
        for proc in mavproxy_procs:
            proc.terminate.assert_called_once()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch.object(SimulationHarness, "_port_open", return_value=False)
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen_dead)
    async def test_cleanup_on_startup_failure(
        self, mock_popen, mock_port, mock_mavproxy, mock_find,
    ):
        """If a SITL process crashes during startup, stop() is still called."""
        sim = SimulationHarness(n_drones=1, startup_timeout=0.5)
        with pytest.raises(SITLStartupError):
            await sim.start()

        # All instances should be cleaned up
        assert sim.instances == []

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_stop_handles_already_dead_process(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=1)
        await sim.start()

        # Simulate both processes already being dead
        sim.instances[0].process.poll.return_value = 0
        sim.instances[0].mavproxy_process.poll.return_value = 0

        # Should not raise
        await sim.stop()
        # terminate should NOT be called on an already-dead process
        assert sim.instances == []  # cleared


# ---------------------------------------------------------------------------
# Port readiness
# ---------------------------------------------------------------------------

class TestPortReadiness:

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    async def test_timeout_raises_startup_error(
        self, mock_popen, mock_mavproxy, mock_find,
    ):
        sim = SimulationHarness(n_drones=1, startup_timeout=0.5)
        # _port_open always returns False -> timeout
        with patch.object(SimulationHarness, "_port_open", return_value=False):
            with pytest.raises(SITLStartupError, match="did not become ready"):
                await sim.start()

    def test_port_open_returns_false_for_closed_port(self):
        # Use a port that is almost certainly not listening
        assert SimulationHarness._port_open(59999) is False


# ---------------------------------------------------------------------------
# Swarm.simulate() factory
# ---------------------------------------------------------------------------

class TestSwarmSimulate:

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_returns_swarm_and_harness(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock):
            swarm, sim = await SwarmOrchestrator.simulate(n_drones=3)

        assert isinstance(swarm, SwarmOrchestrator)
        assert isinstance(sim, SimulationHarness)
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_registers_named_drones(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock):
            swarm, sim = await SwarmOrchestrator.simulate(n_drones=3)

        assert list(swarm.drones.keys()) == ["sim-0", "sim-1", "sim-2"]
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_drone_connection_strings(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock):
            swarm, sim = await SwarmOrchestrator.simulate(n_drones=3)

        # Connection strings now go through MAVProxy UDP
        assert swarm.drones["sim-0"].connection_string == "udp:127.0.0.1:9760"
        assert swarm.drones["sim-1"].connection_string == "udp:127.0.0.1:9770"
        assert swarm.drones["sim-2"].connection_string == "udp:127.0.0.1:9780"
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_calls_connect(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock) as mock_conn:
            _swarm, sim = await SwarmOrchestrator.simulate(n_drones=2)
            mock_conn.assert_awaited_once()
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_no_auto_connect(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock) as mock_conn:
            _swarm, sim = await SwarmOrchestrator.simulate(
                n_drones=2, auto_connect=False,
            )
            mock_conn.assert_not_awaited()
        await sim.stop()

    @_FIND_SITL
    @_FIND_MAVPROXY
    @patch("drone_swarm.simulation.subprocess.Popen", side_effect=_fake_popen)
    @patch.object(SimulationHarness, "_port_open", return_value=True)
    @patch("drone_swarm.simulation.asyncio.sleep", new_callable=AsyncMock)
    async def test_simulate_custom_base_port(
        self, mock_sleep, mock_port, mock_popen, mock_mavproxy, mock_find,
    ):
        with patch.object(SwarmOrchestrator, "connect_all", new_callable=AsyncMock):
            swarm, sim = await SwarmOrchestrator.simulate(
                n_drones=2, base_port=7000,
            )

        # base_port=7000 -> mavproxy_base_port = 7000+4000 = 11000
        assert swarm.drones["sim-0"].connection_string == "udp:127.0.0.1:11000"
        assert swarm.drones["sim-1"].connection_string == "udp:127.0.0.1:11010"
        await sim.stop()

    async def test_simulate_sitl_not_found(self):
        with patch.object(SimulationHarness, "_should_use_wsl", return_value=False), \
             patch("shutil.which", return_value=None), \
             patch("pathlib.Path.exists", return_value=False), pytest.raises(SITLNotFoundError):
            await SwarmOrchestrator.simulate(n_drones=1)
