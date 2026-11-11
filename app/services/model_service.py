import hashlib
import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def compute_sha256(filepath: Path) -> Optional[str]:
    """Calculate SHA256 checksum for a file if it exists."""
    if not filepath.is_file():
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ModelService:
    """Manages YOLO11n and MLOps versioned model lifecycle."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        registry_dir: Optional[Path] = None,
        device: Optional[str] = None,
    ) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()
        self._custom_model_path = model_path
        self.registry_dir = registry_dir or self.settings.MODEL_REGISTRY_DIR
        self.device = device or self.settings.MODEL_DEVICE
        self._model: Optional[Any] = None

        self.model_path: Path
        self.version: str = "baseline-yolo11n"
        self.stage: str = "baseline"
        self.expected_sha256: Optional[str] = None

        self._resolve_model()

    def _resolve_model(self) -> None:
        """Resolve active model weights from registry or fallback baseline."""
        if self._custom_model_path is not None:
            self.model_path = self._custom_model_path
            self.version = "custom"
            self.stage = "custom"
            return

        # Check if registry has an active production model
        if self.settings.MODEL_USE_REGISTRY and self.registry_dir:
            catalog_file = Path(self.registry_dir) / "catalog.json"
            if catalog_file.is_file():
                try:
                    import json
                    with open(catalog_file, "r", encoding="utf-8") as f:
                        catalog = json.load(f)
                    active_ver = catalog.get("active_production")
                    if active_ver and active_ver in catalog.get("models", {}):
                        model_meta = catalog["models"][active_ver]
                        candidate_path = Path(model_meta["weights_path"])
                        if candidate_path.is_file():
                            self.model_path = candidate_path
                            self.version = active_ver
                            self.stage = model_meta.get("stage", "production")
                            self.expected_sha256 = model_meta.get("sha256")
                            logger.info(
                                "Resolved active production model %s from registry: %s",
                                self.version,
                                self.model_path,
                            )
                            return
                except Exception as exc:
                    logger.warning("Could not resolve model from registry: %s. Using default baseline.", exc)

        # Fallback to configured default model path
        self.model_path = Path(self.settings.MODEL_PATH)
        self.version = "baseline-yolo11n"
        self.stage = "baseline"

    def check_weights_exist(self) -> bool:
        """Verify whether model weights file exists on disk."""
        return self.model_path.is_file()

    def validate_checksum(self) -> bool:
        """Verify checksum integrity if expected checksum is recorded."""
        if not self.expected_sha256:
            return True
        actual = compute_sha256(self.model_path)
        return actual == self.expected_sha256

    @staticmethod
    def is_ml_available() -> bool:
        """Check if ultralytics and torch are installed without importing them globally."""
        has_ultra = importlib.util.find_spec("ultralytics") is not None
        has_torch = importlib.util.find_spec("torch") is not None
        return has_ultra and has_torch

    def get_model_info(self) -> Dict[str, Any]:
        """Return non-intrusive metadata about model file, version, and runtime availability."""
        exists = self.check_weights_exist()
        size = self.model_path.stat().st_size if exists else 0
        checksum = compute_sha256(self.model_path) if exists else None

        return {
            "model_path": str(self.model_path),
            "weights_exist": exists,
            "weights_size_bytes": size,
            "is_loaded": self._model is not None,
            "target_class": "person (COCO 0)",
            "ml_dependencies_installed": self.is_ml_available(),
            "version": self.version,
            "stage": self.stage,
            "device": self.device,
            "sha256": checksum,
            "checksum_verified": self.validate_checksum() if exists else False,
        }

    def load_model(self, device: Optional[str] = None) -> Any:
        """Lazily load YOLO11n weights into memory once."""
        if self._model is not None:
            return self._model

        if not self.check_weights_exist():
            raise FileNotFoundError(
                f"YOLO weights not found at: {self.model_path}"
            )

        if not self.validate_checksum():
            raise ValueError(
                f"Model weights at {self.model_path} failed checksum verification."
            )

        if not self.is_ml_available():
            raise RuntimeError(
                "Machine learning dependencies ('ultralytics', 'torch') are not installed. "
                "The health check and management APIs remain fully functional, but model "
                "inference requires installing CV dependencies."
            )

        target_device = device or self.device
        logger.info(f"Loading YOLO model {self.version} from {self.model_path} on {target_device}...")
        from ultralytics import YOLO  # lazy import
        model = YOLO(str(self.model_path))
        if hasattr(model, "to") and target_device:
            try:
                model.to(target_device)
            except Exception as e:
                logger.warning("Could not set device %s on model: %s", target_device, e)

        self._model = model
        logger.info("YOLO model loaded successfully.")
        return self._model

    def unload_model(self) -> None:
        """Release model from memory if needed."""
        self._model = None
        logger.info("YOLO model unloaded from memory.")

    def reload_model(self) -> Dict[str, Any]:
        """Unload current model, re-resolve from registry, and return updated info."""
        self.unload_model()
        self._resolve_model()
        return self.get_model_info()


_instance: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Return singleton ModelService instance."""
    global _instance
    if _instance is None:
        _instance = ModelService()
    return _instance
