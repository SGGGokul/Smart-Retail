"""Model Performance and Data Drift Monitoring for RetailIQ.

Tracks inference latency, prediction confidence distributions, class frequency shifts,
empty detection rates, and image brightness drift.
"""
from __future__ import annotations

import collections
import datetime
import json
import logging
import math
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class DriftMonitor:
    """Monitors operational inference metrics and statistical data drift."""

    def __init__(
        self,
        baseline_class_dist: Optional[Dict[str, float]] = None,
        min_confidence_floor: float = 0.50,
        max_empty_detection_rate: float = 0.40,
        max_mean_latency_ms: float = 35.0,
        window_size: int = 100,
        reports_dir: str = "mlops/artifacts/monitoring",
    ) -> None:
        self.baseline_class_dist = baseline_class_dist or {
            "person": 0.60,
            "product": 0.25,
            "shelf": 0.15,
        }
        self.min_confidence_floor = min_confidence_floor
        self.max_empty_detection_rate = max_empty_detection_rate
        self.max_mean_latency_ms = max_mean_latency_ms
        self.window_size = window_size
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Sliding window queues
        self.latencies: Deque[float] = collections.deque(maxlen=window_size)
        self.confidences: Deque[float] = collections.deque(maxlen=window_size)
        self.detection_counts: Deque[int] = collections.deque(maxlen=window_size)
        self.class_counts: collections.Counter = collections.Counter()
        self.total_requests: int = 0
        self.error_count: int = 0

    def record_inference(
        self,
        latency_ms: float,
        detections: List[Dict[str, Any]],
        is_error: bool = False,
    ) -> None:
        """Record a single inference execution event."""
        self.total_requests += 1
        if is_error:
            self.error_count += 1
            return

        self.latencies.append(latency_ms)
        num_dets = len(detections)
        self.detection_counts.append(num_dets)

        for det in detections:
            conf = det.get("confidence", 0.0)
            self.confidences.append(conf)
            cls_name = det.get("class_name", "unknown")
            self.class_counts[cls_name] += 1

    def compute_drift_report(self) -> Dict[str, Any]:
        """Compute statistical drift indicators and evaluate alert thresholds."""
        alerts: List[str] = []

        # 1. Latency metrics
        count_lat = len(self.latencies)
        mean_latency = sum(self.latencies) / count_lat if count_lat > 0 else 0.0
        sorted_lat = sorted(self.latencies)
        p95_latency = sorted_lat[int(math.ceil(0.95 * count_lat)) - 1] if count_lat > 0 else 0.0

        if mean_latency > self.max_mean_latency_ms:
            alerts.append(
                f"Latency drift: Mean latency ({mean_latency:.2f}ms) exceeds SLA ceiling ({self.max_mean_latency_ms:.2f}ms)"
            )

        # 2. Confidence floor check
        count_conf = len(self.confidences)
        mean_conf = sum(self.confidences) / count_conf if count_conf > 0 else 0.0
        if count_conf > 10 and mean_conf < self.min_confidence_floor:
            alerts.append(
                f"Confidence drift: Mean confidence ({mean_conf:.3f}) fell below minimum floor ({self.min_confidence_floor:.3f})"
            )

        # 3. Empty detection rate
        count_dets = len(self.detection_counts)
        empty_count = sum(1 for c in self.detection_counts if c == 0)
        empty_rate = empty_count / count_dets if count_dets > 0 else 0.0

        if count_dets > 10 and empty_rate > self.max_empty_detection_rate:
            alerts.append(
                f"Empty detection anomaly: {empty_rate:.1%} of recent inferences yielded zero detections"
            )

        # 4. Class distribution shift (Cosine similarity or Total Variation Distance)
        total_cls = sum(self.class_counts.values())
        observed_dist: Dict[str, float] = {}
        tvd: float = 0.0

        if total_cls > 20:
            for cls_name, count in self.class_counts.items():
                observed_dist[cls_name] = round(count / total_cls, 4)

            # Total variation distance against baseline
            all_classes = set(self.baseline_class_dist.keys()) | set(observed_dist.keys())
            for c in all_classes:
                base_prob = self.baseline_class_dist.get(c, 0.0)
                obs_prob = observed_dist.get(c, 0.0)
                tvd += abs(obs_prob - base_prob)
            tvd = 0.5 * tvd

            if tvd > 0.35:
                alerts.append(
                    f"Class distribution drift: Total Variation Distance ({tvd:.3f}) exceeds threshold 0.350"
                )

        report = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_requests": self.total_requests,
            "error_count": self.error_count,
            "error_rate": round(self.error_count / max(self.total_requests, 1), 4),
            "sample_size": count_lat,
            "mean_latency_ms": round(mean_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "mean_confidence": round(mean_conf, 4),
            "empty_detection_rate": round(empty_rate, 4),
            "class_distribution": observed_dist,
            "class_tvd": round(tvd, 4),
            "drift_detected": len(alerts) > 0,
            "alerts": alerts,
        }

        # Persist report
        report_file = self.reports_dir / "latest_drift_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report
