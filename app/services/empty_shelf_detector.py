"""RetailIQ Empty Shelf Detection and Shelf Occupancy Estimation Service.

Implements:
- Shelf structure detection and multi-tier section division.
- Multi-modal product detection (YOLO object detection + retail packaged SKU feature analysis).
- Empty space / gap identification along physical shelf tiers.
- Occupancy percentage calculation for each shelf section and the overall bay.
- Image quality and lighting checks (avoids false empty-shelf alerts on dark or blurry images).
- Rich OpenCV visual annotations for detected products and empty gaps.
"""

from dataclasses import dataclass, field
import base64
import logging
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("retailiq.empty_shelf_detector")


@dataclass
class EmptySpaceBox:
    """Coordinates and dimensions of an empty shelf gap."""
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float
    section_index: int
    gap_type: str = "out_of_stock_gap"  # "out_of_stock_gap" | "empty_section"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x1": round(self.x1, 1),
            "y1": round(self.y1, 1),
            "x2": round(self.x2, 1),
            "y2": round(self.y2, 1),
            "width": round(self.width, 1),
            "height": round(self.height, 1),
            "sectionIndex": self.section_index,
            "gapType": self.gap_type,
        }


@dataclass
class DetectedProductBox:
    """Coordinates, classification, and confidence of a detected retail product."""
    id: str
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float
    section_index: int
    detection_source: str = "hybrid_retail_detector"  # "yolo" | "retail_sku" | "hybrid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "className": self.class_name,
            "confidence": round(self.confidence, 4),
            "x1": round(self.x1, 1),
            "y1": round(self.y1, 1),
            "x2": round(self.x2, 1),
            "y2": round(self.y2, 1),
            "width": round(self.width, 1),
            "height": round(self.height, 1),
            "sectionIndex": self.section_index,
            "source": self.detection_source,
        }


@dataclass
class ShelfSectionResult:
    """Analytics for an individual physical shelf section or tier."""
    section_index: int
    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    occupancy_pct: float
    status: str  # "empty", "critical", "low", "ok"
    products: List[DetectedProductBox] = field(default_factory=list)
    empty_spaces: List[EmptySpaceBox] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sectionIndex": self.section_index,
            "name": self.name,
            "x1": round(self.x1, 1),
            "y1": round(self.y1, 1),
            "x2": round(self.x2, 1),
            "y2": round(self.y2, 1),
            "occupancyPercentage": round(self.occupancy_pct, 1),
            "status": self.status,
            "productsCount": len(self.products),
            "emptySpacesCount": len(self.empty_spaces),
            "products": [p.to_dict() for p in self.products],
            "emptySpaces": [e.to_dict() for e in self.empty_spaces],
        }


@dataclass
class ShelfAnalysisOutcome:
    """Overall outcome of shelf detection, occupancy estimation, and gap analysis."""
    shelf_id: str
    location: str
    width: int
    height: int
    overall_occupancy_pct: float
    total_products_count: int
    total_empty_spaces_count: int
    status: str  # "empty", "critical", "low", "ok", "poor_lighting"
    is_detection_reliable: bool
    reliability_note: Optional[str]
    sections: List[ShelfSectionResult]
    all_detections: List[DetectedProductBox]
    detection_counts: Dict[str, int]
    annotated_image: Optional[str]
    model_used: str = "retailiq_hybrid_shelf_v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shelfId": self.shelf_id,
            "location": self.location,
            "width": self.width,
            "height": self.height,
            "overallOccupancyPercentage": round(self.overall_occupancy_pct, 1),
            "totalProductsCount": self.total_products_count,
            "totalEmptySpacesCount": self.total_empty_spaces_count,
            "status": self.status,
            "isDetectionReliable": self.is_detection_reliable,
            "reliabilityNote": self.reliability_note,
            "sections": [s.to_dict() for s in self.sections],
            "totalDetections": len(self.all_detections),
            "detectionCounts": self.detection_counts,
            "annotatedImage": self.annotated_image,
            "modelUsed": self.model_used,
        }


