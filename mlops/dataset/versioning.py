"""Dataset Versioning and Manifest Management Module.

Computes reproducible checksums (SHA256) of datasets and serializes immutable
manifests for training pipeline verification and provenance tracking.
"""

from dataclasses import dataclass, field
import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("retailiq.mlops.versioning")


@dataclass
class DatasetManifest:
    version_tag: str
    created_at: str
    dataset_checksum: str
    total_images: int
    total_annotations: int
    class_distribution: Dict[int, int]
    split_counts: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_tag": self.version_tag,
            "created_at": self.created_at,
            "dataset_checksum": self.dataset_checksum,
            "total_images": self.total_images,
            "total_annotations": self.total_annotations,
            "class_distribution": self.class_distribution,
            "split_counts": self.split_counts,
            "metadata": self.metadata,
        }

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class DatasetVersioner:
    """Computes reproducible content hashes across YOLO datasets and creates manifests."""

    @staticmethod
    def compute_dataset_hash(dataset_root: Path) -> str:
        """Compute holistic deterministic SHA256 of all images and annotations in dataset."""
        hasher = hashlib.sha256()

        # Collect all files deterministically sorted
        all_files: List[Path] = []
        for p in dataset_root.rglob("*"):
            if p.is_file() and not p.name.endswith(".json") and not p.name.endswith(".lock"):
                all_files.append(p)
        all_files.sort(key=lambda p: str(p.relative_to(dataset_root)).replace("\\", "/"))

        for file_path in all_files:
            rel_str = str(file_path.relative_to(dataset_root)).replace("\\", "/")
            hasher.update(rel_str.encode("utf-8"))
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)

        return hasher.hexdigest()

    @classmethod
    def create_manifest(
        cls,
        dataset_root: Path,
        version_tag: str,
        total_images: int,
        total_annotations: int,
        class_distribution: Dict[int, int],
        split_counts: Dict[str, int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DatasetManifest:
        """Generate a validated dataset manifest."""
        checksum = cls.compute_dataset_hash(dataset_root)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        manifest = DatasetManifest(
            version_tag=version_tag,
            created_at=now_str,
            dataset_checksum=checksum,
            total_images=total_images,
            total_annotations=total_annotations,
            class_distribution=class_distribution,
            split_counts=split_counts,
            metadata=metadata or {},
        )
        return manifest

    @classmethod
    def verify_manifest(cls, dataset_root: Path, manifest_path: Path) -> bool:
        """Verify whether dataset matches its recorded checksum."""
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        current_hash = cls.compute_dataset_hash(dataset_root)
        return current_hash == data.get("dataset_checksum")
