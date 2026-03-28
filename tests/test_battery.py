"""Tests for drone_swarm.battery -- SOC estimation and flight time prediction."""

import pytest

from drone_swarm.battery import BatteryConfig, BatteryPredictor

# ---------------------------------------------------------------------------
# BatteryConfig dataclass
# ---------------------------------------------------------------------------

class TestBatteryConfig:
    def test_defaults(self):
        cfg = BatteryConfig()
        assert cfg.rated_capacity_mah == 3000.0
        assert cfg.rated_voltage == 14.8
        assert cfg.peukert_exponent == 1.05
        assert cfg.min_voltage == 13.2
        assert cfg.reserve_pct == 20.0

    def test_custom_config(self):
        cfg = BatteryConfig(rated_capacity_mah=5000.0, reserve_pct=25.0)
        assert cfg.rated_capacity_mah == 5000.0
        assert cfg.reserve_pct == 25.0


# ---------------------------------------------------------------------------
# SOC: full battery at start
# ---------------------------------------------------------------------------

class TestFullBattery:
    def test_no_consumption_is_100_pct(self):
        pred = BatteryPredictor()
        # Feed a sample at rated voltage with zero current to initialise
        pred.update(voltage=14.8, current_a=0.0, dt_s=0.0)
        assert pred.get_soc() == pytest.approx(100.0)

    def test_soc_100_before_any_update(self):
        """Before any updates, consumed_mah is 0, so SOC should be 100%."""
        pred = BatteryPredictor()
        assert pred.get_soc() == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# SOC decreases with current draw
# ---------------------------------------------------------------------------

class TestSOCDecreases:
    def test_soc_drops_after_discharge(self):
        pred = BatteryPredictor()
        # Draw 3A for 60 seconds => 50 mAh consumed
        pred.update(voltage=14.4, current_a=3.0, dt_s=60.0)
        soc = pred.get_soc()
        assert soc < 100.0
        assert soc > 0.0

    def test_more_time_means_lower_soc(self):
        pred1 = BatteryPredictor()
        pred2 = BatteryPredictor()

        pred1.update(voltage=14.4, current_a=3.0, dt_s=60.0)
        pred2.update(voltage=14.4, current_a=3.0, dt_s=600.0)

        assert pred2.get_soc() < pred1.get_soc()

    def test_soc_never_below_zero(self):
        pred = BatteryPredictor()
        # Massive discharge: 100A for 1 hour = 100,000 mAh >> 3000 mAh
        pred.update(voltage=12.0, current_a=100.0, dt_s=3600.0)
        assert pred.get_soc() == 0.0

    def test_soc_never_above_100(self):
        pred = BatteryPredictor()
        pred.update(voltage=14.8, current_a=0.0, dt_s=0.0)
        assert pred.get_soc() <= 100.0


# ---------------------------------------------------------------------------
# Peukert correction: high current = faster depletion
# ---------------------------------------------------------------------------

class TestPeukertCorrection:
    def test_high_current_depletes_faster(self):
        """At higher discharge rates, the effective capacity is lower,
        so SOC should drop faster per mAh consumed."""
        cfg = BatteryConfig(rated_capacity_mah=3000.0, peukert_exponent=1.05)

        # Low current: 3A (1C) for 120s => 100 mAh consumed
        pred_low = BatteryPredictor(config=cfg)
        pred_low.update(voltage=14.4, current_a=3.0, dt_s=120.0)
        soc_low = pred_low.get_soc()

        # High current: 30A (10C) for 12s => same 100 mAh consumed
        pred_high = BatteryPredictor(config=cfg)
        pred_high.update(voltage=14.4, current_a=30.0, dt_s=12.0)
        soc_high = pred_high.get_soc()

        # Same mAh consumed, but Peukert means high-current battery has
        # lower effective capacity => lower SOC
        assert soc_high < soc_low

    def test_peukert_exponent_1_means_no_correction(self):
        """With exponent=1.0, Peukert has no effect: ratio^0 = 1."""
        cfg = BatteryConfig(peukert_exponent=1.0)
        pred = BatteryPredictor(config=cfg)
        pred.update(voltage=14.4, current_a=30.0, dt_s=120.0)
        soc = pred.get_soc()
        # Consumed = 30 * 1000 * (120/3600) = 1000 mAh
        # effective capacity = 3000 * 1.0 = 3000 (no correction)
        expected = (3000 - 1000) / 3000 * 100
        assert soc == pytest.approx(expected, rel=0.01)

    def test_higher_exponent_more_penalty(self):
        """Higher Peukert exponent means more capacity loss at high current."""
        cfg_low = BatteryConfig(peukert_exponent=1.03)
        cfg_high = BatteryConfig(peukert_exponent=1.10)

        pred_low = BatteryPredictor(config=cfg_low)
        pred_high = BatteryPredictor(config=cfg_high)

        # Same high-current discharge
        pred_low.update(voltage=14.0, current_a=20.0, dt_s=60.0)
        pred_high.update(voltage=14.0, current_a=20.0, dt_s=60.0)

        # Higher exponent => lower effective capacity => lower SOC
        assert pred_high.get_soc() < pred_low.get_soc()


