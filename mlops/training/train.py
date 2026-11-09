"""YOLO11n Training Pipeline for RetailIQ.

Provides reproducible training configuration, deterministic seeding,
parameter validation, and execution wrapper for Ultralytics YOLO.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
from pathlib import Path
import random
import subprocess
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def set_seed(seed: int = 42) -> None:
    """Set deterministic seeds across python, numpy, and torch."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass

    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except Exception:
        pass


def get_git_commit_sha() -> Optional[str]:
    """Retrieve current Git commit SHA if within a git repo."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return out
    except Exception:
        return None


class TrainingConfig:
    """Validated training configuration."""

    def __init__(
        self,
        data: str,
        model: str = "yolo11n.pt",
        epochs: int = 50,
        imgsz: int = 640,
        batch: int = 16,
        lr0: float = 0.01,
        seed: int = 42,
        device: str = "cpu",
        augment: bool = True,
        project: str = "mlops/artifacts/experiments",
        name: Optional[str] = None,
        deterministic: bool = True,
    ) -> None:
        self.data = str(data)
        self.model = str(model)
        self.epochs = int(epochs)
        self.imgsz = int(imgsz)
        self.batch = int(batch)
        self.lr0 = float(lr0)
        self.seed = int(seed)
        self.device = str(device)
        self.augment = bool(augment)
        self.project = str(project)
        self.deterministic = bool(deterministic)

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.name = name or f"yolo11n_retail_{timestamp}"

        self.validate()

    def validate(self) -> None:
        """Validate parameter ranges and paths."""
        if not self.data:
            raise ValueError("Dataset path 'data' cannot be empty.")
        if self.epochs < 1:
            raise ValueError(f"Epochs must be >= 1, got {self.epochs}")
        if self.imgsz < 32 or self.imgsz % 32 != 0:
            raise ValueError(f"Image size must be a multiple of 32 >= 32, got {self.imgsz}")
        if self.batch < 1:
            raise ValueError(f"Batch size must be >= 1, got {self.batch}")
        if self.lr0 <= 0.0 or self.lr0 > 1.0:
            raise ValueError(f"Initial learning rate lr0 must be in (0, 1], got {self.lr0}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "model": self.model,
            "epochs": self.epochs,
            "imgsz": self.imgsz,
            "batch": self.batch,
            "lr0": self.lr0,
            "seed": self.seed,
            "device": self.device,
            "augment": self.augment,
            "project": self.project,
            "name": self.name,
            "deterministic": self.deterministic,
        }


class YOLOTrainingPipeline:
    """Manages the lifecycle of a YOLO training execution."""

    def __init__(self, config: TrainingConfig) -> None:
        self.config = config
        self.run_dir = Path(config.project) / config.name

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute training and generate execution metadata."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        set_seed(self.config.seed)

        start_time = datetime.datetime.now(datetime.timezone.utc)
        git_sha = get_git_commit_sha()

        manifest: Dict[str, Any] = {
            "run_id": self.config.name,
            "git_commit": git_sha,
            "config": self.config.to_dict(),
            "start_time": start_time.isoformat(),
            "status": "pending",
            "weights": {},
            "metrics": {},
        }

        if dry_run:
            logger.info("Executing dry-run training mode.")
            # Simulate output structure for CI testing and dry runs
            weights_dir = self.run_dir / "weights"
            weights_dir.mkdir(parents=True, exist_ok=True)
            best_weight = weights_dir / "best.pt"
            last_weight = weights_dir / "last.pt"
            best_weight.write_text("dry-run-yolo11n-best-model", encoding="utf-8")
            last_weight.write_text("dry-run-yolo11n-last-model", encoding="utf-8")

            manifest["status"] = "completed"
            manifest["weights"] = {
                "best": str(best_weight),
                "last": str(last_weight),
            }
            manifest["metrics"] = {
                "mAP50": 0.885,
                "mAP50-95": 0.652,
                "precision": 0.891,
                "recall": 0.843,
            }
        else:
            try:
                from ultralytics import YOLO

                model = YOLO(self.config.model)
                results = model.train(
                    data=self.config.data,
                    epochs=self.config.epochs,
                    imgsz=self.config.imgsz,
                    batch=self.config.batch,
                    lr0=self.config.lr0,
                    seed=self.config.seed,
                    device=self.config.device,
                    augment=self.config.augment,
                    project=self.config.project,
                    name=self.config.name,
                    deterministic=self.config.deterministic,
                    exist_ok=True,
                )

                weights_dir = self.run_dir / "weights"
                best_weight = weights_dir / "best.pt"
                last_weight = weights_dir / "last.pt"

                manifest["status"] = "completed"
                manifest["weights"] = {
                    "best": str(best_weight) if best_weight.exists() else None,
                    "last": str(last_weight) if last_weight.exists() else None,
                }
                if hasattr(results, "results_dict") and isinstance(results.results_dict, dict):
                    manifest["metrics"] = results.results_dict
            except Exception as exc:
                manifest["status"] = "failed"
                manifest["error"] = str(exc)
                logger.error("Training failed: %s", exc, exc_info=True)
                raise

        end_time = datetime.datetime.now(datetime.timezone.utc)
        manifest["end_time"] = end_time.isoformat()
        manifest["duration_seconds"] = (end_time - start_time).total_seconds()

        manifest_path = self.run_dir / "training_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="RetailIQ YOLO11n Reproducible Training Pipeline"
    )
    parser.add_argument("--data", type=str, required=True, help="Path to dataset YAML file")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Base model checkpoint")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (multiple of 32)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu, cuda, 0, etc.)")
    parser.add_argument("--project", type=str, default="mlops/artifacts/experiments", help="Project dir")
    parser.add_argument("--name", type=str, default=None, help="Run name")
    parser.add_argument("--no-augment", action="store_true", help="Disable data augmentation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate training for CI or smoke tests")
    return parser


def main() -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = TrainingConfig(
            data=args.data,
            model=args.model,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            lr0=args.lr0,
            seed=args.seed,
            device=args.device,
            augment=not args.no_augment,
            project=args.project,
            name=args.name,
        )
        pipeline = YOLOTrainingPipeline(config)
        manifest = pipeline.run(dry_run=args.dry_run)
        print(f"Training finished: {manifest['status']}. Artifacts at: {pipeline.run_dir}")
        return 0 if manifest["status"] == "completed" else 1
    except Exception as exc:
        print(f"Error during training pipeline execution: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
