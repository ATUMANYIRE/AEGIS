"""Schema definitions and Pydantic validation models for AEGIS data."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DailyDemandRecord(BaseModel):
    """Schema for daily demand and supply observations per facility and product."""

    date: date
    hospital_id: str = Field(..., pattern=r"^H(0[1-9]|1[0-9]|20)$")
    warehouse_id: str = Field(..., pattern=r"^W0[1-3]$")
    category_id: Literal["PPE", "Sanitation", "Medical_Utility"]
    demand_units: float = Field(..., ge=0.0, description="True unconstrained demand")
    observed_consumption_units: float = Field(
        ..., ge=0.0, description="Observed consumption clipped by stockout or telemetry"
    )
    reported_inventory_units: float = Field(
        ..., ge=0.0, description="Recorded inventory level at end of day"
    )
    stockout_flag: int = Field(
        ..., ge=0, le=1, description="Binary flag indicating supply exhaustion"
    )
    surge_factor: float = Field(
        ..., ge=1.0, description="Surge multiplier applied to baseline demand"
    )
    lead_time_days: int = Field(
        ..., ge=1, le=14, description="Simulated transport lead time in days"
    )
    is_synthetic: bool = Field(True, description="Strict synthetic data marker")
    synthetic_scenario: str = Field(
        ..., description="Scenario identifier e.g. baseline or outbreak"
    )
    missing_report_flag: int = Field(
        ..., ge=0, le=1, description="Flag indicating simulated telemetry/reporting drop"
    )

    @field_validator("is_synthetic")
    @classmethod
    def validate_is_synthetic(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "AEGIS Milestone 1 synthetic generator records must have is_synthetic=True"
            )
        return v


class DatasetManifest(BaseModel):
    """Manifest documenting data generation parameters, integrity hashes, and provenance."""

    dataset_name: str
    version: str
    created_at_utc: str
    seed: int
    row_count: int
    date_range: list[str]
    file_sha256: str
    hospitals: list[str]
    warehouses: list[str]
    categories: list[str]
    is_synthetic: bool = True
    provenance_statement: str
