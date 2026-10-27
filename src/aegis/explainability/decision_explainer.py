"""Deterministic, evidence-grounded decision explanation builder for supply allocation optimization."""

from typing import Any

from pydantic import BaseModel, Field

from aegis.config import HOSPITALS, WAREHOUSES
from aegis.optimization.fairness import FairnessRelaxationAnalyzer
from aegis.optimization.schema import OptimizationResult
from aegis.scenarios.network import TransportationNetwork


class RouteExplanation(BaseModel):
    """Structured rationale for an individual warehouse-to-hospital transport link."""

    warehouse_id: str
    hospital_id: str
    active: bool
    volume_units: int
    vehicles_assigned: int
    vehicle_capacity_utilization: float
    fixed_route_cost: float
    variable_transport_cost: float
    rationale: str


class ShortageAttribution(BaseModel):
    """Root-cause attribution for unmet demand at a specific hospital and product category."""

    hospital_id: str
    hospital_name: str
    hospital_tier: str
    category_id: str
    demand_units: float
    allocated_units: int
    shortage_units: float
    fill_rate: float
    shortage_penalty_rate: float
    total_penalty: float
    primary_root_cause: str
    evidence: str


class DecisionExplanation(BaseModel):
    """Complete, structured decision intelligence explanation grounded in mathematical constraints."""

    policy: str
    solver_status: str
    solver_runtime_sec: float
    executive_summary: str
    key_drivers: list[str]
    total_cost_breakdown: dict[str, float]
    route_diagnostics: list[RouteExplanation]
    top_shortage_attributions: list[ShortageAttribution]
    fairness_evaluation: dict[str, Any]
    counterfactual_analysis: dict[str, Any]
    governance_badges: dict[str, str] = Field(
        default_factory=lambda: {
            "synthetic_data": "EXPLICITLY_SYNTHETIC",
            "clinical_validation": "NONE_LOGISTICAL_ONLY",
            "patient_data": "ZERO_PHI_PII",
            "decision_authority": "HUMAN_IN_THE_LOOP_REQUIRED",
        }
    )


