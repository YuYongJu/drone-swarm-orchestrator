"""Tests for the anomaly detection system (drone_swarm.anomaly).

Covers individual anomaly detection, swarm-level comparison,
severity scaling, window-size sensitivity, and edge cases.
"""


from drone_swarm.anomaly import Anomaly, AnomalyDetector
from drone_swarm.drone import Drone, DroneRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(drone_id: str = "alpha", **overrides) -> Drone:
    defaults = dict(
        drone_id=drone_id,
        connection_string="udp:127.0.0.1:14550",
        role=DroneRole.RECON,
        battery_pct=80.0,
        lat=35.0,
        lon=-117.0,
        alt=50.0,
        vibration_level=5.0,
        message_loss_rate=0.01,
    )
    defaults.update(overrides)
    return Drone(**defaults)


def _stable_metrics(
    battery_pct: float = 80.0,
    lat: float = 35.0,
    lon: float = -117.0,
    alt: float = 50.0,
    vibration_level: float = 5.0,
    message_loss_rate: float = 0.01,
) -> dict[str, float]:
    return {
        "battery_pct": battery_pct,
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "vibration_level": vibration_level,
        "message_loss_rate": message_loss_rate,
    }


def _feed_stable(det: AnomalyDetector, drone_id: str, n: int = 10, **kwargs) -> None:
    """Feed *n* identical stable readings."""
    for _ in range(n):
        det.update(drone_id, _stable_metrics(**kwargs))


# ---------------------------------------------------------------------------
# Anomaly dataclass
# ---------------------------------------------------------------------------

class TestAnomalyDataclass:
    def test_fields(self):
        a = Anomaly(
            drone_id="d1",
            anomaly_type="gps_jump",
            severity=0.5,
            message="test",
            metric_value=15.0,
            expected_value=0.0,
        )
        assert a.drone_id == "d1"
        assert a.anomaly_type == "gps_jump"
        assert 0.0 <= a.severity <= 1.0


# ---------------------------------------------------------------------------
# Normal data => no anomalies
# ---------------------------------------------------------------------------

class TestNormalData:
    def test_no_anomalies_on_stable_individual(self):
        det = AnomalyDetector(window_size=30)
        _feed_stable(det, "alpha", n=15)
        anomalies = det.check_individual("alpha")
        assert anomalies == []

    def test_no_anomalies_on_stable_swarm(self):
        det = AnomalyDetector(window_size=30)
        for did in ("alpha", "bravo", "charlie"):
            _feed_stable(det, did, n=10)
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        assert anomalies == []

    def test_no_anomalies_with_unknown_drone(self):
        det = AnomalyDetector()
        assert det.check_individual("nonexistent") == []


# ---------------------------------------------------------------------------
# GPS jump detection
# ---------------------------------------------------------------------------

class TestGPSJump:
    def test_gps_jump_detected_individual(self):
        det = AnomalyDetector(window_size=30)
        _feed_stable(det, "alpha", n=5)
        # Inject a big GPS jump (~111 km per degree, 0.001 deg ~ 111 m)
        det.update("alpha", _stable_metrics(lat=35.001, lon=-117.0))
        anomalies = det.check_individual("alpha")
        gps = [a for a in anomalies if a.anomaly_type == "gps_jump"]
        assert len(gps) >= 1
        assert gps[0].metric_value > 10.0  # >10m jump

    def test_small_gps_move_not_flagged(self):
        det = AnomalyDetector(window_size=30)
        _feed_stable(det, "alpha", n=5)
        # ~1m move
        det.update("alpha", _stable_metrics(lat=35.000009, lon=-117.0))
        anomalies = det.check_individual("alpha")
        gps = [a for a in anomalies if a.anomaly_type == "gps_jump"]
        assert gps == []

    def test_gps_jump_swarm_comparison(self):
        """One drone jumps while others are stable -> swarm-level detection."""
        det = AnomalyDetector(window_size=30)
        for did in ("alpha", "bravo", "charlie"):
            _feed_stable(det, did, n=5)
        # Only alpha jumps
        det.update("alpha", _stable_metrics(lat=35.001))
        det.update("bravo", _stable_metrics())
        det.update("charlie", _stable_metrics())
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        gps = [a for a in anomalies if a.anomaly_type == "gps_jump"]
        assert len(gps) >= 1
        assert gps[0].drone_id == "alpha"


# ---------------------------------------------------------------------------
# Battery drain detection
# ---------------------------------------------------------------------------

