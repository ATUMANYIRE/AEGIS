"""Typed Pydantic schemas for AEGIS supply chain allocation and optimization."""

from typing import Literal

from pydantic import BaseModel, Field


class ShipmentAllocation(BaseModel):
    """Specific supply shipment from a warehouse to a hospital."""

    warehouse_id: str
    hospital_id: str
    category_id: str
    quantity: int = Field(..., ge=0, description="Shipped integer units")
    unit_transport_cost: float = Field(..., ge=0.0)
    total_transport_cost: float = Field(..., ge=0.0)


class RouteDispatch(BaseModel):
    """Activated transport corridor between a warehouse and hospital."""

    warehouse_id: str
    hospital_id: str
    active: bool
    vehicles_assigned: int = Field(..., ge=0)
    total_volume_units: int = Field(..., ge=0)
    fixed_activation_cost: float = Field(..., ge=0.0)
    vehicle_cost: float = Field(..., ge=0.0)


class FacilityShortage(BaseModel):
    """Evaluation of demand fulfillment and clinical shortage per facility and product."""

    hospital_id: str
    category_id: str
    demand_units: float = Field(..., ge=0.0)
    allocated_units: int = Field(..., ge=0)
    shortage_units: float = Field(..., ge=0.0)
    fill_rate: float = Field(..., ge=0.0, le=1.0)
    shortage_penalty: float = Field(..., ge=0.0)


class FairnessDiagnostics(BaseModel):
    """Comprehensive equity, service level, and feasibility metrics."""

    worst_facility_fill_rate: float = Field(..., ge=0.0, le=1.0)
    mean_facility_fill_rate: float = Field(..., ge=0.0, le=1.0)
    coverage_disparity: float = Field(
        ..., ge=0.0, le=1.0, description="Max fill rate - Min fill rate"
    )
    configured_min_coverage: float = Field(..., ge=0.0, le=1.0)
    is_fairness_satisfied: bool
    max_feasible_coverage: float | None = None
    bottleneck_warehouses: list[str] = Field(default_factory=list)
    total_inventory_deficit: float = Field(default=0.0, ge=0.0)
    relaxation_summary: str | None = None


class OptimizationResult(BaseModel):
    """Complete, self-contained record of an allocation optimization run."""

    policy: str
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "TIME_LIMIT", "ERROR"]
    solver_name: str = "HiGHS"
    total_cost: float = Field(..., description="Overall objective value")
    transportation_cost: float = Field(..., ge=0.0)
    fixed_route_cost: float = Field(..., ge=0.0)
    vehicle_cost: float = Field(..., ge=0.0)
    shortage_penalty: float = Field(..., ge=0.0)
    total_units_shipped: int = Field(..., ge=0)
    total_unmet_demand: float = Field(..., ge=0.0)
    allocations: list[ShipmentAllocation]
    routes: list[RouteDispatch]
    shortages: list[FacilityShortage]
    fairness: FairnessDiagnostics
    solver_runtime_sec: float = Field(..., ge=0.0)
    mip_gap: float = Field(default=0.0, ge=0.0)
    is_out_of_sample_evaluated: bool = False
    model_version: str = "0.2.0"
