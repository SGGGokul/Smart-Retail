"""API router for MLOps model inspection and lifecycle management."""
from typing import Any, Dict
from fastapi import APIRouter, status

from app.services.model_service import get_model_service

router = APIRouter(tags=["Model"])


@router.get(
    "/info",
    status_code=status.HTTP_200_OK,
    summary="Get active model metadata",
    description="Returns metadata about the active YOLO11n / MLOps model version, weights, and device.",
)
def get_model_info() -> Dict[str, Any]:
    """Retrieve metadata of the currently configured model."""
    service = get_model_service()
    return service.get_model_info()


@router.post(
    "/reload",
    status_code=status.HTTP_200_OK,
    summary="Reload model from registry",
    description="Re-resolves active production model from MLOps registry and refreshes memory state.",
)
def reload_model() -> Dict[str, Any]:
    """Reload active production model."""
    service = get_model_service()
    return service.reload_model()
