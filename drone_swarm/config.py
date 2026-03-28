"""
YAML/dict-based configuration loader.

Replaces hardcoded constants scattered across modules with a single,
overridable configuration object. Supports loading from a YAML file,
a plain dict, or falling back to sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SwarmConfig:
    """
    Central configuration for the drone-swarm SDK.

    All values have safe defaults so the SDK works out-of-the-box for
    simulation. Override via :meth:`from_yaml` or :meth:`from_dict`.
    """

    # -- Telemetry thresholds --------------------------------------------------
    heartbeat_timeout_s: float = 15.0
    battery_rtl_threshold_pct: float = 20.0
    battery_check_grace_period_s: float = 30.0

    # -- RTL altitude staggering -----------------------------------------------
    rtl_base_alt_cm: int = 1500       # 15 m
    rtl_alt_stagger_cm: int = 500     # 5 m per drone

    # -- Connection defaults ---------------------------------------------------
    mavlink_baud: int = 57600
    heartbeat_wait_timeout_s: float = 10.0

    # -- Preflight check thresholds -------------------------------------------
    preflight_min_battery_pct: float = 80.0
    preflight_min_satellites: int = 6
    preflight_vibration_threshold: float = 30.0

    # -- Mission defaults ------------------------------------------------------
    default_altitude_m: float = 10.0
    waypoint_reach_threshold_m: float = 2.0

    # -- Simulation ------------------------------------------------------------
    sitl_speedup: int = 1

    # ---- Factory methods -----------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmConfig:
        """
        Create a config from a plain dictionary.

        Unknown keys are silently ignored so you can pass a superset
        (e.g. a full project config that also contains non-swarm keys).
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_yaml(cls, path: str | Path) -> SwarmConfig:
        """
        Load configuration from a YAML file.

        Requires ``pyyaml`` to be installed (optional dependency).
        """
        try:
            import yaml
        except ImportError as err:
            raise ImportError(
                "PyYAML is required to load config from YAML. "
                "Install it with: pip install pyyaml"
            ) from err
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # Support a top-level ``swarm:`` key or flat structure
        if "swarm" in data and isinstance(data["swarm"], dict):
            data = data["swarm"]
        return cls.from_dict(data)