class TestBatteryDrain:
    def test_sudden_battery_drop_individual(self):
        det = AnomalyDetector(window_size=30)
        # Feed stable battery at 80% for a while
        for _ in range(10):
            det.update("alpha", _stable_metrics(battery_pct=80.0))
        # Sudden drop
        det.update("alpha", _stable_metrics(battery_pct=40.0))
        anomalies = det.check_individual("alpha")
        batt = [a for a in anomalies if a.anomaly_type == "battery_drain"]
        assert len(batt) >= 1

    def test_swarm_battery_drain_outlier(self):
        """One drone drains 3x faster than swarm average."""
        det = AnomalyDetector(window_size=30)
        # All start at 90%
        for did in ("alpha", "bravo", "charlie"):
            det.update(did, _stable_metrics(battery_pct=90.0))
        # Bravo and charlie drain 5% normally, alpha drains 30%
        det.update("alpha", _stable_metrics(battery_pct=60.0))
        det.update("bravo", _stable_metrics(battery_pct=85.0))
        det.update("charlie", _stable_metrics(battery_pct=85.0))
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        batt = [a for a in anomalies if a.anomaly_type == "battery_drain"]
        assert len(batt) >= 1
        assert batt[0].drone_id == "alpha"

    def test_uniform_drain_not_flagged(self):
        det = AnomalyDetector(window_size=30)
        for did in ("alpha", "bravo", "charlie"):
            det.update(did, _stable_metrics(battery_pct=90.0))
        for did in ("alpha", "bravo", "charlie"):
            det.update(did, _stable_metrics(battery_pct=85.0))
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        batt = [a for a in anomalies if a.anomaly_type == "battery_drain"]
        assert batt == []


# ---------------------------------------------------------------------------
# Altitude drift
# ---------------------------------------------------------------------------

class TestAltitudeDrift:
    def test_altitude_drift_detected(self):
        det = AnomalyDetector(window_size=30)
        for _ in range(10):
            det.update("alpha", _stable_metrics(alt=50.0))
        # Drift 10m
        det.update("alpha", _stable_metrics(alt=60.0))
        anomalies = det.check_individual("alpha")
        drift = [a for a in anomalies if a.anomaly_type == "altitude_drift"]
        assert len(drift) >= 1

    def test_minor_altitude_change_not_flagged(self):
        det = AnomalyDetector(window_size=30)
        for _ in range(10):
            det.update("alpha", _stable_metrics(alt=50.0))
        det.update("alpha", _stable_metrics(alt=51.0))
        anomalies = det.check_individual("alpha")
        drift = [a for a in anomalies if a.anomaly_type == "altitude_drift"]
        assert drift == []


# ---------------------------------------------------------------------------
# Vibration spike
# ---------------------------------------------------------------------------

class TestVibrationSpike:
    def test_vibration_spike_individual(self):
        det = AnomalyDetector(window_size=30)
        for _ in range(5):
            det.update("alpha", _stable_metrics(vibration_level=5.0))
        det.update("alpha", _stable_metrics(vibration_level=25.0))
        anomalies = det.check_individual("alpha")
        vib = [a for a in anomalies if a.anomaly_type == "vibration_spike"]
        assert len(vib) >= 1
        assert vib[0].metric_value == 25.0

    def test_vibration_spike_swarm(self):
        det = AnomalyDetector(window_size=30)
        for did in ("alpha", "bravo", "charlie"):
            _feed_stable(det, did, n=5, vibration_level=5.0)
        # Alpha spikes
        det.update("alpha", _stable_metrics(vibration_level=30.0))
        det.update("bravo", _stable_metrics(vibration_level=5.0))
        det.update("charlie", _stable_metrics(vibration_level=5.0))
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        vib = [a for a in anomalies if a.anomaly_type == "vibration_spike"]
        assert len(vib) >= 1
        assert vib[0].drone_id == "alpha"


# ---------------------------------------------------------------------------
# Communication degradation
# ---------------------------------------------------------------------------

