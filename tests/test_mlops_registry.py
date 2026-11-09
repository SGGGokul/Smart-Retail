"""Unit tests for MLOps Model Registry and Promotion Gates."""
from pathlib import Path
import pytest

from mlops.registry.registry import ModelRegistry, compute_sha256
from mlops.evaluation.promotion_gate import PromotionGate


def test_model_registry_registration_and_checksum(tmp_path: Path):
    registry = ModelRegistry(registry_dir=str(tmp_path / "registry"))

    weight_file = tmp_path / "model_weights.pt"
    weight_file.write_bytes(b"mock_weights_binary_data")

    meta = registry.register_model(
        version="v1.0.0",
        weights_path=weight_file,
        metrics={"mAP50": 0.88},
        stage="candidate",
    )

    assert meta["version"] == "v1.0.0"
    assert meta["stage"] == "candidate"
    assert meta["sha256"] == compute_sha256(weight_file)

    # Prevent duplicate
    with pytest.raises(ValueError, match="already registered"):
        registry.register_model(
            version="v1.0.0",
            weights_path=weight_file,
        )


def test_model_registry_stage_transitions_and_rollback(tmp_path: Path):
    registry = ModelRegistry(registry_dir=str(tmp_path / "registry"))

    w1 = tmp_path / "w1.pt"
    w1.write_bytes(b"w1")
    registry.register_model("v1.0.0", w1)

    w2 = tmp_path / "w2.pt"
    w2.write_bytes(b"w2")
    registry.register_model("v1.1.0", w2)

    # Promote v1.0.0 to production
    registry.transition_stage("v1.0.0", "production")
    active = registry.get_active_model("production")
    assert active["version"] == "v1.0.0"

    # Promote v1.1.0 to production
    registry.transition_stage("v1.1.0", "production")
    active = registry.get_active_model("production")
    assert active["version"] == "v1.1.0"
    assert registry.get_model("v1.0.0")["stage"] == "archived"

    # Rollback to v1.0.0
    rolled_back = registry.rollback_production()
    assert rolled_back["version"] == "v1.0.0"
    assert rolled_back["stage"] == "production"
    assert registry.get_model("v1.1.0")["stage"] == "archived"


def test_promotion_gate_cold_start():
    gate = PromotionGate()
    candidate = {
        "overall_metrics": {"mAP50": 0.85},
        "latency": {"mean_latency_ms": 15.0},
    }
    result = gate.evaluate(candidate, baseline_metrics=None)
    assert result.approved is True


def test_promotion_gate_improvement():
    gate = PromotionGate()
    baseline = {
        "overall_metrics": {"mAP50": 0.85},
        "class_metrics": {
            "person": {"mAP50": 0.90},
            "shelf": {"mAP50": 0.82},
            "product": {"mAP50": 0.80},
        },
        "latency": {"mean_latency_ms": 16.0},
    }
    candidate = {
        "overall_metrics": {"mAP50": 0.88},
        "class_metrics": {
            "person": {"mAP50": 0.91},
            "shelf": {"mAP50": 0.85},
            "product": {"mAP50": 0.83},
        },
        "latency": {"mean_latency_ms": 15.5},
    }
    result = gate.evaluate(candidate, baseline_metrics=baseline)
    assert result.approved is True


def test_promotion_gate_rejects_regression():
    gate = PromotionGate(max_class_regression=0.02)
    baseline = {
        "overall_metrics": {"mAP50": 0.85},
        "class_metrics": {
            "person": {"mAP50": 0.90},
            "shelf": {"mAP50": 0.85},
        },
        "latency": {"mean_latency_ms": 15.0},
    }

    # Case 1: Overall mAP50 dropped
    cand_lower_map = {
        "overall_metrics": {"mAP50": 0.82},
        "class_metrics": {
            "person": {"mAP50": 0.90},
            "shelf": {"mAP50": 0.85},
        },
        "latency": {"mean_latency_ms": 15.0},
    }
    res1 = gate.evaluate(cand_lower_map, baseline_metrics=baseline)
    assert res1.approved is False
    assert any("mAP50" in r for r in res1.reasons)

    # Case 2: Person class dropped > 2%
    cand_regressed_class = {
        "overall_metrics": {"mAP50": 0.86},
        "class_metrics": {
            "person": {"mAP50": 0.87},  # dropped 0.03
            "shelf": {"mAP50": 0.89},
        },
        "latency": {"mean_latency_ms": 15.0},
    }
    res2 = gate.evaluate(cand_regressed_class, baseline_metrics=baseline)
    assert res2.approved is False
    assert any("person" in r for r in res2.reasons)

    # Case 3: Latency exceeds threshold
    cand_slow = {
        "overall_metrics": {"mAP50": 0.88},
        "class_metrics": {
            "person": {"mAP50": 0.91},
            "shelf": {"mAP50": 0.86},
        },
        "latency": {"mean_latency_ms": 45.0},
    }
    res3 = gate.evaluate(cand_slow, baseline_metrics=baseline)
    assert res3.approved is False
    assert any("latency" in r.lower() for r in res3.reasons)
