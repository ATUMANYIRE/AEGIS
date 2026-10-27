"""Unit tests for ProvenanceRegistry and dataset manifests."""

from pathlib import Path

from aegis.data.provenance import ProvenanceRegistry


def test_compute_file_sha256(tmp_path: Path) -> None:
    """Test SHA-256 calculation on known content."""
    test_file = tmp_path / "sample.txt"
    test_file.write_text("AEGIS Decision Intelligence 2026", encoding="utf-8")

    digest = ProvenanceRegistry.compute_file_sha256(test_file)
    assert isinstance(digest, str)
    assert len(digest) == 64  # SHA-256 produces 64 hex characters


def test_manifest_creation_and_verification(tmp_path: Path) -> None:
    """Test manifest creation, persistence, and integrity verification."""
    data_file = tmp_path / "data.parquet"
    data_file.write_bytes(b"Simulated binary data chunk")

    manifest = ProvenanceRegistry.create_manifest(
        dataset_name="test_dataset",
        version="1.0.0",
        seed=42,
        row_count=100,
        date_range=["2025-01-01", "2025-01-10"],
        file_path=data_file,
        hospitals=["H01", "H02"],
        warehouses=["W01"],
        categories=["PPE"],
    )

    manifest_path = tmp_path / "manifest.json"
    ProvenanceRegistry.save_manifest(manifest, manifest_path)
    assert manifest_path.exists()

    is_valid, msg = ProvenanceRegistry.load_and_verify_manifest(manifest_path, data_file)
    assert is_valid is True
    assert "verified" in msg.lower()


def test_manifest_tamper_detection(tmp_path: Path) -> None:
    """Test verification fails when dataset content is tampered with."""
    data_file = tmp_path / "data.parquet"
    data_file.write_bytes(b"Original content")

    manifest = ProvenanceRegistry.create_manifest(
        dataset_name="test_tamper",
        version="1.0.0",
        seed=42,
        row_count=10,
        date_range=["2025-01-01", "2025-01-02"],
        file_path=data_file,
        hospitals=["H01"],
        warehouses=["W01"],
        categories=["PPE"],
    )

    manifest_path = tmp_path / "manifest.json"
    ProvenanceRegistry.save_manifest(manifest, manifest_path)

    # Tamper with data file
    data_file.write_bytes(b"Tampered unauthorized content")

    is_valid, msg = ProvenanceRegistry.load_and_verify_manifest(manifest_path, data_file)
    assert is_valid is False
    assert "mismatch" in msg.lower()
