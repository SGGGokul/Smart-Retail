"""Experiment Tracking for RetailIQ MLOps.

Provides experiment run logging, metrics tracking, run indexing,
and comparison utilities.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """Manages experiment runs, metrics logging, and experiment querying."""

    def __init__(self, tracking_dir: str = "mlops/artifacts/runs") -> None:
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.tracking_dir / "experiments_index.json"
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self.index_file.exists():
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump({"runs": []}, f, indent=2)

    def start_run(
        self,
        experiment_name: str,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> str:
        """Initialize a new experiment run."""
        run_id = run_id or f"run_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = self.tracking_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        run_data: Dict[str, Any] = {
            "run_id": run_id,
            "experiment_name": experiment_name,
            "status": "RUNNING",
            "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "end_time": None,
            "params": params or {},
            "tags": tags or {},
            "metrics": {},
            "artifacts": {},
        }

        with open(run_dir / "run.json", "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)

        self._update_index(run_data)
        return run_id

    def log_metrics(self, run_id: str, metrics: Dict[str, float]) -> None:
        """Log or update scalar metrics for a run."""
        run_file = self.tracking_dir / run_id / "run.json"
        if not run_file.exists():
            raise FileNotFoundError(f"Run {run_id} not found at {run_file}")

        with open(run_file, "r", encoding="utf-8") as f:
            run_data = json.load(f)

        run_data["metrics"].update(metrics)

        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)

        self._update_index(run_data)

    def end_run(
        self,
        run_id: str,
        status: str = "COMPLETED",
        artifacts: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Finalize an experiment run."""
        run_file = self.tracking_dir / run_id / "run.json"
        if not run_file.exists():
            raise FileNotFoundError(f"Run {run_id} not found at {run_file}")

        with open(run_file, "r", encoding="utf-8") as f:
            run_data = json.load(f)

        run_data["status"] = status
        run_data["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if artifacts:
            run_data["artifacts"].update(artifacts)

        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)

        self._update_index(run_data)
        return run_data

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve run data by ID."""
        run_file = self.tracking_dir / run_id / "run.json"
        if not run_file.exists():
            return None
        with open(run_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_runs(self, experiment_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tracked runs, optionally filtered by experiment name."""
        with open(self.index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        runs = index.get("runs", [])
        if experiment_name:
            runs = [r for r in runs if r.get("experiment_name") == experiment_name]
        return runs

    def get_best_run(
        self,
        metric: str = "mAP50",
        higher_is_better: bool = True,
        experiment_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find the run with the best value for a given metric."""
        runs = self.list_runs(experiment_name=experiment_name)
        eligible = [r for r in runs if metric in r.get("metrics", {})]
        if not eligible:
            return None

        return max(
            eligible,
            key=lambda r: r["metrics"][metric] if higher_is_better else -r["metrics"][metric],
        )

    def _update_index(self, run_data: Dict[str, Any]) -> None:
        """Update summary index entry."""
        with open(self.index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        runs = index.get("runs", [])
        updated = False
        for i, existing in enumerate(runs):
            if existing.get("run_id") == run_data.get("run_id"):
                runs[i] = run_data
                updated = True
                break
        if not updated:
            runs.append(run_data)

        index["runs"] = runs
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
