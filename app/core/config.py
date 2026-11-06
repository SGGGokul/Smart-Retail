from functools import lru_cache
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # Project metadata
    PROJECT_NAME: str = "RetailIQ Backend"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # API Routing
    API_V1_PREFIX: str = "/api/v1"

    # CORS configuration - default allows Next.js frontend dev servers
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    # Model configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    MODEL_PATH: Path = BASE_DIR / "yolo11n.pt"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"

    # Computer Vision parameters (reused from existing scripts)
    CV_CONFIDENCE: float = 0.4
    CV_MIN_TRACK_SECONDS: float = 1.0
    CV_TRACKER_CONFIG: str = "bytetrack.yaml"

    # Configurable Entrance/Exit Zone
    CV_ZONE_X1: int = 700
    CV_ZONE_X2: int = 846
    CV_ZONE_Y1: int = 320
    CV_ZONE_Y2: int = 480

    # Rule Engine Alert Thresholds
    ALERT_OCCUPANCY_WARNING_THRESHOLD: int = 15
    ALERT_OCCUPANCY_CRITICAL_THRESHOLD: int = 25
    ALERT_DWELL_SECONDS_THRESHOLD: float = 120.0
    ALERT_ENTRY_SURGE_THRESHOLD: int = 20

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
