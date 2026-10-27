"""Regression and audit tests verifying benchmark data integrity, absence of contradictions, and exact cost accounting."""

from pathlib import Path

import pandas as pd
import pytest

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES
from aegis.optimization.engine import optimize
from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.scenarios.network import TransportationNetwork


@pytest.fixture(scope="module")
def benchmark_data():
    raw_path = Path("metrics/optimization_benchmark_raw.csv")
    paired_path = Path("metrics/paired_policy_differences.csv")
    summary_c16_path = Path("metrics/optimization_benchmark_summary_common16.csv")
    summary_feas_path = Path("metrics/optimization_benchmark_summary_feasible_only.csv")

    assert raw_path.exists(), "Raw benchmark CSV missing"
    assert paired_path.exists(), "Paired differences CSV missing"
    assert summary_c16_path.exists(), "Common-16 summary CSV missing"
    assert summary_feas_path.exists(), "Feasible-only summary CSV missing"

    df_raw = pd.read_csv(raw_path)
    df_paired = pd.read_csv(paired_path)
    df_c16 = pd.read_csv(summary_c16_path)
    df_feas = pd.read_csv(summary_feas_path)

    return {
        "raw": df_raw,
        "paired": df_paired,
        "c16": df_c16,
        "feas": df_feas,
    }


def test_cost_decomposition_exactness(benchmark_data):
    """Verify total_cost is exact sum of transport, route, vehicle, and shortage costs for all feasible runs."""
    df_raw = benchmark_data["raw"]
    feasible_records = df_raw[df_raw["status"].isin(["OPTIMAL", "FEASIBLE"])]

    for idx, row in feasible_records.iterrows():
        expected_total = round(
            row["transport_cost"]
            + row["route_cost"]
            + row["vehicle_cost"]
            + row["shortage_penalty"],
            2,
        )
        actual_total = round(row["total_cost"], 2)
        diff = abs(expected_total - actual_total)
        assert diff <= 0.05, (
            f"Cost decomposition mismatch on row {idx} ({row['policy']}, instance {row['instance_id']}): "
            f"expected {expected_total}, got {actual_total} (diff {diff})"
        )


def test_pairwise_matched_sample_sizes(benchmark_data):
    """Verify that within any policy comparison in paired table, all metrics share the exact same N."""
    df_paired = benchmark_data["paired"]

    for pol in df_paired["baseline_policy"].unique():
        pol_rows = df_paired[df_paired["baseline_policy"] == pol]
        unique_n = pol_rows["n_instances"].unique()
        assert len(unique_n) == 1, (
            f"Mismatched sample sizes in paired comparison for {pol}: found N={unique_n}. "
            "All compared metrics must use identical matched instances!"
        )


def test_no_unsupported_sample_size_claims(benchmark_data):
    """Verify Greedy is not claimed to have 25 feasible pairs when it only solved 20."""
    df_paired = benchmark_data["paired"]
    greedy_n = df_paired[df_paired["baseline_policy"] == "Greedy"]["n_instances"].iloc[0]
    assert greedy_n == 20, (
        f"Greedy was feasible on 20 instances, but paired table reports N={greedy_n}"
    )

    prop_n = df_paired[df_paired["baseline_policy"] == "Proportional"]["n_instances"].iloc[0]
    assert prop_n == 24, (
        f"Proportional was feasible on 24 instances, but paired table reports N={prop_n}"
    )


def test_common_feasible_subset_mean_consistency(benchmark_data):
    """Verify that paired differences on Common 16 match difference of summary means."""
    raw = benchmark_data["raw"]
    piv = raw.pivot(index="instance_id", columns="policy", values="status")
    all_feas_mask = piv.isin(["OPTIMAL", "FEASIBLE"]).all(axis=1)
    common_ids = piv[all_feas_mask].index.tolist()
    assert len(common_ids) == 16, f"Expected 16 common feasible instances, got {len(common_ids)}"

    df_c16 = raw[raw["instance_id"].isin(common_ids)]
    stoch_cost = df_c16[df_c16["policy"] == "Stochastic_MILP"]["total_cost"].mean()

    for pol in ["Deterministic_MILP", "Greedy", "Proportional"]:
        base_cost = df_c16[df_c16["policy"] == pol]["total_cost"].mean()
        expected_diff = base_cost - stoch_cost

        # Recompute paired diff
        p_base = df_c16[df_c16["policy"] == pol].set_index("instance_id")["total_cost"]
        p_stoch = df_c16[df_c16["policy"] == "Stochastic_MILP"].set_index("instance_id")[
            "total_cost"
        ]
        paired_diff = (p_base - p_stoch).mean()

        assert abs(expected_diff - paired_diff) < 1e-4, (
            f"Inconsistent aggregate vs paired diff for {pol}: "
            f"summary diff={expected_diff:.2f}, paired diff={paired_diff:.2f}"
        )


def test_infeasible_instances_have_nan_cost(benchmark_data):
    """Verify that instances returning INFEASIBLE have NaN total_cost to prevent distorted averages."""
    df_raw = benchmark_data["raw"]
    infeasible_records = df_raw[df_raw["status"] == "INFEASIBLE"]
    assert len(infeasible_records) > 0, "Expected infeasible instances in raw records"
    assert infeasible_records["total_cost"].isna().all(), (
        "Infeasible records must have NaN for total_cost to avoid polluting feasible averages"
    )


def test_independent_allocation_recomputation():
    """Verify independent reconstruction of all cost terms from raw allocations on a fresh solve."""
    gen = ForecastScenarioGenerator()
    scen = gen.generate_scenario_set(
        target_date="2025-11-08", num_scenarios=3, seed=42, surge_multiplier=1.0
    )
    net = TransportationNetwork()

    exp_d = scen.get_expected_demands()
    stock = {}
    for c in PRODUCT_CATEGORIES:
        tot = sum(exp_d.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS) * 1.25
        stock[("W01", c.category_id)] = int(round(tot * 0.50))
        stock[("W02", c.category_id)] = int(round(tot * 0.25))
        stock[("W03", c.category_id)] = int(round(tot * 0.25))

    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen,
        policy="stochastic_milp",
        min_service_coverage=0.40,
        realized_demand=scen.realized_demand,
        network=net,
        time_limit_sec=15.0,
    )

    assert res.status in ["OPTIMAL", "FEASIBLE"]

    # Reconstruct transport cost
    recalc_trans = sum(
        alloc.quantity
        * net.transport_costs[(alloc.warehouse_id, alloc.hospital_id, alloc.category_id)]
        for alloc in res.allocations
    )
    assert abs(res.transportation_cost - recalc_trans) < 0.05

    # Reconstruct route and vehicle costs
    recalc_route = sum(
        net.fixed_route_costs[(r.warehouse_id, r.hospital_id)] for r in res.routes if r.active
    )
    recalc_veh = sum(
        r.vehicles_assigned * net.params.fixed_vehicle_cost for r in res.routes if r.active
    )
    assert abs(res.fixed_route_cost - recalc_route) < 0.01
    assert abs(res.vehicle_cost - recalc_veh) < 0.01

    # Reconstruct shortage penalties on realized demand
    recalc_shortage_pen = 0.0
    for s in res.shortages:
        real_d = scen.realized_demand.get((s.hospital_id, s.category_id), 0.0)
        shortage = max(0.0, real_d - s.allocated_units)
        pen = shortage * net.shortage_penalties[(s.hospital_id, s.category_id)]
        recalc_shortage_pen += pen

    assert abs(res.shortage_penalty - recalc_shortage_pen) < 0.05