class EmptyShelfDetector:
    """Computer vision engine for supermarket shelf division, product detection,

    gap localization, and occupancy percentage computation.
    """

    MIN_LUMINANCE_THRESHOLD = 25.0  # Luminance below 25 is too dark for reliable detection
    MIN_LAPLACIAN_VARIANCE = 10.0   # Blur measurement threshold
    DEFAULT_EMPTY_THRESHOLD = 5.0   # <= 5% considered completely empty
    DEFAULT_CRITICAL_THRESHOLD = 30.0  # < 30% considered critical depletion
    DEFAULT_WARNING_THRESHOLD = 60.0   # < 60% considered low stock

    def __init__(self, yolo_model: Any = None) -> None:
        self.yolo_model = yolo_model

    def assess_image_quality(self, img: np.ndarray) -> Tuple[bool, Optional[str], float, float]:
        """Assess whether image lighting and clarity are sufficient for reliable vision telemetry.

        Returns (is_reliable, reason, mean_luminance, blur_variance).
        """
        if img is None or img.size == 0:
            return False, "Image array is empty or unreadable.", 0.0, 0.0

        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Check for extreme underexposure (pitch black or dim lighting)
        if mean_val < self.MIN_LUMINANCE_THRESHOLD:
            return (
                False,
                f"Poor lighting detected: mean luminance {mean_val:.1f} < {self.MIN_LUMINANCE_THRESHOLD:.1f}. "
                "Camera requires illumination; detection failure must not be treated as an empty shelf.",
                mean_val,
                laplacian_var,
            )

        # Check for severe blur on illuminated image
        if laplacian_var < self.MIN_LAPLACIAN_VARIANCE and mean_val >= 35.0:
            return (
                False,
                f"Severe blur detected: focus variance {laplacian_var:.1f} < {self.MIN_LAPLACIAN_VARIANCE:.1f}. "
                "Optical stream is out of focus; stock count is uncertain.",
                mean_val,
                laplacian_var,
            )

        return True, None, mean_val, laplacian_var

    def divide_shelf_sections(self, img_shape: Tuple[int, int, int], num_tiers: int = 3) -> List[Tuple[float, float, float, float, str]]:
        """Divide the shelf into physical tiers/sections.

        Returns list of (x1, y1, x2, y2, section_name).
        """
        height, width = img_shape[:2]
        pad_x = width * 0.02
        x1 = float(pad_x)
        x2 = float(width - pad_x)

        # Standard supermarket shelf vertical distribution
        # Tier 1 (Top Tier), Tier 2 (Mid Tier), Tier 3 (Base Tier)
        if num_tiers == 3:
            ratios = [
                (0.06, 0.35, "Section 1 (Top Tier)"),
                (0.35, 0.65, "Section 2 (Mid Tier)"),
                (0.65, 0.94, "Section 3 (Base Tier)"),
            ]
        elif num_tiers == 4:
            ratios = [
                (0.05, 0.27, "Section 1 (Top Tier)"),
                (0.27, 0.50, "Section 2 (Upper-Mid Tier)"),
                (0.50, 0.73, "Section 3 (Lower-Mid Tier)"),
                (0.73, 0.95, "Section 4 (Base Tier)"),
            ]
        else:
            step = 0.88 / max(1, num_tiers)
            ratios = []
            for i in range(num_tiers):
                y_s = 0.06 + i * step
                y_e = 0.06 + (i + 1) * step
                ratios.append((y_s, y_e, f"Section {i + 1} (Tier {i + 1})"))

        sections = []
        for y_s_ratio, y_e_ratio, name in ratios:
            y1 = float(height * y_s_ratio)
            y2 = float(height * y_e_ratio)
            sections.append((x1, y1, x2, y2, name))

        return sections

    def _detect_yolo_products(self, img: np.ndarray, conf_threshold: float = 0.20) -> List[Tuple[str, float, float, float, float, float]]:
        """Run YOLO inference and extract product-like bounding boxes.

        Returns list of (label, conf, x1, y1, x2, y2).
        """
        if self.yolo_model is None:
            return []

        try:
            results = self.yolo_model.predict(source=img, conf=conf_threshold, verbose=False)
            if not results or len(results) == 0 or results[0].boxes is None:
                return []

            height, width = img.shape[:2]
            detections = []
            # Product and grocery friendly COCO classes + retail classes
            excluded_labels = {"person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck"}

            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                label = self.yolo_model.names.get(cls_id, f"item_{cls_id}")
                if label in excluded_labels:
                    continue

                conf = float(box.conf[0].item())
                coords = box.xyxy[0].tolist()
                x1 = max(0.0, min(float(width), coords[0]))
                y1 = max(0.0, min(float(height), coords[1]))
                x2 = max(0.0, min(float(width), coords[2]))
                y2 = max(0.0, min(float(height), coords[3]))

                # Ensure minimum physical size
                if (x2 - x1) >= 15.0 and (y2 - y1) >= 20.0:
                    detections.append((label, conf, x1, y1, x2, y2))

            return detections
        except Exception as exc:
            logger.warning(f"YOLO product inference skipped or unavailable: {exc}")
            return []

    def _detect_retail_sku_contours(
        self,
        img: np.ndarray,
        tier_box: Tuple[float, float, float, float],
        existing_boxes: List[Tuple[float, float, float, float]],
    ) -> List[Tuple[str, float, float, float, float, float]]:
        """Specialized retail shelf contour and edge density detection for packaged grocery items

        (boxes, cartons, cans, jars, packages) not present in COCO classes.
        """
        tx1, ty1, tx2, ty2 = [int(v) for v in tier_box]
        h_tier = ty2 - ty1
        w_tier = tx2 - tx1

        if h_tier < 30 or w_tier < 50:
            return []

        tier_roi = img[ty1:ty2, tx1:tx2]
        gray = cv2.cvtColor(tier_roi, cv2.COLOR_BGR2GRAY)

        # Bilateral filter to smooth texture while preserving shelf product edges
        blurred = cv2.bilateralFilter(gray, 7, 50, 50)

        # Adaptive thresholding and vertical edge enhancement
        sobel_x = cv2.Sobel(blurred, cv2.CV_16S, 1, 0, ksize=3)
        abs_sobel = cv2.convertScaleAbs(sobel_x)

        # Morphological vertical dilation to merge vertical package packaging sides
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 11))
        dilated = cv2.morphologyEx(abs_sobel, cv2.MORPH_DILATE, kernel_v)

        _, thresh = cv2.threshold(dilated, 35, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        found_products = []
        for c in contours:
            cx, cy, cw, ch = cv2.boundingRect(c)
            # Filter by typical retail package aspect ratio and minimum area
            if cw < 20 or ch < 35:
                continue
            if cw > (w_tier * 0.45) or ch > (h_tier * 0.98):
                continue

            # Check that area has sufficient contrast/texture (avoid bare shelf backdrops)
            sub_roi = gray[cy:cy+ch, cx:cx+cw]
            if sub_roi.size == 0 or np.std(sub_roi) < 18.0:
                continue

            abs_x1 = float(tx1 + cx)
            abs_y1 = float(ty1 + cy)
            abs_x2 = float(abs_x1 + cw)
            abs_y2 = float(abs_y1 + ch)

            # Check if this box overlaps substantially with already detected YOLO boxes
            overlaps = False
            for ex1, ey1, ex2, ey2 in existing_boxes:
                # Intersection over Area
                ix1 = max(abs_x1, ex1)
                iy1 = max(abs_y1, ey1)
                ix2 = min(abs_x2, ex2)
                iy2 = min(abs_y2, ey2)
                iw = max(0.0, ix2 - ix1)
                ih = max(0.0, iy2 - iy1)
                inter_area = iw * ih
                min_area = min(cw * ch, (ex2 - ex1) * (ey2 - ey1))
                if min_area > 0 and (inter_area / min_area) > 0.40:
                    overlaps = True
                    break

            if not overlaps:
                # Compute confidence based on edge density and color contrast
                conf = min(0.95, max(0.65, float(np.std(sub_roi) / 45.0)))
                found_products.append(("packaged_good", conf, abs_x1, abs_y1, abs_x2, abs_y2))

        return found_products

    def analyze_shelf_image(
        self,
        img: np.ndarray,
        shelf_id: str = "shelf-bay-1",
        location: str = "Aisle 1 - Retail Shelf",
        num_tiers: int = 3,
        confidence_threshold: float = 0.20,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
        empty_threshold: Optional[float] = None,
    ) -> ShelfAnalysisOutcome:
        """Execute full retail shelf analysis, section division, product detection,

        empty space identification, and occupancy rate estimation.
        """
        warn_th = warning_threshold if warning_threshold is not None else self.DEFAULT_WARNING_THRESHOLD
        crit_th = critical_threshold if critical_threshold is not None else self.DEFAULT_CRITICAL_THRESHOLD
        emp_th = empty_threshold if empty_threshold is not None else self.DEFAULT_EMPTY_THRESHOLD

        height, width = img.shape[:2]

        # 1. Quality & Lighting Assessment
        is_reliable, reliability_reason, mean_lum, blur_var = self.assess_image_quality(img)

        # 2. Divide physical shelf tiers
        tier_specs = self.divide_shelf_sections((height, width, 3), num_tiers=num_tiers)

        # If lighting is inadequate, return non-reliable status (avoids false empty alerts)
        if not is_reliable:
            # Build placeholder sections with zero confidence and diagnosis
            sections_unreliable = []
            for idx, (tx1, ty1, tx2, ty2, name) in enumerate(tier_specs):
                sections_unreliable.append(
                    ShelfSectionResult(
                        section_index=idx + 1,
                        name=name,
                        x1=tx1,
                        y1=ty1,
                        x2=tx2,
                        y2=ty2,
                        occupancy_pct=0.0,
                        status="poor_lighting" if mean_lum < self.MIN_LUMINANCE_THRESHOLD else "blurry_image",
                        products=[],
                        empty_spaces=[],
                    )
                )

            # Draw visual diagnostic warning on annotated image
            annotated_unreliable = img.copy()
            diag_color = (0, 140, 255)  # Orange warning
            cv2.putText(
                annotated_unreliable,
                "DIAGNOSTIC: DETECTION UNCERTAIN - POOR ILLUMINATION / BLUR",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                diag_color,
                2,
                lineType=cv2.LINE_AA,
            )
            cv2.putText(
                annotated_unreliable,
                reliability_reason or "Camera sensor requires maintenance.",
                (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                lineType=cv2.LINE_AA,
            )

            success, buf = cv2.imencode(".jpg", annotated_unreliable, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64_img = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}" if success else None

            return ShelfAnalysisOutcome(
                shelf_id=shelf_id,
                location=location,
                width=width,
                height=height,
                overall_occupancy_pct=0.0,
                total_products_count=0,
                total_empty_spaces_count=0,
                status="poor_lighting" if mean_lum < self.MIN_LUMINANCE_THRESHOLD else "blurry_image",
                is_detection_reliable=False,
                reliability_note=reliability_reason,
                sections=sections_unreliable,
                all_detections=[],
                detection_counts={},
                annotated_image=b64_img,
            )

        # 3. Product Detection: YOLO + Specialized Retail Contour Pipeline
        yolo_dets = self._detect_yolo_products(img, conf_threshold=confidence_threshold)
        existing_boxes = [(d[2], d[3], d[4], d[5]) for d in yolo_dets]

        # Gather contour detections for each tier
        retail_dets = []
        for tx1, ty1, tx2, ty2, _ in tier_specs:
            skus = self._detect_retail_sku_contours(img, (tx1, ty1, tx2, ty2), existing_boxes)
            retail_dets.extend(skus)
            existing_boxes.extend([(s[2], s[3], s[4], s[5]) for s in skus])

        all_candidate_products = yolo_dets + retail_dets

        # 4. Map Products to Tiers and Calculate Gaps & Occupancy
        sections: List[ShelfSectionResult] = []
        all_detected_boxes: List[DetectedProductBox] = []
        detection_counts: Dict[str, int] = {}

        prod_idx_counter = 1

        for s_idx, (tx1, ty1, tx2, ty2, s_name) in enumerate(tier_specs):
            section_number = s_idx + 1
            tier_width = tx2 - tx1

            # Match products whose vertical center falls within this tier
            tier_products: List[DetectedProductBox] = []
            for label, conf, px1, py1, px2, py2 in all_candidate_products:
                py_center = (py1 + py2) / 2.0
                if ty1 <= py_center <= ty2:
                    p_box = DetectedProductBox(
                        id=f"prod-{prod_idx_counter}",
                        class_name=label,
                        confidence=conf,
                        x1=max(tx1, px1),
                        y1=max(ty1, py1),
                        x2=min(tx2, px2),
                        y2=min(ty2, py2),
                        width=max(0.0, min(tx2, px2) - max(tx1, px1)),
                        height=max(0.0, min(ty2, py2) - max(ty1, py1)),
                        section_index=section_number,
                        detection_source="yolo" if (label, conf, px1, py1, px2, py2) in yolo_dets else "retail_sku",
                    )
                    tier_products.append(p_box)
                    all_detected_boxes.append(p_box)
                    detection_counts[label] = detection_counts.get(label, 0) + 1
                    prod_idx_counter += 1

            # Sort products horizontally to detect gaps
            tier_products.sort(key=lambda p: p.x1)

            # Merge overlapping product spans for horizontal coverage
            merged_spans: List[Tuple[float, float]] = []
            for p in tier_products:
                if not merged_spans:
                    merged_spans.append((p.x1, p.x2))
                else:
                    last_start, last_end = merged_spans[-1]
                    if p.x1 <= last_end + 15.0:  # Allow 15px proximity tolerance
                        merged_spans[-1] = (last_start, max(last_end, p.x2))
                    else:
                        merged_spans.append((p.x1, p.x2))

            # Find empty spaces between product spans
            empty_spaces: List[EmptySpaceBox] = []
            min_gap_width = 30.0  # Gaps < 30px are treated as natural packaging gaps

            if not merged_spans:
                # Entire section is completely empty
                empty_spaces.append(
                    EmptySpaceBox(
                        x1=tx1,
                        y1=ty1,
                        x2=tx2,
                        y2=ty2,
                        width=tier_width,
                        height=ty2 - ty1,
                        section_index=section_number,
                        gap_type="empty_section",
                    )
                )
                occupancy_pct = 0.0
            else:
                # Leftmost gap
                if (merged_spans[0][0] - tx1) >= min_gap_width:
                    empty_spaces.append(
                        EmptySpaceBox(
                            x1=tx1,
                            y1=ty1,
                            x2=merged_spans[0][0],
                            y2=ty2,
                            width=merged_spans[0][0] - tx1,
                            height=ty2 - ty1,
                            section_index=section_number,
                            gap_type="out_of_stock_gap",
                        )
                    )

                # Intermediate gaps between product clusters
                for i in range(len(merged_spans) - 1):
                    gap_start = merged_spans[i][1]
                    gap_end = merged_spans[i + 1][0]
                    if (gap_end - gap_start) >= min_gap_width:
                        empty_spaces.append(
                            EmptySpaceBox(
                                x1=gap_start,
                                y1=ty1,
                                x2=gap_end,
                                y2=ty2,
                                width=gap_end - gap_start,
                                height=ty2 - ty1,
                                section_index=section_number,
                                gap_type="out_of_stock_gap",
                            )
                        )

                # Rightmost gap
                if (tx2 - merged_spans[-1][1]) >= min_gap_width:
                    empty_spaces.append(
                        EmptySpaceBox(
                            x1=merged_spans[-1][1],
                            y1=ty1,
                            x2=tx2,
                            y2=ty2,
                            width=tx2 - merged_spans[-1][1],
                            height=ty2 - ty1,
                            section_index=section_number,
                            gap_type="out_of_stock_gap",
                        )
                    )

                total_occupied_width = sum(span[1] - span[0] for span in merged_spans)
                occupancy_pct = min(100.0, max(0.0, (total_occupied_width / max(1.0, tier_width)) * 100.0))

            # Classify section status
            if occupancy_pct <= emp_th:
                s_status = "empty"
            elif occupancy_pct < crit_th:
                s_status = "critical"
            elif occupancy_pct < warn_th:
                s_status = "low"
            else:
                s_status = "ok"

            sections.append(
                ShelfSectionResult(
                    section_index=section_number,
                    name=s_name,
                    x1=tx1,
                    y1=ty1,
                    x2=tx2,
                    y2=ty2,
                    occupancy_pct=occupancy_pct,
                    status=s_status,
                    products=tier_products,
                    empty_spaces=empty_spaces,
                )
            )

        # 5. Overall Shelf Occupancy
        overall_occupancy = sum(s.occupancy_pct for s in sections) / max(1, len(sections))
        total_products = len(all_detected_boxes)
        total_empty = sum(len(s.empty_spaces) for s in sections)
        empty_sections_count = sum(1 for s in sections if s.status == "empty")

        if empty_sections_count == len(sections) or overall_occupancy <= emp_th:
            overall_status = "empty"
        elif empty_sections_count > 0 or overall_occupancy < crit_th:
            overall_status = "critical"
        elif overall_occupancy < warn_th:
            overall_status = "low"
        else:
            overall_status = "ok"

        # 6. Generate Rich OpenCV Annotated Visualization
        annotated = img.copy()
        overlay = img.copy()

        # A. Highlight Empty Spaces / Gaps with Red/Amber Wash and Bounding Box
        for sec in sections:
            for gap in sec.empty_spaces:
                gx1, gy1, gx2, gy2 = int(gap.x1), int(gap.y1), int(gap.x2), int(gap.y2)
                # Red wash for empty gap
                gap_color = (30, 30, 220) if gap.gap_type == "empty_section" else (0, 100, 240)
                cv2.rectangle(overlay, (gx1, gy1), (gx2, gy2), gap_color, -1)
                # Dashed/bold outline
                cv2.rectangle(annotated, (gx1, gy1), (gx2, gy2), gap_color, 2, lineType=cv2.LINE_AA)

                # Label tag
                gap_label = "EMPTY SHELF SECTION" if gap.gap_type == "empty_section" else f"OUT OF STOCK ({int(gap.width)}px)"
                (gw, gh), _ = cv2.getTextSize(gap_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                cv2.rectangle(annotated, (gx1, gy1), (gx1 + gw + 8, gy1 + gh + 6), gap_color, -1)
                cv2.putText(
                    annotated,
                    gap_label,
                    (gx1 + 4, gy1 + gh + 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (255, 255, 255),
                    1,
                    lineType=cv2.LINE_AA,
                )

        # Blend empty space wash (30% opacity)
        cv2.addWeighted(overlay, 0.30, annotated, 0.70, 0, annotated)

        # B. Draw Product Bounding Boxes
        prod_color = (34, 197, 94)  # Emerald green
        for p in all_detected_boxes:
            px1, py1, px2, py2 = int(p.x1), int(p.y1), int(p.x2), int(p.y2)
            cv2.rectangle(annotated, (px1, py1), (px2, py2), prod_color, 2, lineType=cv2.LINE_AA)

            ptag = f"{p.class_name} {int(p.confidence * 100)}%"
            (pw, ph), _ = cv2.getTextSize(ptag, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            cv2.rectangle(annotated, (px1, max(0, py1 - ph - 6)), (px1 + pw + 6, py1), prod_color, -1)
            cv2.putText(
                annotated,
                ptag,
                (px1 + 3, py1 - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (255, 255, 255),
                1,
                lineType=cv2.LINE_AA,
            )

        # C. Draw Tier Rails and Telemetry Tags
        for sec in sections:
            ty2 = int(sec.y2)
            tx1 = int(sec.x1)
            tx2 = int(sec.x2)
            # Divider line
            cv2.line(annotated, (tx1, ty2), (tx2, ty2), (200, 200, 200), 1, lineType=cv2.LINE_AA)

            # Section telemetry chip
            status_chip_color = (
                (30, 30, 220) if sec.status == "empty"
                else (0, 70, 220) if sec.status == "critical"
                else (0, 160, 240) if sec.status == "low"
                else (34, 197, 94)
            )
            sec_tag = f"{sec.name}: {sec.occupancy_pct:.0f}% Occupancy [{sec.status.upper()}] ({len(sec.products)} items)"
            (sw, sh), _ = cv2.getTextSize(sec_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            chip_y = max(18, int(sec.y1) + 16)
            cv2.rectangle(annotated, (tx1 + 5, chip_y - sh - 4), (tx1 + sw + 15, chip_y + 4), (20, 20, 20), -1)
            cv2.rectangle(annotated, (tx1 + 5, chip_y - sh - 4), (tx1 + sw + 15, chip_y + 4), status_chip_color, 1)
            cv2.putText(
                annotated,
                sec_tag,
                (tx1 + 10, chip_y - 1),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                lineType=cv2.LINE_AA,
            )

        # D. HUD Banner at Top
        hud_bg_color = (15, 23, 42)  # Slate-900
        cv2.rectangle(annotated, (0, 0), (width, 36), hud_bg_color, -1)
        hud_text = f"RETAILIQ SHELF VISION | {shelf_id} | OCCUPANCY: {overall_occupancy:.0f}% ({overall_status.upper()}) | PRODUCTS: {total_products} | GAPS: {total_empty}"
        cv2.putText(
            annotated,
            hud_text,
            (14, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
            lineType=cv2.LINE_AA,
        )

        success, enc = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 88])
        annotated_b64 = f"data:image/jpeg;base64,{base64.b64encode(enc).decode('utf-8')}" if success else None

        return ShelfAnalysisOutcome(
            shelf_id=shelf_id,
            location=location,
            width=width,
            height=height,
            overall_occupancy_pct=overall_occupancy,
            total_products_count=total_products,
            total_empty_spaces_count=total_empty,
            status=overall_status,
            is_detection_reliable=True,
            reliability_note=None,
            sections=sections,
            all_detections=all_detected_boxes,
            detection_counts=detection_counts,
            annotated_image=annotated_b64,
        )


_detector_instance: Optional[EmptyShelfDetector] = None


def get_empty_shelf_detector(yolo_model: Any = None) -> EmptyShelfDetector:
    """Singleton getter for the EmptyShelfDetector."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = EmptyShelfDetector(yolo_model=yolo_model)
    elif yolo_model is not None and _detector_instance.yolo_model is None:
        _detector_instance.yolo_model = yolo_model
    return _detector_instance
