"""Configuration definitions for AEGIS platform."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HospitalDefinition:
    """Static metadata defining a simulated hospital facility."""

    hospital_id: str
    name: str
    tier: str  # e.g., 'Level_1_Trauma', 'Regional_Referral', 'Community', 'Specialty_Clinic'
    bed_capacity: int
    base_demand_multiplier: float
    assigned_warehouse_id: str
    base_lead_time_days: int
    surge_sensitivity: float  # sensitivity to seasonal / public health surges


@dataclass(frozen=True)
class WarehouseDefinition:
    """Static metadata defining a regional supply warehouse."""

    warehouse_id: str
    name: str
    region: str
    capacity_units: int


@dataclass(frozen=True)
class ProductCategoryDefinition:
    """Static metadata defining a non-patient-specific medical consumable category."""

    category_id: str
    name: str
    description: str
    unit_measure: str
    base_daily_demand_per_bed: float
    weekend_ratio: float  # Weekend consumption relative to weekday (hospitals operate 24/7 but elective procedures dip)
    winter_surge_multiplier: float  # Higher respiratory/flu consumption during Q1/Q4
    lead_time_buffer_days: int


# Canonical simulated network topology (20 Hospitals, 3 Warehouses, 3 Consumable Categories)
WAREHOUSES: tuple[WarehouseDefinition, ...] = (
    WarehouseDefinition(
        warehouse_id="W01",
        name="Central Logistics Center",
        region="Central",
        capacity_units=150_000,
    ),
    WarehouseDefinition(
        warehouse_id="W02",
        name="Northern Regional Depot",
        region="North",
        capacity_units=80_000,
    ),
    WarehouseDefinition(
        warehouse_id="W03",
        name="Southern Regional Depot",
        region="South",
        capacity_units=80_000,
    ),
)

PRODUCT_CATEGORIES: tuple[ProductCategoryDefinition, ...] = (
    ProductCategoryDefinition(
        category_id="PPE",
        name="Personal Protective Equipment",
        description="Non-patient-specific gloves, N95/surgical masks, and isolation gowns",
        unit_measure="boxes (100 units/box)",
        base_daily_demand_per_bed=0.85,
        weekend_ratio=0.75,
        winter_surge_multiplier=1.45,
        lead_time_buffer_days=1,
    ),
    ProductCategoryDefinition(
        category_id="Sanitation",
        name="Disinfectants & Surface Sanitation",
        description="High-grade surface disinfectant wipes, sanitizing agents, and autoclave supplies",
        unit_measure="canisters (160 wipes/canister)",
        base_daily_demand_per_bed=0.55,
        weekend_ratio=0.70,
        winter_surge_multiplier=1.30,
        lead_time_buffer_days=1,
    ),
    ProductCategoryDefinition(
        category_id="Medical_Utility",
        name="Clinical Utility & Biohazard Disposal",
        description="Rigid sharps disposal containers, biohazard liners, and non-sterile utility gauze",
        unit_measure="units",
        base_daily_demand_per_bed=0.65,
        weekend_ratio=0.80,
        winter_surge_multiplier=1.15,
        lead_time_buffer_days=2,
    ),
)

HOSPITALS: tuple[HospitalDefinition, ...] = (
    HospitalDefinition(
        "H01", "Metropolitan University Hospital", "Level_1_Trauma", 850, 1.35, "W01", 1, 1.40
    ),
    HospitalDefinition(
        "H02", "City Center Emergency Hospital", "Level_1_Trauma", 720, 1.30, "W01", 1, 1.35
    ),
    HospitalDefinition(
        "H03", "St. Jude Regional Medical Center", "Level_1_Trauma", 650, 1.25, "W01", 2, 1.30
    ),
    HospitalDefinition(
        "H04", "Valley Memorial Academic Hospital", "Level_1_Trauma", 580, 1.20, "W02", 2, 1.25
    ),
    HospitalDefinition(
        "H05", "North Shore Regional Hospital", "Regional_Referral", 480, 1.10, "W02", 1, 1.20
    ),
    HospitalDefinition(
        "H06", "Highland District Hospital", "Regional_Referral", 420, 1.05, "W02", 2, 1.15
    ),
    HospitalDefinition(
        "H07", "Pinewood Health Care Center", "Regional_Referral", 390, 1.00, "W02", 2, 1.15
    ),
    HospitalDefinition(
        "H08", "Timberline County Hospital", "Regional_Referral", 360, 0.98, "W02", 3, 1.10
    ),
    HospitalDefinition(
        "H09", "Cascade Provincial Hospital", "Regional_Referral", 340, 0.95, "W02", 3, 1.10
    ),
    HospitalDefinition(
        "H10", "Southern Cross General Hospital", "Regional_Referral", 450, 1.08, "W03", 1, 1.20
    ),
    HospitalDefinition(
        "H11", "Harborview Community Hospital", "Community", 260, 0.88, "W01", 2, 1.05
    ),
    HospitalDefinition(
        "H12", "Riverside Community Hospital", "Community", 240, 0.85, "W01", 2, 1.00
    ),
    HospitalDefinition("H13", "Oakwood Suburban Hospital", "Community", 210, 0.82, "W01", 2, 1.00),
    HospitalDefinition("H14", "Sunridge Valley Hospital", "Community", 190, 0.80, "W03", 2, 0.95),
    HospitalDefinition("H15", "Bayou Health Care Center", "Community", 180, 0.78, "W03", 2, 0.95),
    HospitalDefinition("H16", "Lakeside Memorial Clinic", "Community", 160, 0.75, "W03", 3, 0.90),
    HospitalDefinition(
        "H17", "Prairie View Community Hospital", "Community", 150, 0.72, "W03", 3, 0.90
    ),
    HospitalDefinition(
        "H18", "Summit Surgical Center", "Specialty_Clinic", 120, 0.68, "W01", 1, 0.85
    ),
    HospitalDefinition(
        "H19", "Crestview Pediatric Annex", "Specialty_Clinic", 110, 0.65, "W02", 2, 0.90
    ),
    HospitalDefinition(
        "H20", "Delta Ambulatory Care Pavilion", "Specialty_Clinic", 90, 0.60, "W03", 2, 0.80
    ),
)


@dataclass
class AegisConfig:
    """Master configuration for AEGIS data generation, training, and evaluation."""

    seed: int = 42
    start_date: str = "2025-01-01"
    simulation_days: int = 365
    surge_probability: float = 0.035
    missingness_rate: float = 0.03
    train_end_day: int = 260
    val_end_day: int = 310
    prediction_intervals: list[float] = field(default_factory=lambda: [0.10, 0.50, 0.90])

    # Path configurations
    data_dir: Path = field(default_factory=lambda: Path("data"))
    raw_data_path: Path = field(
        default_factory=lambda: Path("data/raw/synthetic_consumables.parquet")
    )
    processed_data_path: Path = field(
        default_factory=lambda: Path("data/processed/featured_dataset.parquet")
    )
    models_dir: Path = field(default_factory=lambda: Path("models"))
    metrics_dir: Path = field(default_factory=lambda: Path("metrics"))
