"""Automated Promotion Gate for RetailIQ YOLO models.

Evaluates candidate model performance against the active production baseline
to ensure no accuracy regressions on key retail classes and compliance with
inference latency SLAs before promotion.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromotionResult:
    """Outcome of promotion gate evaluation."""

    def __init__(
        self,
        approved: bool,
        reasons: List[str],
        comparison: Dict[str, Any],
    ) -> None:
        self.approved = approved
        self.reasons = reasons
        self.comparison = comparison

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reasons": self.reasons,
            "comparison": self.comparison,
        }


class PromotionGate:
    """Evaluates whether a candidate model qualifies for promotion to production."""

    def __init__(
        self,
        min_map50_improvement: float = 0.0,
        max_class_regression: float = 0.02,
        max_latency_ms: float = 35.0,
        critical_classes: Optional[List[str]] = None,
    ) -> None:
        self.min_map50_improvement = float(min_map50_improvement)
        self.max_class_regression = float(max_class_regression)
        self.max_latency_ms = float(max_latency_ms)
        self.critical_classes = critical_classes or ["person", "shelf", "product"]

    def evaluate(
        self,
        candidate_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]] = None,
    ) -> PromotionResult:
        """Compare candidate model against production baseline."""
        reasons: List[str] = []
        comparison: Dict[str, Any] = {
            "candidate": candidate_metrics,
            "baseline": baseline_metrics,
        }

        cand_overall = candidate_metrics.get("overall_metrics", {})
        cand_map50 = cand_overall.get("mAP50", 0.0)
        cand_latency = candidate_metrics.get("latency", {}).get("mean_latency_ms", 15.0)

        # 1. Latency Check
        if cand_latency > self.max_latency_ms:
            reasons.append(
                f"Candidate latency ({cand_latency:.2f}ms) exceeds SLA ceiling ({self.max_latency_ms:.2f}ms)"
            )

        # Baseline comparison
        if not baseline_metrics:
            # Baseline-free initial deployment checks
            if cand_map50 < 0.70:
                reasons.append(
                    f"Candidate mAP50 ({cand_map50:.3f}) below cold-start minimum 0.700"
                )
            approved = len(reasons) == 0
            if approved:
                reasons.append("Initial deployment approved: meets cold-start quality requirements.")
            return PromotionResult(approved=approved, reasons=reasons, comparison=comparison)

        base_overall = baseline_metrics.get("overall_metrics", {})
        base_map50 = base_overall.get("mAP50", 0.0)

        # 2. Overall mAP50 comparison
        map_delta = cand_map50 - base_map50
        comparison["map50_delta"] = round(map_delta, 4)

        if map_delta < self.min_map50_improvement:
            reasons.append(
                f"Candidate mAP50 ({cand_map50:.3f}) does not meet improvement threshold relative to baseline ({base_map50:.3f})"
            )

        # 3. Critical classes regression check
        cand_classes = candidate_metrics.get("class_metrics", {})
        base_classes = baseline_metrics.get("class_metrics", {})
        class_deltas: Dict[str, float] = {}

        for c in self.critical_classes:
            if c in base_classes and c in cand_classes:
                base_c_map = base_classes[c].get("mAP50", 0.0)
                cand_c_map = cand_classes[c].get("mAP50", 0.0)
                delta = cand_c_map - base_c_map
                class_deltas[c] = round(delta, 4)

                if delta < -self.max_class_regression:
                    reasons.append(
                        f"Critical class '{c}' regressed by {-delta:.3f} (max allowed: {self.max_class_regression:.3f})"
                    )

        comparison["class_deltas"] = class_deltas

        approved = len(reasons) == 0
        if approved:
            reasons.append("Candidate successfully passed all quality and latency promotion gates.")

        return PromotionResult(approved=approved, reasons=reasons, comparison=comparison)
