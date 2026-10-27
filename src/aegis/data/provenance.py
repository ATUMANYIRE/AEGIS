"""Provenance registry and artifact auditing for AEGIS."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.data.schema import DatasetManifest


class ProvenanceRegistry:
    """Registry for data origins, cryptographic integrity checks, and scientific audit trails."""

    PROVENANCE_DISCLAIMER = (
        "AEGIS Milestone 1 strictly operates on a deterministic, parameterized synthetic "
        "medical supply chain benchmark. No external private health records or unverified "
        "public datasets have been integrated or claimed. The synthetic generator models "
        "structural dynamics (seasonality, facility tiers, lead times, surges, and stockouts) "
        "for algorithmic validation without fabricated claims of real-world clinical effectiveness."
    )

    @staticmethod
    def compute_file_sha256(file_path: str | Path) -> str:
        """Compute SHA-256 cryptographic digest of a file."""
        hasher = hashlib.sha256()
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Cannot compute hash: file does not exist at {path}")

        with path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def create_manifest(
        cls,
        dataset_name: str,
        version: str,
        seed: int,
        row_count: int,
        date_range: list[str],
        file_path: str | Path,
        hospitals: list[str],
        warehouses: list[str],
        categories: list[str],
        extra_metadata: dict[str, Any] | None = None,
    ) -> DatasetManifest:
        """Generate a validated DatasetManifest with cryptographic checksum."""
        sha256 = cls.compute_file_sha256(file_path)
        now_utc = datetime.now(UTC).isoformat()

        manifest = DatasetManifest(
            dataset_name=dataset_name,
            version=version,
            created_at_utc=now_utc,
            seed=seed,
            row_count=row_count,
            date_range=date_range,
            file_sha256=sha256,
            hospitals=hospitals,
            warehouses=warehouses,
            categories=categories,
            is_synthetic=True,
            provenance_statement=cls.PROVENANCE_DISCLAIMER,
        )
        return manifest

    @classmethod
    def save_manifest(cls, manifest: DatasetManifest, output_path: str | Path) -> None:
        """Save a DatasetManifest to JSON."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(), f, indent=2)

    @classmethod
    def load_and_verify_manifest(
        cls, manifest_path: str | Path, file_path: str | Path
    ) -> tuple[bool, str]:
        """Load manifest and verify SHA-256 against actual dataset file.

        Returns (is_valid, message).
        """
        path = Path(manifest_path)
        if not path.exists():
            return False, f"Manifest not found at {manifest_path}"

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest = DatasetManifest(**data)

        actual_sha = cls.compute_file_sha256(file_path)
        if actual_sha != manifest.file_sha256:
            return (
                False,
                f"SHA-256 mismatch! Manifest recorded: {manifest.file_sha256}, actual: {actual_sha}",
            )
        return True, "Manifest integrity verified."
