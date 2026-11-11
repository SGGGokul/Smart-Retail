from pathlib import Path
import pytest
import cv2

from app.core.config import get_settings
from app.services.cv_service import CVService


@pytest.fixture(scope="module")
def sample_video_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a valid test mp4 video clip from existing MERL sample frames."""
    settings = get_settings()
    sample_dir = settings.BASE_DIR / "results" / "sample_frames"
    sample_images = sorted(list(sample_dir.glob("*.png")))

    if not sample_images:
        pytest.skip("No sample frames found in results/sample_frames for CV testing.")

    temp_dir = tmp_path_factory.mktemp("videos")
    video_file = temp_dir / "real_test_clip.mp4"

    first_frame = cv2.imread(str(sample_images[0]))
    h, w, _ = first_frame.shape
    fps = 5.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_file), fourcc, fps, (w, h))

    # Write sequence of sample frames
    for img_path in sample_images:
        img = cv2.imread(str(img_path))
        out.write(img)
    out.release()

    return video_file


def test_real_yolo11n_bytetrack_inference(sample_video_path: Path) -> None:
    """Execute real YOLO11n + ByteTrack inference on test video and assert metrics."""
    settings = get_settings()
    assert settings.MODEL_PATH.exists(), f"Weights file missing: {settings.MODEL_PATH}"

    service = CVService(model_path=settings.MODEL_PATH)
    metrics = service.process_video(
        video_path=sample_video_path,
        confidence=0.35,
        min_track_seconds=0.1,  # short threshold for 5-frame test
    )

    assert metrics["total_frames"] == 5
    assert metrics["fps"] == 5.0
    assert metrics["measured_fps"] > 0.0
    assert metrics["unique_customers"] >= 1
    assert metrics["peak_occupancy"] >= 1
    assert metrics["average_occupancy"] >= 0.2
    assert isinstance(metrics["detections"], list)
    assert len(metrics["detections"]) > 0

    det = metrics["detections"][0]
    assert det.label == "person"
    assert det.confidence >= 0.35
    assert det.box.width > 0
    assert det.box.height > 0
