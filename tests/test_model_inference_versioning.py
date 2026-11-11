"""Unit tests for versioned model loading and inference integration."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.services.model_service import ModelService, compute_sha256
from app.main import app


def test_model_service_default_fallback():
    service = ModelService()
    info = service.get_model_info()

    assert info["weights_exist"] is True
    assert info["version"] == "baseline-yolo11n"
    assert info["stage"] == "baseline"
    assert info["target_class"] == "person (COCO 0)"
    assert info["sha256"] is not None


def test_model_service_resolves_registry(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    weights_file = tmp_path / "custom_yolo.pt"
    weights_file.write_bytes(b"custom_yolo_model_content_12345")
    checksum = compute_sha256(weights_file)

    catalog = {
        "active_production": "v2.0.0-retail",
        "previous_production": None,
        "models": {
            "v2.0.0-retail": {
                "version": "v2.0.0-retail",
                "weights_path": str(weights_file),
                "sha256": checksum,
                "stage": "production",
            }
        },
    }

    catalog_file = registry_dir / "catalog.json"
    catalog_file.write_text(json.dumps(catalog))

    service = ModelService(registry_dir=registry_dir)
    info = service.get_model_info()

    assert info["version"] == "v2.0.0-retail"
    assert info["stage"] == "production"
    assert info["weights_exist"] is True
    assert info["checksum_verified"] is True


def test_model_service_checksum_mismatch(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    weights_file = tmp_path / "corrupted_yolo.pt"
    weights_file.write_bytes(b"corrupted_bytes")

    catalog = {
        "active_production": "v2.0.0-corrupted",
        "models": {
            "v2.0.0-corrupted": {
                "version": "v2.0.0-corrupted",
                "weights_path": str(weights_file),
                "sha256": "expected_different_sha256_hash",
                "stage": "production",
            }
        },
    }
    (registry_dir / "catalog.json").write_text(json.dumps(catalog))

    service = ModelService(registry_dir=registry_dir)
    assert service.validate_checksum() is False

    with pytest.raises(ValueError, match="failed checksum verification"):
        service.load_model()


def test_api_model_info_endpoint(client: TestClient):
    response = client.get("/api/v1/model/info")
    assert response.status_code == 200
    data = response.json()

    assert "model_path" in data
    assert "version" in data
    assert "stage" in data
    assert "weights_exist" in data
    assert data["weights_exist"] is True


def test_api_model_reload_endpoint(client: TestClient):
    response = client.post("/api/v1/model/reload")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "is_loaded" in data
    assert data["is_loaded"] is False
