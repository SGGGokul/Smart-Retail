from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse
from app.services.model_service import get_model_service


def test_health_success(client: TestClient) -> None:
    """GET /health must return status 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_schema(client: TestClient) -> None:
    """GET /health must return fields strictly matching API_CONTRACT.md section 1."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    # Validate against Pydantic schema
    validated = HealthResponse(**data)
    assert validated.status == "ok"
    assert validated.version == "1.0.0"
    assert isinstance(validated.uptimeSeconds, int)
    assert validated.uptimeSeconds >= 0
    assert validated.timestamp.endswith("Z")

    # Validate ISO-8601 UTC parseability
    parsed_dt = datetime.fromisoformat(validated.timestamp.replace("Z", "+00:00"))
    assert parsed_dt is not None


def test_health_v1_endpoint(client: TestClient) -> None:
    """GET /api/v1/health must also return the health check response."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_api_startup_and_openapi(client: TestClient) -> None:
    """Application OpenAPI schema and Swagger documentation must load properly."""
    docs_res = client.get("/docs")
    assert docs_res.status_code == 200

    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert schema["info"]["title"] == "RetailIQ Backend"
    assert "/health" in schema["paths"]


def test_config_loading() -> None:
    """Application settings must load defaults and allow customization."""
    settings = get_settings()
    assert settings.PROJECT_NAME == "RetailIQ Backend"
    assert settings.VERSION == "1.0.0"
    assert settings.PORT == 8000
    assert "http://localhost:3000" in settings.CORS_ORIGINS

    # Test CORS validator with comma-separated string
    custom_settings = Settings(CORS_ORIGINS="http://site-a.com, http://site-b.com")
    assert custom_settings.CORS_ORIGINS == ["http://site-a.com", "http://site-b.com"]


def test_cors_headers(client: TestClient) -> None:
    """CORS middleware must allow requests from the Next.js frontend origin."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_error_envelope_404(client: TestClient) -> None:
    """404 responses must conform to the API_CONTRACT.md error envelope."""
    response = client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "message" in data["error"]


def test_model_service_non_intrusive() -> None:
    """ModelService must report weight presence without executing model inference."""
    service = get_model_service()
    info = service.get_model_info()

    assert "model_path" in info
    assert "weights_exist" in info
    assert info["weights_exist"] is True  # yolo11n.pt is physically present
    assert info["weights_size_bytes"] > 5_000_000
    assert info["is_loaded"] is False  # Not loaded eagerly during startup
    assert info["target_class"] == "person (COCO 0)"
