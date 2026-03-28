"""Tests for the dso CLI (drone_swarm.cli)."""

from __future__ import annotations

import os

import pytest

from drone_swarm.cli import _SWARM_YAML_TEMPLATE, build_parser, main

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

class TestParser:
    """Verify argument parsing for each subcommand."""

    def test_no_command_returns_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_version_command(self):
        parser = build_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_init_command(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"
        assert args.force is False

    def test_init_force(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--force"])
        assert args.command == "init"
        assert args.force is True

    def test_simulate_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["simulate"])
        assert args.command == "simulate"
        assert args.drones == 3
        assert args.speedup == 1

    def test_simulate_custom(self):
        parser = build_parser()
        args = parser.parse_args(["simulate", "--drones", "5", "--speedup", "10"])
        assert args.drones == 5
        assert args.speedup == 10

    def test_simulate_short_flags(self):
        parser = build_parser()
        args = parser.parse_args(["simulate", "-n", "2", "-s", "4"])
        assert args.drones == 2
        assert args.speedup == 4

    def test_status_requires_connection(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["status"])

    def test_status_with_connection(self):
        parser = build_parser()
        args = parser.parse_args(["status", "--connection", "tcp:127.0.0.1:5760"])
        assert args.command == "status"
        assert args.connection == "tcp:127.0.0.1:5760"

    def test_status_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["status", "-c", "udp:127.0.0.1:14550"])
        assert args.connection == "udp:127.0.0.1:14550"

    def test_preflight_requires_connection(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["preflight"])

    def test_preflight_with_connection(self):
        parser = build_parser()
        args = parser.parse_args(["preflight", "-c", "tcp:127.0.0.1:5760"])
        assert args.command == "preflight"
        assert args.connection == "tcp:127.0.0.1:5760"
        assert args.id == "drone-1"

    def test_preflight_custom_id(self):
        parser = build_parser()
        args = parser.parse_args(["preflight", "-c", "tcp:127.0.0.1:5760", "--id", "alpha"])
        assert args.id == "alpha"


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

class TestHelp:
    """Verify help text does not crash and contains expected strings."""

    def test_top_level_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "dso" in out
        assert "simulate" in out
        assert "status" in out
        assert "preflight" in out
        assert "init" in out

    def test_simulate_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["simulate", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--drones" in out
        assert "--speedup" in out

    def test_status_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["status", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--connection" in out

    def test_preflight_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["preflight", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--connection" in out
        assert "--id" in out


# ---------------------------------------------------------------------------
# dso version
# ---------------------------------------------------------------------------

class TestVersionCommand:
    def test_prints_version(self, capsys):
        from drone_swarm._version import __version__
        rc = main(["version"])
        assert rc == 0
        out = capsys.readouterr().out
        assert __version__ in out

    def test_version_flag(self, capsys):
        """--version flag on the top-level parser also works."""
        from drone_swarm._version import __version__
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert __version__ in out


# ---------------------------------------------------------------------------
# dso init
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_creates_swarm_yaml(self, tmp_path, capsys):
        """dso init creates a swarm.yaml file."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            rc = main(["init"])
            assert rc == 0
            created = tmp_path / "swarm.yaml"
            assert created.exists()
            content = created.read_text(encoding="utf-8")
            assert "swarm:" in content
            assert "drones:" in content
            out = capsys.readouterr().out
            assert "Created" in out
        finally:
            os.chdir(original_cwd)

    def test_refuses_overwrite_without_force(self, tmp_path, capsys):
        """dso init refuses to overwrite an existing swarm.yaml."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            (tmp_path / "swarm.yaml").write_text("existing", encoding="utf-8")
            rc = main(["init"])
            assert rc == 1
            out = capsys.readouterr().out
            assert "already exists" in out
        finally:
            os.chdir(original_cwd)

    def test_force_overwrites(self, tmp_path, capsys):
        """dso init --force overwrites an existing swarm.yaml."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            (tmp_path / "swarm.yaml").write_text("old", encoding="utf-8")
            rc = main(["init", "--force"])
            assert rc == 0
            content = (tmp_path / "swarm.yaml").read_text(encoding="utf-8")
            assert content == _SWARM_YAML_TEMPLATE
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# dso with no args
# ---------------------------------------------------------------------------

class TestNoArgs:
    def test_no_args_prints_help(self, capsys):
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "dso" in out
