import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ModelService:
    """Manages YOLO11n model lifecycle without eager loading at API startup."""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = (
            model_path
            if model_path is not None
            else (Path(__file__).resolve().parent.parent.parent / "yolo11n.pt")
        )
        self._model: Optional[Any] = None

    def check_weights_exist(self) -> bool:
        """Verify whether model weights file exists on disk."""
        return self.model_path.is_file()

    @staticmethod
    def is_ml_available() -> bool:
        """Check if ultralytics and torch are installed without importing them globally."""
        has_ultra = importlib.util.find_spec("ultralytics") is not None
        has_torch = importlib.util.find_spec("torch") is not None
        return has_ultra and has_torch

    def get_model_info(self) -> Dict[str, Any]:
        """Return non-intrusive metadata about model file and runtime availability."""
        exists = self.check_weights_exist()
        size = self.model_path.stat().st_size if exists else 0

        return {
            "model_path": str(self.model_path),
            "weights_exist": exists,
            "weights_size_bytes": size,
            "is_loaded": self._model is not None,
            "target_class": "person (COCO 0)",
            "ml_dependencies_installed": self.is_ml_available(),
        }

    def load_model(self) -> Any:
        """Lazily load YOLO11n weights into memory once (singleton)."""
        if self._model is not None:
            return self._model

        if not self.check_weights_exist():
            raise FileNotFoundError(
                f"YOLO weights not found at: {self.model_path}"
            )

        if not self.is_ml_available():
            raise RuntimeError(
                "Machine learning dependencies ('ultralytics', 'torch') are not installed. "
                "The health check and management APIs remain fully functional, but model "
                "inference requires installing CV dependencies."
            )

        logger.info(f"Loading YOLO11n weights from {self.model_path}...")
        from ultralytics import YOLO  # lazy import
        self._model = YOLO(str(self.model_path))
        logger.info("YOLO11n model loaded successfully.")
        return self._model

    def unload_model(self) -> None:
        """Release model from memory if needed."""
        self._model = None
        logger.info("YOLO11n model unloaded from memory.")


_instance: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Return singleton ModelService instance."""
    global _instance
    if _instance is None:
        _instance = ModelService()
    return _instance
