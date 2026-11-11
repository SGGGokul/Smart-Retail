"""Model Registry for RetailIQ MLOps.

Maintains model versioning, lifecycle stages (candidate, staging, production, archived, rejected),
checksum verification, and rollback history.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_STAGES = {"candidate", "staging", "production", "archived", "rejected"}


def compute_sha256(filepath: str | Path) -> str:
    """Calculate SHA256 checksum for a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ModelRegistry:
    """Model Registry managing registered models, version metadata, and production deployments."""

    def __init__(self, registry_dir: str = "mlops/artifacts/registry") -> None:
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir = self.registry_dir / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_file = self.registry_dir / "catalog.json"
        self._ensure_catalog()

    def _ensure_catalog(self) -> None:
        if not self.catalog_file.exists():
            initial_data = {
                "active_production": None,
                "previous_production": None,
                "models": {},
            }
            with open(self.catalog_file, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    def _load_catalog(self) -> Dict[str, Any]:
        with open(self.catalog_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_catalog(self, catalog: Dict[str, Any]) -> None:
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)

    def register_model(
        self,
        version: str,
        weights_path: str | Path,
        metrics: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        stage: str = "candidate",
        description: str = "",
    ) -> Dict[str, Any]:
        """Register a new model checkpoint into the registry."""
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Model weights not found at {weights_path}")

        if stage not in ALLOWED_STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of {ALLOWED_STAGES}")

        catalog = self._load_catalog()
        if version in catalog["models"]:
            raise ValueError(f"Model version '{version}' is already registered.")

        # Compute SHA256 checksum
        checksum = compute_sha256(weights_path)

        # Copy weight file to versioned registry directory
        target_file = self.models_dir / f"{version}_{weights_path.name}"
        shutil.copy2(weights_path, target_file)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata: Dict[str, Any] = {
            "version": version,
            "weights_path": str(target_file),
            "sha256": checksum,
            "stage": stage,
            "metrics": metrics or {},
            "parameters": parameters or {},
            "run_id": run_id,
            "description": description,
            "created_at": now,
            "updated_at": now,
        }

        catalog["models"][version] = metadata
        self._save_catalog(catalog)

        # If registered directly to production
        if stage == "production":
            self.transition_stage(version, "production")

        logger.info("Successfully registered model version %s (stage: %s)", version, stage)
        return metadata

    def transition_stage(self, version: str, target_stage: str) -> Dict[str, Any]:
        """Transition a model to a target lifecycle stage."""
        if target_stage not in ALLOWED_STAGES:
            raise ValueError(f"Invalid stage '{target_stage}'. Must be one of {ALLOWED_STAGES}")

        catalog = self._load_catalog()
        if version not in catalog["models"]:
            raise KeyError(f"Model version '{version}' not found in registry.")

        model = catalog["models"][version]
        current_stage = model["stage"]

        if target_stage == "production":
            current_prod = catalog.get("active_production")
            if current_prod and current_prod != version:
                # Save previous production for atomic rollback
                catalog["previous_production"] = current_prod
                if current_prod in catalog["models"]:
                    catalog["models"][current_prod]["stage"] = "archived"
                    catalog["models"][current_prod]["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            catalog["active_production"] = version

        model["stage"] = target_stage
        model["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        catalog["models"][version] = model
        self._save_catalog(catalog)

        logger.info("Model %s transitioned from %s to %s", version, current_stage, target_stage)
        return model

    def rollback_production(self) -> Optional[Dict[str, Any]]:
        """Atomically rollback production model to the previous production version."""
        catalog = self._load_catalog()
        current_prod = catalog.get("active_production")
        prev_prod = catalog.get("previous_production")

        if not prev_prod or prev_prod not in catalog["models"]:
            logger.warning("No previous production model available to rollback.")
            return None

        # Archive current production
        if current_prod and current_prod in catalog["models"]:
            catalog["models"][current_prod]["stage"] = "archived"
            catalog["models"][current_prod]["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Re-activate previous production
        catalog["models"][prev_prod]["stage"] = "production"
        catalog["models"][prev_prod]["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        catalog["active_production"] = prev_prod
        catalog["previous_production"] = current_prod  # swap for multi-rollback capability

        self._save_catalog(catalog)
        logger.info("Rolled back production model from %s to %s", current_prod, prev_prod)
        return catalog["models"][prev_prod]

    def get_model(self, version: str) -> Optional[Dict[str, Any]]:
        """Retrieve model metadata by version."""
        catalog = self._load_catalog()
        return catalog["models"].get(version)

    def get_active_model(self, stage: str = "production") -> Optional[Dict[str, Any]]:
        """Retrieve the currently active model for a stage."""
        catalog = self._load_catalog()
        if stage == "production":
            prod_ver = catalog.get("active_production")
            return catalog["models"].get(prod_ver) if prod_ver else None

        for m in catalog["models"].values():
            if m["stage"] == stage:
                return m
        return None

    def list_models(self, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        """List registered models, optionally filtered by stage."""
        catalog = self._load_catalog()
        models = list(catalog["models"].values())
        if stage:
            models = [m for m in models if m["stage"] == stage]
        return models
