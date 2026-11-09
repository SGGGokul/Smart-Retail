import os
import uuid
import pytest
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.db.session import normalize_database_url
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def configure_test_db():
    """Ensure test runs execute against the isolated retailiq_test database and resilient fail-mode."""
    settings = get_settings()
    base_url = normalize_database_url(settings.DATABASE_URL)
    test_db_url = base_url.rsplit("/", 1)[0] + "/retailiq_test"
    original_url = os.environ.get("DATABASE_URL")
    original_rate_limit_fail = os.environ.get("RATE_LIMIT_FAIL_MODE")

    os.environ["DATABASE_URL"] = test_db_url
    if "RATE_LIMIT_FAIL_MODE" not in os.environ:
        os.environ["RATE_LIMIT_FAIL_MODE"] = "open"
    get_settings.cache_clear()

    yield

    if original_url is not None:
        os.environ["DATABASE_URL"] = original_url
    else:
        os.environ.pop("DATABASE_URL", None)

    if original_rate_limit_fail is not None:
        os.environ["RATE_LIMIT_FAIL_MODE"] = original_rate_limit_fail
    else:
        os.environ.pop("RATE_LIMIT_FAIL_MODE", None)
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    """Fixture providing synchronous FastAPI test client with isolated client identity."""
    test_uid = f"test-client-{uuid.uuid4().hex[:8]}"
    with TestClient(app, headers={"X-User-ID": test_uid}) as test_client:
        yield test_client
