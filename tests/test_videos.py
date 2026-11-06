import io
from fastapi.testclient import TestClient
from app.schemas.video import VideoJob, VideoResultsResponse, VideoUploadResponse


def test_video_upload_invalid_extension(client: TestClient) -> None:
    """POST /api/v1/videos must reject invalid file types."""
    dummy_file = io.BytesIO(b"dummy text")
    response = client.post(
        "/api/v1/videos",
        files={"file": ("test.txt", dummy_file, "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"


def test_video_upload_empty_file(client: TestClient) -> None:
    """POST /api/v1/videos must reject empty 0-byte uploads."""
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/videos",
        files={"file": ("empty.mp4", empty_file, "video/mp4")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_video_upload_and_status(client: TestClient) -> None:
    """POST /api/v1/videos queues valid upload and returns expected schema."""
    fake_video_data = io.BytesIO(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41")
    response = client.post(
        "/api/v1/videos",
        files={"file": ("store_cam1.mp4", fake_video_data, "video/mp4")},
    )
    assert response.status_code in (200, 201)
    data = response.json()
    validated = VideoUploadResponse(**data)
    assert validated.jobId.startswith("vj-")
    assert validated.filename == "store_cam1.mp4"
    assert validated.status in ("queued", "processing", "done", "failed")

    # Fetch job status via GET /api/v1/videos/{id}
    job_res = client.get(f"/api/v1/videos/{validated.jobId}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    job_val = VideoJob(**job_data)
    assert job_val.id == validated.jobId
    assert job_val.file == "store_cam1.mp4"

    # List jobs via GET /api/v1/videos
    list_res = client.get("/api/v1/videos")
    assert list_res.status_code == 200
    jobs_list = list_res.json()
    assert any(j["id"] == validated.jobId for j in jobs_list)


def test_video_job_not_found(client: TestClient) -> None:
    """GET /api/v1/videos/{id} returns 404 for unknown job."""
    response = client.get("/api/v1/videos/vj-unknown-999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_video_results_not_found(client: TestClient) -> None:
    """GET /api/v1/videos/{id}/results returns 404 for unknown job."""
    response = client.get("/api/v1/videos/vj-unknown-999/results")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