# ---------------------------------------------------------------------------
# Remaining flight time prediction
# ---------------------------------------------------------------------------

class TestRemainingFlightTime:
    def test_no_current_returns_zero(self):
        pred = BatteryPredictor()
        pred.update(voltage=14.8, current_a=0.0, dt_s=0.0)
        assert pred.get_remaining_flight_time_s() == 0.0

    def test_positive_flight_time(self):
        pred = BatteryPredictor()
        pred.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        rft = pred.get_remaining_flight_time_s()
        assert rft > 0

    def test_flight_time_decreases_with_consumption(self):
        pred = BatteryPredictor()
        pred.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        rft1 = pred.get_remaining_flight_time_s()

        pred.update(voltage=14.2, current_a=3.0, dt_s=600.0)
        rft2 = pred.get_remaining_flight_time_s()

        assert rft2 < rft1

    def test_depleted_battery_returns_zero(self):
        pred = BatteryPredictor()
        # Consume everything
        pred.update(voltage=12.0, current_a=100.0, dt_s=3600.0)
        assert pred.get_remaining_flight_time_s() == 0.0

    def test_flight_time_accounts_for_reserve(self):
        """With 20% reserve, flight time should be based on 80% of capacity."""
        cfg_no_reserve = BatteryConfig(reserve_pct=0.0)
        cfg_with_reserve = BatteryConfig(reserve_pct=20.0)

        pred_no = BatteryPredictor(config=cfg_no_reserve)
        pred_yes = BatteryPredictor(config=cfg_with_reserve)

        pred_no.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        pred_yes.update(voltage=14.4, current_a=3.0, dt_s=1.0)

        rft_no = pred_no.get_remaining_flight_time_s()
        rft_yes = pred_yes.get_remaining_flight_time_s()

        # Reserve means less usable capacity => shorter reported flight time
        assert rft_yes < rft_no
        # Should be roughly 80% of the no-reserve time
        assert rft_yes == pytest.approx(rft_no * 0.8, rel=0.05)


# ---------------------------------------------------------------------------
# Reserve enforcement
# ---------------------------------------------------------------------------

class TestReserveEnforcement:
    def test_reserve_reduces_usable_capacity(self):
        cfg = BatteryConfig(reserve_pct=50.0)
        pred = BatteryPredictor(config=cfg)
        pred.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        rft_50 = pred.get_remaining_flight_time_s()

        cfg2 = BatteryConfig(reserve_pct=0.0)
        pred2 = BatteryPredictor(config=cfg2)
        pred2.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        rft_0 = pred2.get_remaining_flight_time_s()

        # 50% reserve means half the usable capacity
        assert rft_50 == pytest.approx(rft_0 * 0.5, rel=0.05)

    def test_100_pct_reserve_means_zero_flight_time(self):
        cfg = BatteryConfig(reserve_pct=100.0)
        pred = BatteryPredictor(config=cfg)
        pred.update(voltage=14.4, current_a=3.0, dt_s=1.0)
        assert pred.get_remaining_flight_time_s() == 0.0


# ---------------------------------------------------------------------------
# Multiple updates accumulate consumption
# ---------------------------------------------------------------------------

class TestMultipleUpdates:
    def test_cumulative_consumption(self):
        pred = BatteryPredictor()
        # 3A for 60s twice = 3A for 120s total
        pred.update(voltage=14.4, current_a=3.0, dt_s=60.0)
        pred.update(voltage=14.3, current_a=3.0, dt_s=60.0)

        pred_single = BatteryPredictor()
        pred_single.update(voltage=14.4, current_a=3.0, dt_s=120.0)

        assert pred.get_soc() == pytest.approx(pred_single.get_soc(), rel=0.05)