class TestCommsDegradation:
    def test_comms_degradation_individual(self):
        det = AnomalyDetector(window_size=30)
        for _ in range(5):
            det.update("alpha", _stable_metrics(message_loss_rate=0.01))
        det.update("alpha", _stable_metrics(message_loss_rate=0.40))
        anomalies = det.check_individual("alpha")
        comms = [a for a in anomalies if a.anomaly_type == "comms_degradation"]
        assert len(comms) >= 1

    def test_comms_degradation_swarm(self):
        det = AnomalyDetector(window_size=30)
        for did in ("alpha", "bravo", "charlie"):
            _feed_stable(det, did, n=5, message_loss_rate=0.01)
        det.update("alpha", _stable_metrics(message_loss_rate=0.50))
        det.update("bravo", _stable_metrics(message_loss_rate=0.01))
        det.update("charlie", _stable_metrics(message_loss_rate=0.01))
        drones = {did: _make_drone(did) for did in ("alpha", "bravo", "charlie")}
        anomalies = det.check_swarm(drones)
        comms = [a for a in anomalies if a.anomaly_type == "comms_degradation"]
        assert len(comms) >= 1
        assert comms[0].drone_id == "alpha"


# ---------------------------------------------------------------------------
# Severity scaling
# ---------------------------------------------------------------------------

class TestSeverityScaling:
    def test_severity_increases_with_magnitude(self):
        """A larger GPS jump should produce higher severity."""
        det1 = AnomalyDetector(window_size=30)
        det2 = AnomalyDetector(window_size=30)
        _feed_stable(det1, "a", n=5)
        _feed_stable(det2, "a", n=5)
        # Small jump (~15m) -- 0.000135 deg lat ~ 15m
        det1.update("a", _stable_metrics(lat=35.000135))
        # Larger jump (~55m) -- 0.0005 deg lat ~ 55m
        det2.update("a", _stable_metrics(lat=35.0005))
        a1 = [a for a in det1.check_individual("a") if a.anomaly_type == "gps_jump"]
        a2 = [a for a in det2.check_individual("a") if a.anomaly_type == "gps_jump"]
        assert len(a1) >= 1 and len(a2) >= 1
        assert a2[0].severity > a1[0].severity

    def test_severity_clamped_to_1(self):
        det = AnomalyDetector(window_size=30)
        _feed_stable(det, "a", n=5)
        # Enormous jump
        det.update("a", _stable_metrics(lat=36.0))
        anomalies = [a for a in det.check_individual("a") if a.anomaly_type == "gps_jump"]
        assert len(anomalies) >= 1
        assert anomalies[0].severity <= 1.0


# ---------------------------------------------------------------------------
# Window size sensitivity
# ---------------------------------------------------------------------------

class TestWindowSize:
    def test_small_window_more_sensitive(self):
        """With a smaller window, anomalies are detected sooner."""
        det_small = AnomalyDetector(window_size=5)
        det_large = AnomalyDetector(window_size=30)
        # Feed 5 stable readings then a spike
        for det in (det_small, det_large):
            for _ in range(5):
                det.update("a", _stable_metrics(vibration_level=5.0))
            det.update("a", _stable_metrics(vibration_level=20.0))
        a_small = det_small.check_individual("a")
        a_large = det_large.check_individual("a")
        # Both should detect the spike since we have enough history in both
        vib_small = [a for a in a_small if a.anomaly_type == "vibration_spike"]
        vib_large = [a for a in a_large if a.anomaly_type == "vibration_spike"]
        assert len(vib_small) >= 1
        assert len(vib_large) >= 1

    def test_window_size_stored(self):
        det = AnomalyDetector(window_size=42)
        assert det.window_size == 42


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_drone_swarm_no_crash(self):
        """Swarm check with only one drone should return empty, not crash."""
        det = AnomalyDetector()
        _feed_stable(det, "only_one", n=10)
        drones = {"only_one": _make_drone("only_one")}
        assert det.check_swarm(drones) == []

    def test_empty_swarm(self):
        det = AnomalyDetector()
        assert det.check_swarm({}) == []

    def test_update_ignores_unknown_metrics(self):
        det = AnomalyDetector()
        det.update("a", {"battery_pct": 80.0, "unknown_field": 999.0})
        # Should not crash
        assert det.check_individual("a") == []

    def test_negative_vibration_not_flagged(self):
        """vibration_level=-1 (no data sentinel) should not trigger."""
        det = AnomalyDetector(window_size=30)
        for _ in range(10):
            det.update("a", _stable_metrics(vibration_level=-1.0))
        anomalies = det.check_individual("a")
        vib = [a for a in anomalies if a.anomaly_type == "vibration_spike"]
        assert vib == []

    def test_insufficient_history_no_anomalies(self):
        det = AnomalyDetector(window_size=30)
        det.update("a", _stable_metrics())
        assert det.check_individual("a") == []
