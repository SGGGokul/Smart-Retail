import io
import time
from pathlib import Path
import cv2
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture(scope="module")
def sample_e2e_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    settings = get_settings()
    sample_dir = settings.BASE_DIR / "results" / "sample_frames"
    sample_images = sorted(list(sample_dir.glob("*.png")))

    temp_dir = tmp_path_factory.mktemp("e2e_videos")
    video_file = temp_dir / "e2e_store_footage.mp4"

    first_frame = cv2.imread(str(sample_images[0]))
    h, w, _ = first_frame.shape
    fps = 10.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_file), fourcc, fps, (w, h))
    for _ in range(3):  # write 15 frames
        for img_path in sample_images:
            out.write(cv2.imread(str(img_path)))
    out.release()
    return video_file


def test_full_video_to_analytics_workflow(client: TestClient, sample_e2e_video: Path) -> None:
    """Full lifecycle test:

    1. Upload real video
    2. Wait for async CV worker to finish
    3. Verify job results schema & detections
    4. Verify analytics summary updated with real customer numbers
    5. Verify assistant reports the real customer counts
    """
    with sample_e2e_video.open("rb") as f:
        video_bytes = f.read()

    upload_res = client.post(
        "/api/v1/videos",
        files={"file": ("e2e_store_footage.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert upload_res.status_code in (200, 201)
    job_id = upload_res.json()["jobId"]

    # Poll status until done (max 15 seconds)
    max_wait = 15
    start = time.time()
    final_status = None
    while time.time() - start < max_wait:
        status_res = client.get(f"/api/v1/videos/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        if data["status"] in ("done", "failed"):
            final_status = data["status"]
            break
        time.sleep(0.5)

    assert final_status == "done", f"Job failed or timed out: {data}"

    # Results check
    results_res = client.get(f"/api/v1/videos/{job_id}/results")
    assert results_res.status_code == 200
    res_data = results_res.json()
    assert res_data["status"] == "done"
    assert res_data["totalFrames"] == 15
    assert res_data["customersDetected"] >= 1
    assert len(res_data["detections"]) > 0

    # Analytics summary check
    summary_res = client.get("/api/v1/analytics/summary")
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["todayCustomers"] >= 1

    # Assistant chat check
    chat_res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "How many customers visited today?"},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert str(summary_data["todayCustomers"]) in chat_data["answer"]
