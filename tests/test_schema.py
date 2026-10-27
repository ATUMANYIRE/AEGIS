"""Unit tests for Pydantic schema validation models."""

from datetime import date

import pytest
from pydantic import ValidationError

from aegis.data.schema import DailyDemandRecord, DatasetManifest


def test_valid_daily_demand_record() -> None:
    """Test valid observation complies with DailyDemandRecord schema."""
    record = DailyDemandRecord(
        date=date(2025, 1, 15),
        hospital_id="H01",
        warehouse_id="W01",
        category_id="PPE",
        demand_units=540.5,
        observed_consumption_units=540.5,
        reported_inventory_units=2100.0,
        stockout_flag=0,
        surge_factor=1.0,
        lead_time_days=2,
        is_synthetic=True,
        synthetic_scenario="baseline",
        missing_report_flag=0,
    )
    assert record.hospital_id == "H01"
    assert record.demand_units == 540.5
    assert record.is_synthetic is True


def test_invalid_hospital_id() -> None:
    """Test invalid hospital regex pattern fails schema validation."""
    with pytest.raises(ValidationError):
        DailyDemandRecord(
            date=date(2025, 1, 15),
            hospital_id="H99",  # Invalid ID (only H01-H20 permitted)
            warehouse_id="W01",
            category_id="PPE",
            demand_units=100.0,
            observed_consumption_units=100.0,
            reported_inventory_units=500.0,
            stockout_flag=0,
            surge_factor=1.0,
            lead_time_days=2,
            is_synthetic=True,
            synthetic_scenario="baseline",
            missing_report_flag=0,
        )


def test_invalid_warehouse_id() -> None:
    """Test invalid warehouse ID fails schema validation."""
    with pytest.raises(ValidationError):
        DailyDemandRecord(
            date=date(2025, 1, 15),
            hospital_id="H01",
            warehouse_id="W05",  # Invalid (only W01-W03 permitted)
            category_id="PPE",
            demand_units=100.0,
            observed_consumption_units=100.0,
            reported_inventory_units=500.0,
            stockout_flag=0,
            surge_factor=1.0,
            lead_time_days=2,
            is_synthetic=True,
            synthetic_scenario="baseline",
            missing_report_flag=0,
        )


def test_negative_demand_fails() -> None:
    """Test negative demand values are rejected by schema constraints."""
    with pytest.raises(ValidationError):
        DailyDemandRecord(
            date=date(2025, 1, 15),
            hospital_id="H01",
            warehouse_id="W01",
            category_id="Sanitation",
            demand_units=-15.0,  # Negative demand strictly prohibited
            observed_consumption_units=0.0,
            reported_inventory_units=500.0,
            stockout_flag=0,
            surge_factor=1.0,
            lead_time_days=2,
            is_synthetic=True,
            synthetic_scenario="baseline",
            missing_report_flag=0,
        )


def test_non_synthetic_marker_fails() -> None:
    """Test is_synthetic=False is rejected to prevent unverified real-data claims."""
    with pytest.raises(ValidationError):
        DailyDemandRecord(
            date=date(2025, 1, 15),
            hospital_id="H01",
            warehouse_id="W01",
            category_id="Medical_Utility",
            demand_units=100.0,
            observed_consumption_units=100.0,
            reported_inventory_units=500.0,
            stockout_flag=0,
            surge_factor=1.0,
            lead_time_days=2,
            is_synthetic=False,  # Prohibited
            synthetic_scenario="baseline",
            missing_report_flag=0,
        )


def test_dataset_manifest_schema() -> None:
    """Test DatasetManifest validation."""
    manifest = DatasetManifest(
        dataset_name="aegis_test",
        version="1.0.0",
        created_at_utc="2026-10-27T00:00:00Z",
        seed=42,
        row_count=1000,
        date_range=["2025-01-01", "2025-12-31"],
        file_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        hospitals=["H01", "H02"],
        warehouses=["W01"],
        categories=["PPE"],
        is_synthetic=True,
        provenance_statement="Synthetic benchmark",
    )
    assert manifest.seed == 42
    assert manifest.is_synthetic is True
