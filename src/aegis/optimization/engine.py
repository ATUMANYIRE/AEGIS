"""Unified optimization engine interface for AEGIS multi-echelon supply allocation."""

from typing import Literal

from aegis.optimization.baselines import GreedyAllocationPolicy, ProportionalAllocationPolicy
from aegis.optimization.fairness import FairnessRelaxationAnalyzer
from aegis.optimization.milp_deterministic import DeterministicMILPSolver
from aegis.optimization.milp_stochastic import StochasticMILPSolver
from aegis.optimization.schema import OptimizationResult
from aegis.scenarios.generator import ScenarioSet
from aegis.scenarios.network import TransportationNetwork


def optimize(
    warehouse_stock: dict[tuple[str, str], int],
    scenario_set: ScenarioSet | None = None,
    demands: dict[tuple[str, str], float] | None = None,
    policy: Literal[
        "stochastic_milp", "deterministic_milp", "proportional", "greedy"
    ] = "stochastic_milp",
    min_service_coverage: float = 0.0,
    time_limit_sec: float = 30.0,
    mip_rel_gap: float = 0.01,
    relax_fairness_if_infeasible: bool = False,
    realized_demand: dict[tuple[str, str], float] | None = None,
    network: TransportationNetwork | None = None,
) -> OptimizationResult:
    """Solve multi-echelon supply allocation under selected policy and constraints.

    Parameters
    ----------
    warehouse_stock : dict[tuple[str, str], int]
        Available on-hand inventory per (warehouse_id, category_id).
    scenario_set : ScenarioSet, optional
        Set of calibrated demand scenarios (required for stochastic MILP).
    demands : dict[tuple[str, str], float], optional
        Point demand forecast (defaults to scenario_set.point_forecast if omitted).
    policy : str
        Allocation policy: 'stochastic_milp', 'deterministic_milp', 'proportional', or 'greedy'.
    min_service_coverage : float
        Configurable minimum service coverage target per hospital (0.0 to 1.0).
    time_limit_sec : float
        MIP solver execution cutoff in seconds.
    mip_rel_gap : float
        Relative optimality tolerance gap (default 0.01 = 1%).
    relax_fairness_if_infeasible : bool
        If True and problem is infeasible under min_service_coverage, re-solve at max feasible coverage.
    realized_demand : dict[tuple[str, str], float], optional
        Held-out ground truth demand for out-of-sample evaluation.
    network : TransportationNetwork, optional
        Custom network instance (uses default if omitted).

    Returns
    -------
    OptimizationResult
        Complete mathematical optimization result and diagnostics.
    """
    net = network or TransportationNetwork()

    # Determine point demand
    if demands is None:
        if scenario_set is not None:
            demands = scenario_set.point_forecast
        else:
            raise ValueError("Either demands or scenario_set must be provided.")

    # 1. Dispatch solver according to selected policy
    if policy == "stochastic_milp":
        if scenario_set is None:
            raise ValueError("Stochastic MILP requires a ScenarioSet.")
        solver_stoch = StochasticMILPSolver(network=net)
        result = solver_stoch.solve(
            scenario_set=scenario_set,
            warehouse_stock=warehouse_stock,
            min_service_coverage=min_service_coverage,
            time_limit_sec=time_limit_sec,
            mip_rel_gap=mip_rel_gap,
            realized_demand=realized_demand,
        )

    elif policy == "deterministic_milp":
        solver_det = DeterministicMILPSolver(network=net)
        result = solver_det.solve(
            demands=demands,
            warehouse_stock=warehouse_stock,
            min_service_coverage=min_service_coverage,
            time_limit_sec=time_limit_sec,
            mip_rel_gap=mip_rel_gap,
            realized_demand=realized_demand,
        )

    elif policy == "proportional":
        policy_prop = ProportionalAllocationPolicy(network=net)
        result = policy_prop.solve(
            demands=demands,
            warehouse_stock=warehouse_stock,
            min_service_coverage=min_service_coverage,
            realized_demand=realized_demand,
        )

    elif policy == "greedy":
        policy_greedy = GreedyAllocationPolicy(network=net)
        result = policy_greedy.solve(
            demands=demands,
            warehouse_stock=warehouse_stock,
            min_service_coverage=min_service_coverage,
            realized_demand=realized_demand,
        )

    else:
        raise ValueError(f"Unknown optimization policy '{policy}'")

    # 2. Infeasibility analysis and optional relaxation
    if result.status == "INFEASIBLE":
        analyzer = FairnessRelaxationAnalyzer(network=net)
        diag = analyzer.analyze_relaxation(
            demands=demands,
            warehouse_stock=warehouse_stock,
            target_min_coverage=min_service_coverage,
        )
        result.fairness.max_feasible_coverage = diag.max_feasible_coverage
        result.fairness.bottleneck_warehouses = diag.bottleneck_warehouses
        result.fairness.total_inventory_deficit = diag.total_inventory_deficit
        result.fairness.relaxation_summary = diag.relaxation_summary

        if relax_fairness_if_infeasible and diag.max_feasible_coverage is not None:
            relaxed_alpha = max(0.0, diag.max_feasible_coverage - 0.01)
            # Re-solve at relaxed feasible coverage
            relaxed_result = optimize(
                warehouse_stock=warehouse_stock,
                scenario_set=scenario_set,
                demands=demands,
                policy=policy,
                min_service_coverage=relaxed_alpha,
                time_limit_sec=time_limit_sec,
                mip_rel_gap=mip_rel_gap,
                relax_fairness_if_infeasible=False,
                realized_demand=realized_demand,
                network=net,
            )
            relaxed_result.fairness.relaxation_summary = (
                f"Automatically relaxed target from {min_service_coverage:.1%} to {relaxed_alpha:.1%}. "
                + (diag.relaxation_summary or "")
            )
            return relaxed_result

    return result
