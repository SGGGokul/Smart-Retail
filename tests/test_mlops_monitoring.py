"""Unit tests for MLOps drift monitoring and reporting."""
from pathlib import Path
import pytest

from mlops.monitoring.drift_detector import DriftMonitor


def test_drift_monitor_healthy_stream(tmp_path: Path):
    monitor = DriftMonitor(reports_dir=str(tmp_path / "monitoring"))

    # Record 20 normal inferences
    for _ in range(25):
        monitor.record_inference(
            latency_ms=16.0,
            detections=[
                {"class_name": "person", "confidence": 0.88},
                {"class_name": "product", "confidence": 0.79},
            ],
        )

    report = monitor.compute_drift_report()
    assert report["drift_detected"] is False
    assert len(report["alerts"]) == 0
    assert report["mean_latency_ms"] == 16.0
    assert report["mean_confidence"] > 0.80
    assert (tmp_path / "monitoring" / "latest_drift_report.json").exists()


def test_drift_monitor_latency_alert(tmp_path: Path):
    monitor = DriftMonitor(
        max_mean_latency_ms=25.0,
        reports_dir=str(tmp_path / "monitoring"),
    )

    for _ in range(15):
        monitor.record_inference(latency_ms=50.0, detections=[{"class_name": "person", "confidence": 0.9}])

    report = monitor.compute_drift_report()
    assert report["drift_detected"] is True
    assert any("Latency drift" in a for a in report["alerts"])


def test_drift_monitor_confidence_drift(tmp_path: Path):
    monitor = DriftMonitor(
        min_confidence_floor=0.70,
        reports_dir=str(tmp_path / "monitoring"),
    )

    for _ in range(20):
        monitor.record_inference(latency_ms=15.0, detections=[{"class_name": "person", "confidence": 0.45}])

    report = monitor.compute_drift_report()
    assert report["drift_detected"] is True
    assert any("Confidence drift" in a for a in report["alerts"])


def test_drift_monitor_empty_detection_anomaly(tmp_path: Path):
    monitor = DriftMonitor(
        max_empty_detection_rate=0.30,
        reports_dir=str(tmp_path / "monitoring"),
    )

    for _ in range(15):
        monitor.record_inference(latency_ms=15.0, detections=[])

    report = monitor.compute_drift_report()
    assert report["drift_detected"] is True
    assert any("Empty detection anomaly" in a for a in report["alerts"])
