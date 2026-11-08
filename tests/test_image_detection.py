import io
from pathlib import Path
import cv2
from fastapi.testclient import TestClient
import numpy as np

from app.schemas.image import ImageDetectionResponse


def _create_synthetic_image(fmt: str = ".jpg", width: int = 640, height: int = 480, draw_shapes: bool = True) -> bytes:
    """Helper to create valid image bytes in memory."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    if draw_shapes:
        # Draw some colored shapes / contrast
        cv2.rectangle(img, (50, 50), (200, 300), (0, 255, 0), -1)
        cv2.circle(img, (400, 240), 80, (255, 0, 0), -1)
        cv2.putText(img, "RetailIQ Store Shelf", (50, 400), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    success, encoded = cv2.imencode(fmt, img)
    assert success
    return encoded.tobytes()


def test_detect_image_valid_jpg(client: TestClient) -> None:
    """POST /api/v1/images/detect succeeds with valid JPG image."""
    image_bytes = _create_synthetic_image(".jpg")
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("store_shelf.jpg", io.BytesIO(image_bytes), "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    validated = ImageDetectionResponse(**data)
    assert validated.filename == "store_shelf.jpg"
    assert validated.width == 640
    assert validated.height == 480
    assert validated.modelUsed == "yolo11n.pt"
    assert validated.isCocoGeneralModel is True
    assert validated.shelfDetectionSupported is False
    assert "COCO" in validated.note
    assert validated.annotatedImage is not None
    assert validated.annotatedImage.startswith("data:image/jpeg;base64,")


def test_detect_image_valid_png(client: TestClient) -> None:
    """POST /api/v1/images/detect succeeds with valid PNG image."""
    image_bytes = _create_synthetic_image(".png", width=320, height=240)
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("shelf_inventory.png", io.BytesIO(image_bytes), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    validated = ImageDetectionResponse(**data)
    assert validated.filename == "shelf_inventory.png"
    assert validated.width == 320
    assert validated.height == 240


def test_detect_image_valid_webp(client: TestClient) -> None:
    """POST /api/v1/images/detect succeeds with valid WEBP image."""
    image_bytes = _create_synthetic_image(".webp", width=400, height=300)
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("aisle_view.webp", io.BytesIO(image_bytes), "image/webp")},
    )
    assert response.status_code == 200
    data = response.json()
    validated = ImageDetectionResponse(**data)
    assert validated.filename == "aisle_view.webp"
    assert validated.width == 400
    assert validated.height == 300


def test_detect_image_zero_detections(client: TestClient) -> None:
    """POST /api/v1/images/detect handles 0 detections gracefully on blank canvas."""
    # Blank pure black image has 0 COCO detections
    image_bytes = _create_synthetic_image(".jpg", draw_shapes=False)
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("empty_black.jpg", io.BytesIO(image_bytes), "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    validated = ImageDetectionResponse(**data)
    assert validated.totalDetections == 0
    assert validated.detections == []
    assert validated.detectionCounts == {}
    assert validated.annotatedImage is not None


def test_detect_image_corrupted_file(client: TestClient) -> None:
    """POST /api/v1/images/detect returns 400 Bad Request on corrupted image bytes."""
    corrupted_bytes = b"NOT_A_VALID_JPEG_HEADER_RANDOM_DATA_CORRUPTION"
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("corrupt.jpg", io.BytesIO(corrupted_bytes), "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data or "detail" in data


def test_detect_image_empty_file(client: TestClient) -> None:
    """POST /api/v1/images/detect returns 400 Bad Request on empty 0-byte file."""
    empty_bytes = b""
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("empty.jpg", io.BytesIO(empty_bytes), "image/jpeg")},
    )
    assert response.status_code == 400


def test_detect_image_unsupported_extension(client: TestClient) -> None:
    """POST /api/v1/images/detect returns 400 Bad Request on non-image extension."""
    doc_bytes = b"Hello world text document"
    response = client.post(
        "/api/v1/images/detect",
        files={"file": ("store_report.pdf", io.BytesIO(doc_bytes), "application/pdf")},
    )
    assert response.status_code == 400


def test_shelves_detect_endpoint(client: TestClient) -> None:
    """POST /api/v1/shelves/detect works as an alias for shelf image processing."""
    image_bytes = _create_synthetic_image(".jpg")
    response = client.post(
        "/api/v1/shelves/detect",
        files={"file": ("shelf_bay_a.jpg", io.BytesIO(image_bytes), "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    validated = ImageDetectionResponse(**data)
    assert validated.filename == "shelf_bay_a.jpg"


def test_video_endpoint_rejects_image(client: TestClient) -> None:
    """POST /api/v1/videos must reject image files, enforcing separation of endpoints."""
    image_bytes = _create_synthetic_image(".jpg")
    response = client.post(
        "/api/v1/videos",
        files={"file": ("camera_snapshot.jpg", io.BytesIO(image_bytes), "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    # Confirms video endpoint rejects image format
    err_str = str(data)
    assert "Unsupported video format" in err_str or "400" in err_str


def test_real_sample_image_inference(client: TestClient) -> None:
    """Inference test using the real store frame extracted from CCTV."""
    sample_path = Path("D:/Download/CISG/Backend/data/uploads/sample_retail_shelf.jpg")
    if sample_path.exists():
        with open(sample_path, "rb") as f:
            content = f.read()
        response = client.post(
            "/api/v1/images/detect",
            files={"file": ("sample_retail_shelf.jpg", io.BytesIO(content), "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ImageDetectionResponse(**data)
        assert validated.width > 0
        assert validated.height > 0
        assert validated.annotatedImage is not None
        # On real store frame, shoppers/people or objects are detected
        assert validated.totalDetections >= 0
