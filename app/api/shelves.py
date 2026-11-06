from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.shelves import ShelfItem, ShelvesResponse

router = APIRouter()


@router.get(
    "",
    response_model=ShelvesResponse,
    summary="List monitored shelf zones",
)
async def list_shelves(
    status: Optional[str] = Query(default=None, description="all | low | critical")
) -> ShelvesResponse:
    """Lists all monitored retail shelf zones and stock levels.

    NOTE: Shelf inventory detection with YOLO11n is not supported; returning
    contract-valid empty response without fabricating fill percentages.
    """
    return ShelvesResponse(
        shelves=[],
        totalCount=0,
        criticalCount=0,
        lowStockCount=0,
    )


@router.get(
    "/{id}",
    response_model=ShelfItem,
    summary="Get individual shelf zone",
)
async def get_shelf(id: str) -> ShelfItem:
    """Retrieves an individual shelf bay status."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Shelf zone '{id}' not found.",
    )
