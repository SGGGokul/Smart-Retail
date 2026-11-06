from fastapi import APIRouter

from app.api.alerts import router as alerts_router
from app.api.analytics import router as analytics_router
from app.api.assistant import router as assistant_router
from app.api.health import router as health_router
from app.api.shelves import router as shelves_router
from app.api.videos import router as videos_router

api_v1_router = APIRouter()

# Include health check under v1 as well for API version consistency
api_v1_router.include_router(health_router, prefix="", tags=["Health"])

# Domain routers conforming to API_CONTRACT.md
api_v1_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_v1_router.include_router(shelves_router, prefix="/shelves", tags=["Shelves"])
api_v1_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_v1_router.include_router(videos_router, prefix="/videos", tags=["Videos"])
api_v1_router.include_router(assistant_router, prefix="/assistant", tags=["Assistant"])