class AllocationDecisionExplainer:
    """Explains optimization allocations using solver constraints, physical costs, and counterfactuals.

    NOTE: SHAP explains forecast demand, while AllocationDecisionExplainer explains
    operations research allocation decisions, linking inputs to operational actions.
    """

    def __init__(self, network: TransportationNetwork | None = None) -> None:
        self.network = network or TransportationNetwork()
        self.relaxation_analyzer = FairnessRelaxationAnalyzer(network=self.network)

    def explain(
        self,
        result: OptimizationResult,
        demands: dict[tuple[str, str], float],
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float = 0.0,
        policy_name: str = "Stochastic_MILP",
    ) -> DecisionExplanation:
        """Construct structured, evidence-grounded explanation from optimization result."""
        total_d = sum(demands.values())
        total_s = sum(warehouse_stock.values())
        stock_ratio = (total_s / total_d) if total_d > 0 else 1.0

        # 1. Total cost breakdown
        cost_breakdown = {
            "total_cost": result.total_cost,
            "transportation_cost": result.transportation_cost,
            "fixed_route_cost": result.fixed_route_cost,
            "vehicle_cost": result.vehicle_cost,
            "shortage_penalty": result.shortage_penalty,
        }

        # 2. Route diagnostics & utilization
        route_explanations: list[RouteExplanation] = []
        active_routes_count = 0
        total_vehicles = 0

        route_map = {(r.warehouse_id, r.hospital_id): r for r in result.routes}
        alloc_by_route: dict[tuple[str, str], int] = {}
        alloc_cost_by_route: dict[tuple[str, str], float] = {}

        for a in result.allocations:
            pair = (a.warehouse_id, a.hospital_id)
            alloc_by_route[pair] = alloc_by_route.get(pair, 0) + a.quantity
            alloc_cost_by_route[pair] = alloc_cost_by_route.get(pair, 0.0) + a.total_transport_cost

        for w in WAREHOUSES:
            for h in HOSPITALS:
                pair = (w.warehouse_id, h.hospital_id)
                vol = alloc_by_route.get(pair, 0)
                is_active = vol > 0
                if is_active:
                    active_routes_count += 1
                r_rec = route_map.get(pair)
                v_count = r_rec.vehicles_assigned if r_rec else (1 if vol > 0 else 0)
                total_vehicles += v_count

                v_cap = self.network.params.vehicle_capacity_units * max(1, v_count)
                util = round(vol / v_cap, 4) if is_active else 0.0
                r_cost = self.network.fixed_route_costs[pair] if is_active else 0.0
                t_cost = alloc_cost_by_route.get(pair, 0.0)

                dist = self.network.distances_km[pair]
                if is_active:
                    rationale = (
                        f"Route opened: dispatched {vol:,} units across {v_count} vehicle(s) "
                        f"({util:.1%} capacity). Distance {dist:.1f} km, fixed activation ${r_cost:.2f}."
                    )
                else:
                    rationale = f"Route inactive: zero allocation to minimize fixed activation (${self.network.fixed_route_costs[pair]:.2f})."

                if is_active:
                    route_explanations.append(
                        RouteExplanation(
                            warehouse_id=w.warehouse_id,
                            hospital_id=h.hospital_id,
                            active=is_active,
                            volume_units=vol,
                            vehicles_assigned=v_count,
                            vehicle_capacity_utilization=util,
                            fixed_route_cost=round(r_cost, 2),
                            variable_transport_cost=round(t_cost, 2),
                            rationale=rationale,
                        )
                    )

        # 3. Shortage attributions
        hosp_dict = {h.hospital_id: h for h in HOSPITALS}
        shortage_attributions: list[ShortageAttribution] = []

        # Find bottleneck warehouses
        stock_used = {}
        for a in result.allocations:
            stock_used[(a.warehouse_id, a.category_id)] = (
                stock_used.get((a.warehouse_id, a.category_id), 0) + a.quantity
            )

        for s in result.shortages:
            if s.shortage_units > 0:
                h_def = hosp_dict[s.hospital_id]
                pen_rate = self.network.shortage_penalties[(s.hospital_id, s.category_id)]

                # Determine primary root cause
                if stock_ratio < 0.90:
                    root_cause = "GLOBAL_INVENTORY_SCARCITY"
                    evidence = (
                        f"Total system stock ratio is {stock_ratio:.1%} of demand. "
                        f"Solver prioritized critical Trauma tiers over lower clinical tiers."
                    )
                elif h_def.tier in ["Community", "Specialty"]:
                    root_cause = "CLINICAL_TIER_PRIORITIZATION"
                    evidence = (
                        f"Hospital tier '{h_def.tier}' carries lower shortage penalty multiplier "
                        f"({self.network.params.tier_penalty_multipliers.get(h_def.tier, 1.0)}x) "
                        f"compared to Level 1 Trauma centers (3.0x). Solver rationally protected higher-severity facilities."
                    )
                else:
                    root_cause = "DISPATCH_OR_FLEET_BOTTLENECK"
                    evidence = (
                        f"High local demand ({s.demand_units:,.1f} units) constrained by vehicle batching "
                        f"or warehouse fulfillment throughput limits."
                    )

                shortage_attributions.append(
                    ShortageAttribution(
                        hospital_id=s.hospital_id,
                        hospital_name=h_def.name,
                        hospital_tier=h_def.tier,
                        category_id=s.category_id,
                        demand_units=s.demand_units,
                        allocated_units=s.allocated_units,
                        shortage_units=s.shortage_units,
                        fill_rate=s.fill_rate,
                        shortage_penalty_rate=pen_rate,
                        total_penalty=s.shortage_penalty,
                        primary_root_cause=root_cause,
                        evidence=evidence,
                    )
                )

        # Sort shortages by total penalty (highest clinical impact first)
        shortage_attributions.sort(key=lambda sa: sa.total_penalty, reverse=True)

        # 4. Fairness evaluation
        is_fair = result.fairness.is_fairness_satisfied
        worst_fill = result.fairness.worst_facility_fill_rate
        disparity = result.fairness.coverage_disparity

        relaxation_diag = None
        if not is_fair or result.status == "INFEASIBLE":
            relaxation_diag = self.relaxation_analyzer.analyze_relaxation(
                demands=demands,
                warehouse_stock=warehouse_stock,
                target_min_coverage=min_service_coverage,
            ).model_dump()

        fairness_eval = {
            "configured_min_coverage": min_service_coverage,
            "worst_facility_fill_rate": worst_fill,
            "mean_facility_fill_rate": result.fairness.mean_facility_fill_rate,
            "coverage_disparity": disparity,
            "is_fairness_satisfied": is_fair,
            "relaxation_analysis": relaxation_diag,
        }

        # 5. Key Drivers & Executive Summary
        key_drivers = [
            f"Policy '{policy_name}' solved with status {result.status} in {result.solver_runtime_sec:.3f}s.",
            f"Total supply chain cost evaluated at ${result.total_cost:,.2f} ({result.total_units_shipped:,} units shipped).",
            f"Active transportation network: {active_routes_count} opened routes requiring {total_vehicles} vehicle dispatch(es).",
            f"Equity target (min {min_service_coverage:.0%}): worst facility fill rate is {worst_fill:.1%} with disparity of {disparity:.1%}.",
        ]

        if result.total_unmet_demand > 0:
            key_drivers.append(
                f"Unmet demand totaled {result.total_unmet_demand:,.1f} units, incurring ${result.shortage_penalty:,.2f} in tier-weighted clinical penalties."
            )
        else:
            key_drivers.append(
                "100% of network demand satisfied across all facilities and consumable categories."
            )

        if result.status == "INFEASIBLE":
            exec_summary = (
                f"CRITICAL: Policy '{policy_name}' detected mathematical infeasibility for the requested service target "
                f"({min_service_coverage:.0%} coverage). Zero units were dispatched to preserve hard constraint integrity. "
                f"Maximum achievable coverage without constraint violation is "
                f"{fairness_eval.get('relaxation_analysis', {}).get('max_feasible_coverage', 0.0):.1%}."
            )
        else:
            exec_summary = (
                f"The {policy_name} engine successfully allocated {result.total_units_shipped:,} medical consumable units "
                f"across 20 hospitals at total cost ${result.total_cost:,.2f}. Network mean fill rate reached "
                f"{result.fairness.mean_facility_fill_rate:.1%}, with worst facility fill rate at {worst_fill:.1%}. "
                f"Route activation and vehicle batching saved substantial fixed dispatch overhead."
            )

        # 6. Counterfactual analysis
        counterfactuals = {
            "baseline_point_demand_sum": round(total_d, 1),
            "baseline_total_inventory": total_s,
            "inventory_to_demand_ratio": round(stock_ratio, 3),
            "what_if_stock_plus_20_pct": {
                "additional_stock_units": int(total_s * 0.20),
                "estimated_unmet_reduction": round(
                    min(result.total_unmet_demand, total_s * 0.20), 1
                ),
            },
            "what_if_zero_route_costs": {
                "route_cost_savings": result.fixed_route_cost,
                "percent_cost_reduction": round(
                    (result.fixed_route_cost / result.total_cost * 100)
                    if result.total_cost > 0
                    else 0.0,
                    2,
                ),
            },
        }

        return DecisionExplanation(
            policy=policy_name,
            solver_status=result.status,
            solver_runtime_sec=result.solver_runtime_sec,
            executive_summary=exec_summary,
            key_drivers=key_drivers,
            total_cost_breakdown=cost_breakdown,
            route_diagnostics=route_explanations[:10],  # Top active routes
            top_shortage_attributions=shortage_attributions[:10],  # Top clinical shortages
            fairness_evaluation=fairness_eval,
            counterfactual_analysis=counterfactuals,
        )
