"""Tests for drone_swarm.config -- SwarmConfig defaults, from_dict, validation."""


from drone_swarm.config import SwarmConfig


class TestSwarmConfigDefaults:
    def test_heartbeat_timeout(self, default_config):
        assert default_config.heartbeat_timeout_s == 15.0

    def test_battery_rtl_threshold(self, default_config):
        assert default_config.battery_rtl_threshold_pct == 20.0

    def test_preflight_min_battery(self, default_config):
        assert default_config.preflight_min_battery_pct == 80.0

    def test_preflight_min_satellites(self, default_config):
        assert default_config.preflight_min_satellites == 6

    def test_default_altitude(self, default_config):
        assert default_config.default_altitude_m == 10.0

    def test_sitl_speedup(self, default_config):
        assert default_config.sitl_speedup == 1

    def test_mavlink_baud(self, default_config):
        assert default_config.mavlink_baud == 57600

    def test_waypoint_reach_threshold(self, default_config):
        assert default_config.waypoint_reach_threshold_m == 2.0


class TestSwarmConfigFromDict:
    def test_override_single_field(self):
        cfg = SwarmConfig.from_dict({"heartbeat_timeout_s": 30.0})
        assert cfg.heartbeat_timeout_s == 30.0
        # Other fields stay default
        assert cfg.battery_rtl_threshold_pct == 20.0

    def test_override_multiple_fields(self):
        cfg = SwarmConfig.from_dict({
            "heartbeat_timeout_s": 5.0,
            "default_altitude_m": 25.0,
            "sitl_speedup": 10,
        })
        assert cfg.heartbeat_timeout_s == 5.0
        assert cfg.default_altitude_m == 25.0
        assert cfg.sitl_speedup == 10

    def test_unknown_keys_are_ignored(self):
        cfg = SwarmConfig.from_dict({
            "heartbeat_timeout_s": 8.0,
            "totally_unknown_key": "should be ignored",
            "another_fake": 42,
        })
        assert cfg.heartbeat_timeout_s == 8.0
        assert not hasattr(cfg, "totally_unknown_key")

    def test_empty_dict_returns_defaults(self):
        cfg = SwarmConfig.from_dict({})
        default = SwarmConfig()
        assert cfg == default

    def test_from_dict_type_preservation(self):
        cfg = SwarmConfig.from_dict({"rtl_base_alt_cm": 2000})
        assert cfg.rtl_base_alt_cm == 2000
        assert isinstance(cfg.rtl_base_alt_cm, int)


class TestSwarmConfigValidation:
    def test_config_fields_are_numeric(self):
        """All config fields should have numeric defaults (no None)."""
        cfg = SwarmConfig()
        for f in cfg.__dataclass_fields__.values():
            val = getattr(cfg, f.name)
            assert isinstance(val, (int, float)), f"{f.name} is {type(val)}, expected numeric"

    def test_battery_thresholds_are_percentages(self):
        cfg = SwarmConfig()
        assert 0 <= cfg.battery_rtl_threshold_pct <= 100
        assert 0 <= cfg.preflight_min_battery_pct <= 100

    def test_altitudes_are_positive(self):
        cfg = SwarmConfig()
        assert cfg.default_altitude_m > 0
        assert cfg.rtl_base_alt_cm > 0
