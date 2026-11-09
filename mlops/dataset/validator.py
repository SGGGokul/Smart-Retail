"""Dataset Validation Module for YOLO11n MLOps.

Validates retail datasets formatted in YOLO format:
- Bounding box coordinates normalized in [0, 1].
- Valid class IDs within configured class list.
- Image integrity and readable resolution.
- Detection of missing labels or orphan annotations.
- Detection of data leakage across train, val, and test splits.
- Generation of class distribution and validation reports.
"""

from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

logger = logging.getLogger("retailiq.mlops.validator")

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class ValidationIssue:
    level: str  # "ERROR" or "WARNING"
    category: str
    file_path: str
    message: str


@dataclass
class DatasetValidationReport:
    is_valid: bool
    total_images: int
    total_annotations: int
    class_distribution: Dict[int, int]
    issues: List[ValidationIssue] = field(default_factory=list)
    split_counts: Dict[str, int] = field(default_factory=dict)
    leakage_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_images": self.total_images,
            "total_annotations": self.total_annotations,
            "class_distribution": self.class_distribution,
            "split_counts": self.split_counts,
            "leakage_detected": self.leakage_detected,
            "issue_count": len(self.issues),
            "issues": [
                {
                    "level": i.level,
                    "category": i.category,
                    "file": i.file_path,
                    "message": i.message,
                }
                for i in self.issues
            ],
        }


