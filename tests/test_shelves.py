from fastapi.testclient import TestClient
from app.schemas.shelves import ShelvesResponse


def test_shelves_list_contract_schema(client: TestClient) -> None:
    """GET /api/v1/shelves must return valid schema with zero counts when unavailable."""
    response = client.get("/api/v1/shelves")
    assert response.status_code == 200
    data = response.json()
    validated = ShelvesResponse(**data)
    assert validated.shelves == []
    assert validated.totalCount == 0
    assert validated.criticalCount == 0
    assert validated.lowStockCount == 0


def test_shelf_by_id_not_found(client: TestClient) -> None:
    """GET /api/v1/shelves/{id} must return 404 with standard error envelope."""
    response = client.get("/api/v1/shelves/sh-A4")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
