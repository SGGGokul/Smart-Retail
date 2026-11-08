import base64
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
from fastapi import HTTPException, UploadFile, status
import numpy as np

from app.core.config import get_settings
from app.schemas.image import ImageBox, ImageDetectionBox, ImageDetectionResponse

# Prevent Ultralytics auto-telemetry or permission warnings
os.environ.setdefault("YOLO_OFFLINE", "1")

logger = logging.getLogger("retailiq.image_service")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_PREFIXES = {"image/"}
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


class ImageDetectionService:
    """Service for processing uploaded images with YOLO inference and OpenCV visualization.

    Designed with plug-and-play architecture for future fine-tuned shelf models (e.g., SKU-110K).
    """

    def __init__(self, model_path: Optional[Path] = None, shelf_model_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self.model_path = model_path or settings.MODEL_PATH
        self.shelf_model_path = shelf_model_path
        self._model = None
        self._shelf_model = None

    def _get_model(self):
        """Lazy-load YOLO model singleton to conserve resources."""
        if self._model is None:
            from ultralytics import YOLO

            logger.info(f"Loading YOLO model from {self.model_path}")
            self._model = YOLO(str(self.model_path))
        return self._model

    def _get_shelf_model(self):
        """Check and lazy-load specialized shelf model if available."""
        if self.shelf_model_path and self.shelf_model_path.exists():
            if self._shelf_model is None:
                from ultralytics import YOLO

                logger.info(f"Loading specialized shelf model from {self.shelf_model_path}")
                self._shelf_model = YOLO(str(self.shelf_model_path))
            return self._shelf_model
        return None

    async def detect_image(
        self,
        file: UploadFile,
        confidence_threshold: float = 0.25,
    ) -> ImageDetectionResponse:
        """Validate, decode, run inference, and annotate an uploaded image."""
        filename = file.filename or "uploaded_image.jpg"
        ext = Path(filename).suffix.lower()

        # 1. Extension validation
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            allowed_sorted = sorted(list(ALLOWED_IMAGE_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image format '{ext}'. Allowed formats: {allowed_sorted}.",
            )

        # 2. MIME type validation (when content_type header is provided)
        if file.content_type:
            ct = file.content_type.lower()
            if not any(ct.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES) and ct != "application/octet-stream":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid MIME type '{file.content_type}'. Must be an image MIME type.",
                )

        # 3. Read content and validate size
        content = await file.read()
        if not content or len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty (0 bytes).",
            )

        if len(content) > MAX_IMAGE_SIZE_BYTES:
            max_mb = MAX_IMAGE_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image size exceeds maximum limit of {max_mb} MB.",
            )

        # 4. Decode image bytes via OpenCV
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not decode image file. File may be corrupted, truncated, or an invalid image format.",
            )

        height, width = img.shape[:2]

        # 5. Model selection (specialized shelf model vs general COCO YOLO11n)
        specialized_model = self._get_shelf_model()
        if specialized_model is not None:
            active_model = specialized_model
            model_name = self.shelf_model_path.name if self.shelf_model_path else "shelf_sku_custom.pt"
            is_coco = False
            shelf_supported = True
            note = "Specialized retail shelf / SKU model was used for detection."
        else:
            active_model = self._get_model()
            model_name = self.model_path.name if self.model_path else "yolo11n.pt"
            is_coco = True
            # Check if shelf is in model's class list
            shelf_supported = any("shelf" in name.lower() for name in active_model.names.values())
            note = (
                "Standard COCO weights (80 classes) detected general retail objects (e.g. bottles, cups, persons). "
                "Native shelf inventory, planogram compliance, and out-of-stock SKU detection require specialized "
                "retail models (e.g. SKU-110K)."
            )

        # 6. Execute inference
        # Predict synchronously in worker thread or directly on single frame
        results = active_model.predict(
            source=img,
            conf=confidence_threshold,
            verbose=False,
        )

        detections: List[ImageDetectionBox] = []
        counts: Dict[str, int] = {}

        # 7. Parse bounding boxes and annotate image
        annotated_img = img.copy()

        # Color palette for classes (BGR)
        palette = [
            (34, 197, 94),   # Emerald green
            (59, 130, 246),  # Blue
            (249, 115, 22),  # Orange
            (168, 85, 247),  # Purple
            (236, 72, 153),  # Pink
            (20, 184, 166),  # Teal
            (234, 179, 8),   # Yellow
            (99, 102, 241),  # Indigo
        ]

        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for idx, box in enumerate(boxes):
                cls_id = int(box.cls[0].item())
                label = active_model.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0].item())
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]

                # Clamp to image boundaries
                x1 = max(0.0, min(float(width), x1))
                y1 = max(0.0, min(float(height), y1))
                x2 = max(0.0, min(float(width), x2))
                y2 = max(0.0, min(float(height), y2))
                bw = max(0.0, x2 - x1)
                bh = max(0.0, y2 - y1)

                det_id = f"det-{idx + 1}"
                detections.append(
                    ImageDetectionBox(
                        id=det_id,
                        classId=cls_id,
                        label=label,
                        confidence=round(conf, 4),
                        box=ImageBox(
                            x1=round(x1, 1),
                            y1=round(y1, 1),
                            x2=round(x2, 1),
                            y2=round(y2, 1),
                            x=round(x1, 1),
                            y=round(y1, 1),
                            width=round(bw, 1),
                            height=round(bh, 1),
                        ),
                    )
                )

                counts[label] = counts.get(label, 0) + 1

                # Draw bounding box
                color = palette[cls_id % len(palette)]
                p1 = (int(x1), int(y1))
                p2 = (int(x2), int(y2))
                cv2.rectangle(annotated_img, p1, p2, color, thickness=2, lineType=cv2.LINE_AA)

                # Label tag
                tag = f"{label} {int(conf * 100)}%"
                font_scale = 0.5
                thickness = 1
                (tw, th), baseline = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                tag_y1 = max(0, int(y1) - th - 6)
                tag_y2 = int(y1)
                tag_x1 = int(x1)
                tag_x2 = int(x1) + tw + 8

                # Tag background
                cv2.rectangle(
                    annotated_img,
                    (tag_x1, tag_y1),
                    (tag_x2, tag_y2),
                    color,
                    -1,
                )
                # Tag text (white or dark depending on background)
                cv2.putText(
                    annotated_img,
                    tag,
                    (tag_x1 + 4, tag_y2 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    (255, 255, 255),
                    thickness,
                    lineType=cv2.LINE_AA,
                )

        # 8. Encode annotated image to Base64 JPEG
        success, enc_buf = cv2.imencode(".jpg", annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        annotated_b64 = None
        if success:
            annotated_b64 = f"data:image/jpeg;base64,{base64.b64encode(enc_buf).decode('utf-8')}"

        return ImageDetectionResponse(
            filename=filename,
            width=width,
            height=height,
            totalDetections=len(detections),
            detections=detections,
            detectionCounts=counts,
            annotatedImage=annotated_b64,
            modelUsed=model_name,
            isCocoGeneralModel=is_coco,
            shelfDetectionSupported=shelf_supported,
            note=note,
        )


_image_service_instance: Optional[ImageDetectionService] = None


def get_image_detection_service() -> ImageDetectionService:
    """Singleton getter for ImageDetectionService."""
    global _image_service_instance
    if _image_service_instance is None:
        _image_service_instance = ImageDetectionService()
    return _image_service_instance
