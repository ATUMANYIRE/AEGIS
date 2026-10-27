"""Structured Pydantic schemas for the GenAI Decision Explanation Layer."""

from pydantic import BaseModel, Field


class ForecastUncertaintyContext(BaseModel):
    """Contextual forecast metrics and prediction intervals for a specific facility and product."""

    facility_id: str = Field(description="Hospital identifier, e.g. H01")
    facility_name: str = Field(description="Hospital name")
    facility_tier: str = Field(description="Clinical tier, e.g. Level 1 Trauma")
    product_category: str = Field(description="Product category, e.g. PPE")
    point_forecast: float = Field(description="Expected demand forecast (p50 median)")
    p10_lower: float = Field(description="10th percentile lower demand bound")
    p90_upper: float = Field(description="90th percentile upper demand bound")
    prediction_interval_width: float = Field(description="p90 - p10 prediction interval width")
    historical_wape_pct: float = Field(default=14.62, description="Validated model WAPE percentage")


class SHAPContributionContext(BaseModel):
    """Local TreeSHAP feature attributions explaining the demand forecast."""

    feature_name: str = Field(description="Feature column name")
    feature_value: float = Field(description="Observed feature value for instance")
    shap_value: float = Field(description="Marginal additive SHAP contribution phi_i")
    contribution_direction: str = Field(description="'increases_demand' or 'decreases_demand'")


class BindingConstraintContext(BaseModel):
    """Identified physical or policy binding constraints in the optimization model."""

    constraint_type: str = Field(
        description="e.g. 'warehouse_inventory', 'dispatch_throughput', 'vehicle_capacity', 'fairness_floor'"
    )
    entity_id: str = Field(description="Entity identifier, e.g. W01, PPE, or Network")
    utilization_pct: float = Field(description="Capacity or target utilization percentage")
    is_binding: bool = Field(description="True if constraint is active at capacity/floor")
    impact_description: str = Field(description="Operational impact of this constraint")


class OptimizationResultContext(BaseModel):
    """Operations research optimization output context."""

    policy: str = Field(
        description="Policy name, e.g. Stochastic_MILP, Deterministic_MILP, Greedy, Proportional"
    )
    status: str = Field(description="Solver status: Optimal, Feasible, Infeasible, or Timeout")
    runtime_ms: float = Field(description="Solver execution latency in milliseconds")
    total_cost: float = Field(description="Total objective or evaluated cost ($)")
    transport_cost: float = Field(description="Variable transit cost ($)")
    route_activation_cost: float = Field(description="Fixed route activation cost ($)")
    vehicle_cost: float = Field(description="Vehicle trip dispatch cost ($)")
    shortage_penalty: float = Field(description="Evaluated recourse shortage penalty ($)")
    service_coverage_pct: float = Field(description="Network-wide fulfilled demand percentage")
    total_unmet_demand: float = Field(description="Total units of unmet demand across network")
    facility_allocated_units: int = Field(description="Units allocated to the focal facility")
    facility_fill_rate_pct: float = Field(description="Fill rate percentage at the focal facility")


class FairnessOutcomeContext(BaseModel):
    """Equity and clinical tier protection metrics across the network."""

    min_fill_rate_pct: float = Field(description="Lowest facility fill rate")
    mean_fill_rate_pct: float = Field(description="Mean facility fill rate")
    max_fill_rate_pct: float = Field(description="Highest facility fill rate")
    disparity_ratio: float = Field(description="Ratio of min fill rate to max fill rate")
    trauma_tier_fill_rate_pct: float = Field(
        description="Average fill rate for Level 1 Trauma centers"
    )
    community_tier_fill_rate_pct: float = Field(
        description="Average fill rate for Community hospitals"
    )
    specialty_tier_fill_rate_pct: float = Field(
        description="Average fill rate for Specialty clinics"
    )


class ScenarioDifferenceContext(BaseModel):
    """Active scenario parameter adjustments relative to nominal baseline."""

    scenario_name: str = Field(default="Custom Scenario", description="Scenario label")
    demand_surge_pct: float = Field(default=0.0, description="Demand surge percentage applied")
    stock_multiplier_pct: float = Field(
        default=100.0, description="Warehouse stock multiplier percentage"
    )
    vehicle_capacity_units: int = Field(default=300, description="Vehicle capacity in units")
    min_service_coverage_target: float = Field(
        default=0.0, description="Minimum service coverage target alpha_min"
    )
    shortage_penalty_multiplier: float = Field(
        default=1.0, description="Shortage penalty weighting multiplier"
    )


class ProvenanceContext(BaseModel):
    """Cryptographic and operational provenance metadata."""

    dataset_manifest_hash: str = Field(
        default="38a9d18... (SHA-256)", description="Dataset manifest hash"
    )
    model_version: str = Field(
        default="xgboost_demand_v1.0", description="Forecasting model version"
    )
    random_seed: int = Field(default=42, description="Deterministic benchmark seed")
    synthetic_data_notice: str = Field(
        default="EXPLICITLY_SYNTHETIC: 20 hospitals, 3 warehouses, 3 categories, 365 days",
        description="Synthetic data provenance statement",
    )


class DecisionContextRecord(BaseModel):
    """Complete, structured decision record containing verified metrics for GenAI explanation."""

    forecast: ForecastUncertaintyContext
    top_shap_contributions: list[SHAPContributionContext]
    shap_base_value: float
    optimization: OptimizationResultContext
    binding_constraints: list[BindingConstraintContext]
    fairness: FairnessOutcomeContext
    scenario_deltas: ScenarioDifferenceContext
    provenance: ProvenanceContext
    user_query: str | None = Field(
        default=None, description="Optional operator question or scenario note"
    )


class GroundingAudit(BaseModel):
    """Verification audit confirming the explanation contains only factual, grounded claims."""

    is_grounded: bool = Field(
        description="True if all numerical claims match the decision context record"
    )
    verified_numerical_claims: list[str] = Field(
        default_factory=list, description="Verified facts cited in text"
    )
    unverified_claims: list[str] = Field(
        default_factory=list, description="Any ungrounded statements detected"
    )
    prompt_injection_detected: bool = Field(
        default=False, description="True if prompt injection was detected & mitigated"
    )
    provider_used: str = Field(
        description="e.g. 'gemini-1.5-flash', 'openai-gpt-4o', or 'deterministic-fallback'"
    )
    latency_ms: float = Field(description="Generation and validation latency in milliseconds")


class GenAIDecisionExplanation(BaseModel):
    """Pydantic output schema for the GenAI Decision Explanation Layer."""

    executive_summary: str = Field(
        description="1-2 sentence executive operational explanation of the allocation"
    )
    forecast_rationale: str = Field(
        description="Explanation of key predictive drivers (TreeSHAP) behind demand forecast"
    )
    allocation_rationale: str = Field(
        description="Explanation of why this allocation was selected given binding constraints"
    )
    fairness_and_risk_assessment: str = Field(
        description="Assessment of clinical tier protection, equity, and shortage impacts"
    )
    recommended_operational_action: str = Field(
        description="Logistical supply chain recommendations (non-clinical)"
    )
    grounding_audit: GroundingAudit = Field(
        description="Grounding and factual verification audit results"
    )
    is_fallback: bool = Field(description="True if generated by deterministic offline fallback")
    clinical_disclaimer: str = Field(
        default="GOVERNANCE NOTICE: AEGIS is a supply chain logistics intelligence platform. It does NOT make clinical diagnoses, prescribe drug dosages, or alter patient triage protocols. Human operator review is required prior to physical dispatch.",
        description="Mandatory governance disclaimer",
    )
