"""Scientific benchmark evaluating 4 supply allocation policies across 30 experiment instances."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES
from aegis.optimization.engine import optimize
from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.scenarios.network import NetworkParameters, TransportationNetwork
from aegis.utils.logging import setup_logger

logger = setup_logger("aegis.opt_benchmark")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AEGIS Optimization Scientific Benchmark")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="metrics",
        help="Directory to persist benchmark results and paired statistical tables",
    )
    parser.add_argument(
        "--num-instances",
        type=int,
        default=30,
        help="Number of experiment scenario instances (default 30)",
    )
    return parser.parse_args()


def calculate_paired_stats(diffs: np.ndarray, confidence: float = 0.95) -> dict[str, float]:
    """Calculate mean difference, standard error, t-interval, and bootstrap CI."""
    n = len(diffs)
    if n == 0:
        return {
            "mean_diff": 0.0,
            "std_err": 0.0,
            "ci_lower_t": 0.0,
            "ci_upper_t": 0.0,
            "ci_lower_boot": 0.0,
            "ci_upper_boot": 0.0,
            "p_value": 1.0,
        }

    mean_d = float(np.mean(diffs))
    if n == 1:
        return {
            "mean_diff": round(mean_d, 2),
            "std_err": 0.0,
            "ci_lower_t": round(mean_d, 2),
            "ci_upper_t": round(mean_d, 2),
            "ci_lower_boot": round(mean_d, 2),
            "ci_upper_boot": round(mean_d, 2),
            "p_value": 1.0,
        }

    std_err = float(stats.sem(diffs))
    # Student's t critical value
    t_crit = float(stats.t.ppf((1.0 + confidence) / 2.0, df=n - 1))
    ci_l_t = mean_d - t_crit * std_err
    ci_u_t = mean_d + t_crit * std_err

    # Percentile bootstrap CI (B=2000)
    rng = np.random.default_rng(42)
    boot_means = [float(np.mean(rng.choice(diffs, size=n, replace=True))) for _ in range(2000)]
    alpha_half = (1.0 - confidence) / 2.0
    ci_l_b = float(np.percentile(boot_means, 100 * alpha_half))
    ci_u_b = float(np.percentile(boot_means, 100 * (1.0 - alpha_half)))

    # Two-sided t-test
    _, p_val = stats.ttest_1samp(diffs, popmean=0.0)

    return {
        "mean_diff": round(mean_d, 2),
        "std_err": round(std_err, 2),
        "ci_lower_t": round(ci_l_t, 2),
        "ci_upper_t": round(ci_u_t, 2),
        "ci_lower_boot": round(ci_l_b, 2),
        "ci_upper_boot": round(ci_u_b, 2),
        "p_value": round(float(p_val), 5),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing Forecast Scenario Generator...")
    scen_gen = ForecastScenarioGenerator()

    # Define 30 experimental scenario instances spanning 6 operational regimes
    regimes = [
        ("Normal_Demand", 1.0, 1.25, 1.0, 0.50, False),  # 5 instances
        ("Demand_Surge", 1.55, 1.25, 1.0, 0.50, False),  # 5 instances
        ("Stock_Scarcity", 1.0, 0.65, 1.0, 0.40, False),  # 5 instances
        ("Transport_Bottleneck", 1.0, 1.25, 0.45, 0.40, False),  # 5 instances
        ("Asymmetric_Trauma_Surge", 1.30, 1.10, 1.0, 0.50, False),  # 5 instances
        ("Infeasible_Target_Stress", 1.0, 0.70, 1.0, 0.95, False),  # 5 instances
    ]

    instances = []
    # Test dates available in held-out partition: 2025-11-07 to 2025-12-31
    available_dates = (
        pd.date_range("2025-11-08", periods=5, freq="3D").strftime("%Y-%m-%d").tolist()
    )

    instance_id = 1
    for r_name, surge_mult, stock_ratio, capacity_scale, alpha_target, _relax in regimes:
        for _d_idx, t_date in enumerate(available_dates):
            instances.append(
                {
                    "instance_id": instance_id,
                    "regime": r_name,
                    "target_date": t_date,
                    "surge_multiplier": surge_mult,
                    "stock_ratio": stock_ratio,
                    "capacity_scale": capacity_scale,
                    "min_coverage": alpha_target,
                    "seed": 100 + instance_id,
                }
            )
            instance_id += 1

    logger.info("Prepared %d experimental instances across 6 regimes.", len(instances))

    policies = ["Proportional", "Greedy", "Deterministic_MILP", "Stochastic_MILP"]
    results_records: list[dict[str, Any]] = []

    for inst in instances:
        i_id = inst["instance_id"]
        r_name = inst["regime"]
        t_date = inst["target_date"]
        logger.info("[Instance %02d/30] Regime: %s, Date: %s", i_id, r_name, t_date)

        # 1. Generate scenario set from XGBoost forecast
        scen_set = scen_gen.generate_scenario_set(
            target_date=t_date,
            num_scenarios=5,
            seed=inst["seed"],
            surge_multiplier=inst["surge_multiplier"],
        )

        # 2. Establish network parameters for this instance
        params = NetworkParameters()
        if inst["capacity_scale"] < 1.0:
            # Throttle dispatch capacities
            params = NetworkParameters(
                warehouse_dispatch_capacities={
                    w: int(params.warehouse_dispatch_capacities[w] * inst["capacity_scale"])
                    for w in params.warehouse_dispatch_capacities
                },
                max_route_capacity_units=int(
                    params.max_route_capacity_units * inst["capacity_scale"]
                ),
            )
        net = TransportationNetwork(params=params)

        # 3. Establish warehouse stock levels
        # Stock proportional to total expected demand multiplied by stock_ratio
        exp_demands = scen_set.get_expected_demands()
        warehouse_stock: dict[tuple[str, str], int] = {}
        for c in PRODUCT_CATEGORIES:
            tot_cat_exp = sum(
                exp_demands.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS
            )
            target_total_stk = tot_cat_exp * inst["stock_ratio"]
            # Split stock across 3 warehouses: 50% central, 25% north, 25% south
            warehouse_stock[("W01", c.category_id)] = int(round(target_total_stk * 0.50))
            warehouse_stock[("W02", c.category_id)] = int(round(target_total_stk * 0.25))
            warehouse_stock[("W03", c.category_id)] = int(round(target_total_stk * 0.25))

        # 4. Evaluate each policy on identical instance
        for pol in policies:
            pol_key = pol.lower()
            res = optimize(
                warehouse_stock=warehouse_stock,
                scenario_set=scen_set,
                demands=scen_set.point_forecast,
                policy=pol_key,  # type: ignore[arg-type]
                min_service_coverage=inst["min_coverage"],
                time_limit_sec=20.0,
                realized_demand=scen_set.realized_demand,
                network=net,
            )

            results_records.append(
                {
                    "instance_id": i_id,
                    "regime": r_name,
                    "target_date": t_date,
                    "policy": pol,
                    "status": res.status,
                    "total_cost": res.total_cost if res.status != "INFEASIBLE" else np.nan,
                    "transport_cost": res.transportation_cost,
                    "route_cost": res.fixed_route_cost,
                    "vehicle_cost": res.vehicle_cost,
                    "shortage_penalty": res.shortage_penalty
                    if res.status != "INFEASIBLE"
                    else np.nan,
                    "units_shipped": res.total_units_shipped,
                    "unmet_demand": res.total_unmet_demand,
                    "mean_fill_rate": res.fairness.mean_facility_fill_rate,
                    "worst_fill_rate": res.fairness.worst_facility_fill_rate,
                    "coverage_disparity": res.fairness.coverage_disparity,
                    "runtime_sec": res.solver_runtime_sec,
                    "is_fairness_satisfied": res.fairness.is_fairness_satisfied,
                }
            )

    df_res = pd.DataFrame(results_records)

    # 5. Compute Paired Policy Differences
    # Compare each baseline policy against Stochastic_MILP on feasible instances
    paired_rows = []
    # Pivot for paired comparison
    feasible_insts = df_res[df_res["policy"] == "Stochastic_MILP"]
    feasible_ids = feasible_insts[feasible_insts["status"].isin(["OPTIMAL", "FEASIBLE"])][
        "instance_id"
    ].unique()

    df_feas = df_res[df_res["instance_id"].isin(feasible_ids)].copy()

    metrics_to_compare = [
        ("total_cost", "Total Cost ($)", "lower_is_better"),
        ("unmet_demand", "Unmet Demand (units)", "lower_is_better"),
        ("transport_cost", "Transport Cost ($)", "lower_is_better"),
        ("mean_fill_rate", "Mean Fill Rate", "higher_is_better"),
        ("worst_fill_rate", "Worst Facility Fill Rate", "higher_is_better"),
        ("coverage_disparity", "Coverage Disparity", "lower_is_better"),
    ]

    for pol in ["Deterministic_MILP", "Greedy", "Proportional"]:
        for metric_col, metric_label, direction in metrics_to_compare:
            p_base = df_feas[df_feas["policy"] == pol].set_index("instance_id")[metric_col]
            p_stoch = df_feas[df_feas["policy"] == "Stochastic_MILP"].set_index("instance_id")[
                metric_col
            ]

            valid_idx = p_base.dropna().index.intersection(p_stoch.dropna().index)
            # Difference: Baseline - Stochastic
            diffs = (p_base.loc[valid_idx] - p_stoch.loc[valid_idx]).values

            stats_dict = calculate_paired_stats(diffs)
            stats_dict["baseline_policy"] = pol
            stats_dict["benchmark_policy"] = "Stochastic_MILP"
            stats_dict["metric"] = metric_label
            stats_dict["metric_col"] = metric_col
            stats_dict["direction"] = direction
            stats_dict["n_instances"] = len(diffs)
            paired_rows.append(stats_dict)

    df_paired = pd.DataFrame(paired_rows)

    # 6. Save results to disk
    raw_csv = out_dir / "optimization_benchmark_raw.csv"
    df_res.to_csv(raw_csv, index=False)
    logger.info("Saved raw benchmark instances to %s", raw_csv)

    paired_csv = out_dir / "paired_policy_differences.csv"
    df_paired.to_csv(paired_csv, index=False)
    logger.info("Saved paired policy differences and confidence intervals to %s", paired_csv)

    # Save summary table
    summary_df = (
        df_res.groupby("policy")
        .agg(
            feasibility_rate=("status", lambda s: np.mean(s.isin(["OPTIMAL", "FEASIBLE"]))),
            mean_total_cost=("total_cost", "mean"),
            mean_unmet_demand=("unmet_demand", "mean"),
            mean_fill_rate=("mean_fill_rate", "mean"),
            worst_fill_rate=("worst_fill_rate", "mean"),
            mean_disparity=("coverage_disparity", "mean"),
            mean_runtime_sec=("runtime_sec", "mean"),
        )
        .reset_index()
    )

    summary_csv = out_dir / "optimization_benchmark_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    logger.info("Saved summary table to %s", summary_csv)

    summary_json = out_dir / "optimization_benchmark_results.json"
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "num_instances": len(instances),
                "summary": summary_df.to_dict(orient="records"),
                "paired_differences": df_paired.to_dict(orient="records"),
            },
            f,
            indent=2,
        )
    logger.info("Saved benchmark JSON report to %s", summary_json)

    # Print summary table to console
    print("\n" + "=" * 105)
    print("AEGIS MILESTONE 2: OPTIMIZATION POLICY BENCHMARK SUMMARY (30 EXPERIMENTAL INSTANCES)")
    print("=" * 105)
    print(
        f"{'Policy':<20} | {'Feasible':<9} | {'Mean Total Cost':<16} | {'Unmet Demand':<13} | {'Mean Fill':<10} | {'Worst Fill':<11} | {'Disparity':<10} | {'Runtime (s)':<11}"
    )
    print("-" * 105)
    for _, row in summary_df.iterrows():
        print(
            f"{row['policy']:<20} | {row['feasibility_rate']:<9.1%} | ${row['mean_total_cost']:<15.2f} | {row['mean_unmet_demand']:<13.1f} | "
            f"{row['mean_fill_rate']:<10.2%} | {row['worst_fill_rate']:<11.2%} | {row['mean_disparity']:<10.2%} | {row['mean_runtime_sec']:<11.4f}"
        )
    print("=" * 105)

    print("\n" + "=" * 115)
    print("PAIRED POLICY DIFFERENCES VS STOCHASTIC MILP (95% CONFIDENCE INTERVALS)")
    print("=" * 115)
    print(
        f"{'Comparison':<36} | {'Metric':<24} | {'Mean Diff':<11} | {'95% t-Interval':<22} | {'95% Boot CI':<22} | {'p-value':<8}"
    )
    print("-" * 115)
    for _, r in df_paired.iterrows():
        comp = f"{r['baseline_policy']} vs Stoch"
        ci_t = f"[{r['ci_lower_t']:+.2f}, {r['ci_upper_t']:+.2f}]"
        ci_b = f"[{r['ci_lower_boot']:+.2f}, {r['ci_upper_boot']:+.2f}]"
        print(
            f"{comp:<36} | {r['metric']:<24} | {r['mean_diff']:<+11.2f} | {ci_t:<22} | {ci_b:<22} | {r['p_value']:<8.4f}"
        )
    print("=" * 115)


if __name__ == "__main__":
    main()
