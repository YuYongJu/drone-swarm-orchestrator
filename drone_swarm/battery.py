"""
Battery State-of-Charge estimation and remaining-flight-time prediction.

Uses coulomb counting with Peukert correction to account for the fact that
higher discharge rates yield less usable capacity from a LiPo battery.

    actual_capacity = rated_capacity * (rated_current / actual_current) ^ (p - 1)

where *p* is the Peukert exponent (~1.05 for LiPo).

References:
- NASA, "Remaining Flying Time Prediction Implementing Battery SOC Estimation", 2018.
- "Measuring Battery Discharge Characteristics for Accurate UAV Endurance Estimation", 2020.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BatteryConfig:
    """Configuration parameters for a single battery pack.

    Attributes:
        rated_capacity_mah: Nameplate capacity in mAh (e.g. 3000).
        rated_voltage: Nominal pack voltage in V (e.g. 14.8 for 4S).
        peukert_exponent: Peukert exponent for the cell chemistry.
            LiPo is typically ~1.05.
        min_voltage: Voltage at which the pack is considered empty.
            For a 4S LiPo at 3.3 V/cell this is 13.2 V.
        reserve_pct: Safety reserve percentage (0-100).  The predictor
            will treat this portion of capacity as unavailable.
    """
    rated_capacity_mah: float = 3000.0
    rated_voltage: float = 14.8
    peukert_exponent: float = 1.05
    min_voltage: float = 13.2
    reserve_pct: float = 20.0


@dataclass
class BatteryPredictor:
    """Per-battery SOC estimator and flight-time predictor.

    Combines coulomb counting with Peukert correction to track how much
    energy has been consumed and predict how much remains.

    Args:
        config: A :class:`BatteryConfig` describing the battery pack.
    """
    config: BatteryConfig = field(default_factory=BatteryConfig)

    # Internal state
    _consumed_mah: float = field(default=0.0, init=False, repr=False)
    _latest_voltage: float = field(default=0.0, init=False, repr=False)
    _latest_current_a: float = field(default=0.0, init=False, repr=False)
    _avg_current_a: float = field(default=0.0, init=False, repr=False)
    _update_count: int = field(default=0, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def update(self, voltage: float, current_a: float, dt_s: float) -> None:
        """Record a new telemetry sample.

        Args:
            voltage: Instantaneous pack voltage in volts.
            current_a: Instantaneous current draw in amps (positive = discharge).
            dt_s: Time elapsed since the last sample, in seconds.
        """
        self._latest_voltage = voltage
        self._latest_current_a = current_a

        # Coulomb counting: consumed_mAh += current_mA * dt_h
        if current_a > 0 and dt_s > 0:
            current_ma = current_a * 1000.0
            dt_h = dt_s / 3600.0
            self._consumed_mah += current_ma * dt_h

        # Running average of current draw
        self._update_count += 1
        self._avg_current_a += (current_a - self._avg_current_a) / self._update_count

    def get_soc(self) -> float:
        """Estimated State of Charge as a percentage (0-100).

        Uses Peukert-corrected effective capacity so that high-current
        draws correctly report a faster SOC decrease.
        """
        effective_cap = self._effective_capacity_mah()
        if effective_cap <= 0:
            return 0.0
        soc = ((effective_cap - self._consumed_mah) / effective_cap) * 100.0
        return max(0.0, min(100.0, soc))

    def get_remaining_flight_time_s(self) -> float:
        """Estimated remaining flight time in seconds.

        Based on the usable (reserve-adjusted, Peukert-corrected) capacity
        minus what has already been consumed, divided by the running-average
        current draw.

        Returns 0.0 if there is no current draw history or the battery is
        depleted.
        """
        effective_cap = self._effective_capacity_mah()
        usable_cap = effective_cap * (1.0 - self.config.reserve_pct / 100.0)
        remaining_mah = usable_cap - self._consumed_mah
        if remaining_mah <= 0:
            return 0.0
        avg_ma = self._avg_current_a * 1000.0
        if avg_ma <= 0:
            return 0.0
        remaining_h = remaining_mah / avg_ma
        return remaining_h * 3600.0

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _effective_capacity_mah(self) -> float:
        """Peukert-corrected effective capacity in mAh.

        actual_capacity = rated_capacity * (I_rated / I_actual) ^ (p - 1)

        If the average current is unknown (no updates yet), returns the
        rated capacity unmodified.
        """
        cfg = self.config
        if self._avg_current_a <= 0:
            return cfg.rated_capacity_mah

        # Rated current: the 1C discharge rate
        rated_current_a = cfg.rated_capacity_mah / 1000.0  # mAh -> Ah = C-rate current

        ratio = rated_current_a / self._avg_current_a
        # Peukert correction
        effective = cfg.rated_capacity_mah * (ratio ** (cfg.peukert_exponent - 1))
        return effective