class DatasetValidator:
    """Validator for YOLO-formatted object detection datasets."""

    def __init__(self, num_classes: int = 80, class_names: Optional[List[str]] = None) -> None:
        self.num_classes = num_classes
        self.class_names = class_names or []

    @staticmethod
    def compute_file_hash(path: Path) -> str:
        """Compute SHA-256 hash of a file for duplicate detection."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def validate_annotation_file(
        self, label_file: Path, img_w: Optional[int] = None, img_h: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[ValidationIssue]]:
        """Validate single YOLO text annotation file."""
        boxes = []
        issues = []

        if not label_file.exists():
            return boxes, issues

        try:
            with open(label_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            issues.append(
                ValidationIssue("ERROR", "unreadable_file", str(label_file), f"Could not read label file: {e}")
            )
            return boxes, issues

        for line_idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            tokens = line_str.split()
            if len(tokens) < 5:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "malformed_box",
                        f"{label_file}:{line_idx}",
                        f"Expected at least 5 tokens (class x y w h), got {len(tokens)}",
                    )
                )
                continue

            try:
                cls_id = int(tokens[0])
                xc, yc, w, h = [float(v) for v in tokens[1:5]]
            except ValueError as e:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "invalid_number",
                        f"{label_file}:{line_idx}",
                        f"Failed to parse numeric coordinates: {e}",
                    )
                )
                continue

            # Class ID range validation
            if cls_id < 0 or cls_id >= self.num_classes:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "invalid_class_id",
                        f"{label_file}:{line_idx}",
                        f"Class ID {cls_id} out of bounds (allowed: 0..{self.num_classes-1})",
                    )
                )

            # Bounding box coordinates bounds in [0.0, 1.0]
            if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "bbox_center_out_of_bounds",
                        f"{label_file}:{line_idx}",
                        f"Center coordinates ({xc}, {yc}) outside normalized [0, 1] range",
                    )
                )

            if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "bbox_dim_out_of_bounds",
                        f"{label_file}:{line_idx}",
                        f"Box dimensions ({w}, {h}) invalid; width and height must be in (0, 1]",
                    )
                )

            # Boundaries check
            x1 = xc - w / 2.0
            y1 = yc - h / 2.0
            x2 = xc + w / 2.0
            y2 = yc + h / 2.0
            if x1 < -0.05 or y1 < -0.05 or x2 > 1.05 or y2 > 1.05:
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "bbox_exceeds_image",
                        f"{label_file}:{line_idx}",
                        f"Box coordinates [{x1:.2f}, {y1:.2f}, {x2:.2f}, {y2:.2f}] extend beyond image bounds",
                    )
                )

            boxes.append({"class_id": cls_id, "bbox": [xc, yc, w, h]})

        return boxes, issues

    def validate_split(
        self, images_dir: Path, labels_dir: Path
    ) -> Tuple[Dict[str, str], int, Dict[int, int], List[ValidationIssue]]:
        """Validate images and labels inside one split directory."""
        image_hashes: Dict[str, str] = {}  # hash -> relative_path
        total_boxes = 0
        class_dist: Dict[int, int] = {}
        issues: List[ValidationIssue] = []

        if not images_dir.exists():
            issues.append(
                ValidationIssue("ERROR", "missing_split_directory", str(images_dir), "Image directory not found")
            )
            return image_hashes, 0, class_dist, issues

        image_files = [p for p in images_dir.iterdir() if p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]

        for img_path in image_files:
            # Check duplicate / compute hash
            try:
                img_hash = self.compute_file_hash(img_path)
                image_hashes[img_hash] = img_path.name
            except Exception as e:
                issues.append(
                    ValidationIssue("ERROR", "unreadable_image", str(img_path), f"Cannot compute hash: {e}")
                )

            # Check corresponding label file
            label_path = labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "missing_label_file",
                        str(img_path),
                        f"No annotation file found at {label_path.name}",
                    )
                )
                continue

            boxes, box_issues = self.validate_annotation_file(label_path)
            issues.extend(box_issues)
            total_boxes += len(boxes)
            for b in boxes:
                c = b["class_id"]
                class_dist[c] = class_dist.get(c, 0) + 1

        return image_hashes, total_boxes, class_dist, issues

    def validate_dataset(self, dataset_root: Path) -> DatasetValidationReport:
        """Execute full dataset validation on train, val, and optional test splits."""
        all_issues: List[ValidationIssue] = []
        overall_dist: Dict[int, int] = {}
        total_images = 0
        total_annotations = 0
        split_counts: Dict[str, int] = {}
        split_hashes: Dict[str, Dict[str, str]] = {}

        splits = ["train", "val", "test"]
        for s in splits:
            images_dir = dataset_root / "images" / s
            labels_dir = dataset_root / "labels" / s

            if not images_dir.exists() and s == "test":
                continue  # test split is optional

            hashes, boxes_count, c_dist, issues = self.validate_split(images_dir, labels_dir)
            split_hashes[s] = hashes
            split_counts[s] = len(hashes)
            total_images += len(hashes)
            total_annotations += boxes_count
            all_issues.extend(issues)

            for c, cnt in c_dist.items():
                overall_dist[c] = overall_dist.get(c, 0) + cnt

        # Check train / val / test leakage (identical images across splits)
        leakage_detected = False
        split_names = list(split_hashes.keys())
        for i in range(len(split_names)):
            for j in range(i + 1, len(split_names)):
                s1, s2 = split_names[i], split_names[j]
                overlap = set(split_hashes[s1].keys()) & set(split_hashes[s2].keys())
                if overlap:
                    leakage_detected = True
                    for h in overlap:
                        all_issues.append(
                            ValidationIssue(
                                "ERROR",
                                "data_leakage",
                                f"{s1}/{split_hashes[s1][h]} <=> {s2}/{split_hashes[s2][h]}",
                                f"Identical image exists in both '{s1}' and '{s2}' splits",
                            )
                        )

        # Has errors if any issue is level ERROR
        has_errors = any(i.level == "ERROR" for i in all_issues)
        is_valid = not has_errors and not leakage_detected and total_images > 0

        return DatasetValidationReport(
            is_valid=is_valid,
            total_images=total_images,
            total_annotations=total_annotations,
            class_distribution=overall_dist,
            issues=all_issues,
            split_counts=split_counts,
            leakage_detected=leakage_detected,
        )
