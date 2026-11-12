from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # Project metadata
    PROJECT_NAME: str = "RetailIQ Backend"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    STORE_TIMEZONE: str = "Asia/Kolkata"

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

    # Database Configuration (PostgreSQL with asyncpg driver)
    DATABASE_URL: Optional[str] = "postgresql+asyncpg://postgres:postgres@localhost:5432/retailiq"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # Model configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    MODEL_PATH: Path = BASE_DIR / "yolo11n.pt"
    MODEL_DEVICE: str = "cpu"
    MODEL_REGISTRY_DIR: Path = BASE_DIR / "mlops" / "artifacts" / "registry"
    MODEL_USE_REGISTRY: bool = True
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
    ALERT_SHELF_WARNING_THRESHOLD: float = 60.0
    ALERT_SHELF_CRITICAL_THRESHOLD: float = 30.0
    ALERT_SHELF_EMPTY_THRESHOLD: float = 5.0

    # Groq LLM & Guardrail Configuration
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_GUARD_MODEL: str = "meta-llama/llama-prompt-guard-2-86m"
    GROQ_SAFEGUARD_MODEL: str = "openai/gpt-oss-safeguard-20b"
    GROQ_TIMEOUT_SECONDS: float = 15.0
    GROQ_MAX_RETRIES: int = 2
    GROQ_MAX_TOKENS: int = 800

    # RAG Configuration
    RAG_ENABLE_RERANKER: bool = False
    RAG_TOP_K: int = 3
    RAG_CONFIDENCE_THRESHOLD: float = 0.50

    # Centralized Redis Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_BACKEND: str = "redis"
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379/1"
    RATE_LIMIT_FAIL_MODE: str = "closed"
    RATE_LIMIT_TRUSTED_PROXIES: Union[List[str], str] = []

    @field_validator("RATE_LIMIT_TRUSTED_PROXIES", mode="before")
    @classmethod
    def assemble_trusted_proxies(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

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
        env_file=(BASE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
