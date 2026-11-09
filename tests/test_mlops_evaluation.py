"""Unit tests for MLOps experiment tracking and evaluation."""
import json
from pathlib import Path
import pytest

from mlops.tracking.tracker import ExperimentTracker
from mlops.evaluation.evaluator import ModelEvaluator


def test_experiment_tracker_lifecycle(tmp_path: Path):
    tracker = ExperimentTracker(tracking_dir=str(tmp_path / "runs"))

    # Start run
    run_id = tracker.start_run(
        experiment_name="test_experiment",
        params={"lr": 0.01, "batch": 16},
        tags={"dataset": "retail_v1"},
    )
    assert run_id.startswith("run_")

    # Log metrics
    tracker.log_metrics(run_id, {"mAP50": 0.85, "precision": 0.88})

    # End run
    run_data = tracker.end_run(
        run_id,
        status="COMPLETED",
        artifacts={"weights": "/tmp/best.pt"},
    )
    assert run_data["status"] == "COMPLETED"
    assert run_data["metrics"]["mAP50"] == 0.85
    assert run_data["artifacts"]["weights"] == "/tmp/best.pt"

    # Query run
    retrieved = tracker.get_run(run_id)
    assert retrieved is not None
    assert retrieved["run_id"] == run_id


def test_experiment_tracker_best_run(tmp_path: Path):
    tracker = ExperimentTracker(tracking_dir=str(tmp_path / "runs"))

    r1 = tracker.start_run("retail_exp")
    tracker.log_metrics(r1, {"mAP50": 0.82})
    tracker.end_run(r1)

    r2 = tracker.start_run("retail_exp")
    tracker.log_metrics(r2, {"mAP50": 0.91})
    tracker.end_run(r2)

    best = tracker.get_best_run(metric="mAP50", experiment_name="retail_exp")
    assert best is not None
    assert best["run_id"] == r2
    assert best["metrics"]["mAP50"] == 0.91


def test_model_evaluator_dry_run(tmp_path: Path):
    eval_dir = tmp_path / "evaluations"
    evaluator = ModelEvaluator(
        model_path="dummy_yolo.pt",
        data_yaml="dummy_data.yaml",
        output_dir=str(eval_dir),
    )

    report = evaluator.evaluate(dry_run=True)
    assert report["status"] == "SUCCESS"
    assert "eval_id" in report
    assert report["overall_metrics"]["mAP50"] > 0.8
    assert "person" in report["class_metrics"]
    assert "mean_latency_ms" in report["latency"]

    # Check persisted file
    report_file = eval_dir / f"{report['eval_id']}.json"
    assert report_file.exists()
    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["eval_id"] == report["eval_id"]
