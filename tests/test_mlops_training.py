"""Unit tests for MLOps YOLO training pipeline."""
import json
from pathlib import Path
import pytest
import random

from mlops.training.train import (
    TrainingConfig,
    YOLOTrainingPipeline,
    build_parser,
    set_seed,
)


def test_training_config_valid(tmp_path: Path):
    data_file = tmp_path / "dataset.yaml"
    data_file.write_text("names: {0: person}")

    config = TrainingConfig(
        data=str(data_file),
        model="yolo11n.pt",
        epochs=10,
        imgsz=640,
        batch=16,
        lr0=0.01,
        seed=123,
        device="cpu",
    )
    assert config.epochs == 10
    assert config.imgsz == 640
    assert config.seed == 123
    assert "yolo11n_retail_" in config.name


def test_training_config_invalid_parameters():
    with pytest.raises(ValueError, match="multiple of 32"):
        TrainingConfig(data="dataset.yaml", imgsz=500)

    with pytest.raises(ValueError, match="Epochs must be >= 1"):
        TrainingConfig(data="dataset.yaml", epochs=0)

    with pytest.raises(ValueError, match="Batch size must be >= 1"):
        TrainingConfig(data="dataset.yaml", batch=-1)

    with pytest.raises(ValueError, match="learning rate"):
        TrainingConfig(data="dataset.yaml", lr0=0.0)


def test_deterministic_seed():
    set_seed(42)
    val1 = [random.random() for _ in range(5)]

    set_seed(42)
    val2 = [random.random() for _ in range(5)]

    assert val1 == val2


def test_pipeline_dry_run_generates_manifest_and_artifacts(tmp_path: Path):
    project_dir = tmp_path / "experiments"
    config = TrainingConfig(
        data="mock_dataset.yaml",
        model="yolo11n.pt",
        epochs=1,
        imgsz=640,
        batch=4,
        project=str(project_dir),
        name="test_run_01",
    )

    pipeline = YOLOTrainingPipeline(config)
    manifest = pipeline.run(dry_run=True)

    assert manifest["status"] == "completed"
    assert manifest["run_id"] == "test_run_01"
    assert "duration_seconds" in manifest

    weights_dir = project_dir / "test_run_01" / "weights"
    assert (weights_dir / "best.pt").exists()
    assert (weights_dir / "last.pt").exists()

    manifest_file = project_dir / "test_run_01" / "training_manifest.json"
    assert manifest_file.exists()
    with open(manifest_file, "r", encoding="utf-8") as f:
        saved_manifest = json.load(f)
    assert saved_manifest["run_id"] == "test_run_01"
    assert saved_manifest["metrics"]["mAP50"] > 0


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["--data", "retail.yaml"])
    assert args.data == "retail.yaml"
    assert args.model == "yolo11n.pt"
    assert args.epochs == 50
    assert args.imgsz == 640
    assert args.device == "cpu"
    assert not args.dry_run
