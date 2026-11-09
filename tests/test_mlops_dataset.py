"""Unit tests for MLOps dataset validation and versioning."""

from pathlib import Path
import tempfile
import cv2
import numpy as np
import pytest

from mlops.dataset.validator import DatasetValidator
from mlops.dataset.versioning import DatasetVersioner


@pytest.fixture
def temp_dataset_dir():
    """Create a temporary valid YOLO dataset structure."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "images" / "train").mkdir(parents=True)
        (root / "images" / "val").mkdir(parents=True)
        (root / "labels" / "train").mkdir(parents=True)
        (root / "labels" / "val").mkdir(parents=True)

        # Generate a dummy synthetic image
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(root / "images" / "train" / "sample1.jpg"), img1)
        # Annotation: class 0, x=0.5, y=0.5, w=0.4, h=0.4
        with open(root / "labels" / "train" / "sample1.txt", "w") as f:
            f.write("0 0.5 0.5 0.4 0.4\n")

        # Generate second distinct image for val
        img2 = np.ones((100, 100, 3), dtype=np.uint8) * 128
        cv2.imwrite(str(root / "images" / "val" / "sample2.jpg"), img2)
        with open(root / "labels" / "val" / "sample2.txt", "w") as f:
            f.write("1 0.3 0.3 0.2 0.2\n")

        yield root


def test_valid_dataset_passes_validation(temp_dataset_dir):
    validator = DatasetValidator(num_classes=8)
    report = validator.validate_dataset(temp_dataset_dir)
    assert report.is_valid is True
    assert report.total_images == 2
    assert report.total_annotations == 2
    assert report.split_counts == {"train": 1, "val": 1}
    assert report.class_distribution == {0: 1, 1: 1}
    assert report.leakage_detected is False


def test_invalid_class_id_detected(temp_dataset_dir):
    # Add box with class 99 (out of range)
    with open(temp_dataset_dir / "labels" / "train" / "sample1.txt", "a") as f:
        f.write("99 0.5 0.5 0.2 0.2\n")

    validator = DatasetValidator(num_classes=8)
    report = validator.validate_dataset(temp_dataset_dir)
    assert report.is_valid is False
    assert any(i.category == "invalid_class_id" for i in report.issues)


def test_out_of_bounds_bbox_detected(temp_dataset_dir):
    # Add box with center coordinate > 1.0
    with open(temp_dataset_dir / "labels" / "train" / "sample1.txt", "w") as f:
        f.write("0 1.5 0.5 0.2 0.2\n")

    validator = DatasetValidator(num_classes=8)
    report = validator.validate_dataset(temp_dataset_dir)
    assert report.is_valid is False
    assert any(i.category == "bbox_center_out_of_bounds" for i in report.issues)


def test_data_leakage_detected(temp_dataset_dir):
    # Copy exact same image sample1.jpg into val split
    img_data = (temp_dataset_dir / "images" / "train" / "sample1.jpg").read_bytes()
    (temp_dataset_dir / "images" / "val" / "sample1_copy.jpg").write_bytes(img_data)
    (temp_dataset_dir / "labels" / "val" / "sample1_copy.txt").write_text("0 0.5 0.5 0.2 0.2\n")

    validator = DatasetValidator(num_classes=8)
    report = validator.validate_dataset(temp_dataset_dir)
    assert report.is_valid is False
    assert report.leakage_detected is True
    assert any(i.category == "data_leakage" for i in report.issues)


def test_dataset_versioning_and_manifest(temp_dataset_dir):
    manifest = DatasetVersioner.create_manifest(
        dataset_root=temp_dataset_dir,
        version_tag="v1.0.0",
        total_images=2,
        total_annotations=2,
        class_distribution={0: 1, 1: 1},
        split_counts={"train": 1, "val": 1},
        metadata={"retail_store": "store-104"},
    )
    manifest_path = temp_dataset_dir / "manifest.json"
    manifest.save(manifest_path)

    assert manifest.dataset_checksum is not None
    assert len(manifest.dataset_checksum) == 64
    assert DatasetVersioner.verify_manifest(temp_dataset_dir, manifest_path) is True
