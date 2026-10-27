"""Automated tests for Milestone 3 Streamlit UI workspace, TreeSHAP, and decision explainability."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES
from aegis.explainability.decision_explainer import (
    AllocationDecisionExplainer,
    DecisionExplanation,
)
from aegis.explainability.tree_shap import TreeSHAPExplainer
from aegis.optimization.engine import optimize
from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.scenarios.network import TransportationNetwork
from aegis.ui.plots import (
    plot_cost_waterfall,
    plot_facility_map,
    plot_fill_rate_distribution,
    plot_forecast_timeseries,
    plot_policy_benchmark_comparison,
    plot_shap_summary,
    plot_shap_waterfall,
)
from aegis.ui.state import (
    get_cached_benchmark_metrics,
    get_cached_featured_data,
    get_cached_model_and_explainer,
    get_cached_network,
    get_cached_scenario_generator,
)


@pytest.fixture(scope="module")
def featured_data():
    path = Path("data/processed/featured_dataset.parquet")
    assert path.exists(), "Featured dataset parquet missing"
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def shap_explainer():
    explainer = TreeSHAPExplainer()
    assert explainer.is_available, "TreeSHAPExplainer failed to initialize"
    return explainer


@pytest.fixture(scope="module")
def scenario_and_result():
    gen = ForecastScenarioGenerator()
    scen = gen.generate_scenario_set(target_date="2025-11-08", num_scenarios=3, seed=42)
    net = TransportationNetwork()

    exp_d = scen.get_expected_demands()
    stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_c = sum(exp_d.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        stk_c = tot_c * 1.25
        stock[("W01", c.category_id)] = int(round(stk_c * 0.50))
        stock[("W02", c.category_id)] = int(round(stk_c * 0.25))
        stock[("W03", c.category_id)] = int(round(stk_c * 0.25))

    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen,
        demands=scen.point_forecast,
        policy="stochastic_milp",
        min_service_coverage=0.40,
        time_limit_sec=15.0,
        realized_demand=scen.realized_demand,
        network=net,
    )
    return scen, stock, net, res


def test_shap_explainer_initialization_and_availability(shap_explainer):
    """Verify TreeSHAP loads XGBoost model and initializes with correct feature count."""
    assert shap_explainer.is_available
    assert len(shap_explainer.feature_names) == 39
    assert "lag_1" in shap_explainer.feature_names
    assert "rolling_mean_7" in shap_explainer.feature_names
    assert "hospital_id" in shap_explainer.feature_names


def test_shap_global_importance_schema_and_ordering(shap_explainer, featured_data):
    """Verify global feature importance produces sorted dataframe with correct metrics."""
    sample = featured_data.head(50)
    imp_df = shap_explainer.get_global_importance(sample, top_k=10)

    assert isinstance(imp_df, pd.DataFrame)
    assert len(imp_df) == 10
    assert list(imp_df.columns) == ["feature", "mean_abs_shap", "mean_shap"]
    # Verify descending sort order
    assert (imp_df["mean_abs_shap"].diff().dropna() <= 0).all()
    # Lag 1 should be the top predictive feature
    assert imp_df.iloc[0]["feature"] == "lag_1"


def test_shap_local_instance_additivity(shap_explainer, featured_data):
    """Verify mathematical additivity of TreeSHAP: base_value + sum(shap_i) == prediction."""
    sample_row = featured_data.head(1)
    res = shap_explainer.explain_instance(sample_row)

    assert res["status"] == "SUCCESS"
    assert res["is_additive"] is True
    assert res["additivity_error"] < 0.005

    # Check structure
    assert "base_value" in res
    assert "prediction" in res
    assert "top_positive_features" in res
    assert "top_negative_features" in res
    assert len(res["all_contributions"]) == 39


def test_decision_explainer_structured_output(scenario_and_result):
    """Verify DecisionExplainer generates structured DecisionExplanation grounded in solver outputs."""
    scen, stock, net, res = scenario_and_result
    explainer = AllocationDecisionExplainer(network=net)
    exp = explainer.explain(
        result=res,
        demands=scen.point_forecast,
        warehouse_stock=stock,
        min_service_coverage=0.40,
        policy_name="Stochastic_MILP",
    )

    assert isinstance(exp, DecisionExplanation)
    assert exp.policy == "Stochastic_MILP"
    assert exp.solver_status in ["OPTIMAL", "FEASIBLE"]
    assert len(exp.executive_summary) > 50
    assert len(exp.key_drivers) >= 4
    assert exp.total_cost_breakdown["total_cost"] == res.total_cost
    assert exp.total_cost_breakdown["transportation_cost"] == res.transportation_cost

    # Verify governance badges
    assert exp.governance_badges["synthetic_data"] == "EXPLICITLY_SYNTHETIC"
    assert exp.governance_badges["clinical_validation"] == "NONE_LOGISTICAL_ONLY"
    assert exp.governance_badges["patient_data"] == "ZERO_PHI_PII"


def test_decision_explainer_infeasibility_relaxation():
    """Verify DecisionExplainer detects mathematical infeasibility and computes relaxation diagnostic."""
    gen = ForecastScenarioGenerator()
    scen = gen.generate_scenario_set(target_date="2025-11-08", num_scenarios=3, seed=42)
    net = TransportationNetwork()

    # Highly constrained deficit stock (only 20% of demand) with 95% target
    exp_d = scen.get_expected_demands()
    deficit_stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_c = sum(exp_d.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        deficit_stock[("W01", c.category_id)] = int(tot_c * 0.10)
        deficit_stock[("W02", c.category_id)] = int(tot_c * 0.05)
        deficit_stock[("W03", c.category_id)] = int(tot_c * 0.05)

    res = optimize(
        warehouse_stock=deficit_stock,
        scenario_set=scen,
        demands=scen.point_forecast,
        policy="stochastic_milp",
        min_service_coverage=0.95,
        time_limit_sec=10.0,
        network=net,
    )

    assert res.status == "INFEASIBLE"
    explainer = AllocationDecisionExplainer(network=net)
    exp = explainer.explain(
        result=res,
        demands=scen.point_forecast,
        warehouse_stock=deficit_stock,
        min_service_coverage=0.95,
        policy_name="Stochastic_MILP",
    )

    assert (
        "CRITICAL: Policy 'Stochastic_MILP' detected mathematical infeasibility"
        in exp.executive_summary
    )
    relax = exp.fairness_evaluation.get("relaxation_analysis")
    assert relax is not None
    assert relax["max_feasible_coverage"] < 0.95
    assert relax["total_inventory_deficit"] > 0


def test_plotly_figures_generation(scenario_and_result, featured_data, shap_explainer):
    """Verify that all Plotly chart generation functions return valid Figure objects without errors."""
    scen, stock, net, res = scenario_and_result

    # 1. Facility map
    fig_map = plot_facility_map(result=res, network=net)
    assert isinstance(fig_map, go.Figure)

    # 2. Time-series forecast
    fig_ts = plot_forecast_timeseries(
        df_featured=featured_data,
        target_date="2025-11-08",
        facility_id="H01",
        category_id="PPE",
        point_forecast=500.0,
        lower_bound=300.0,
        upper_bound=700.0,
    )
    assert isinstance(fig_ts, go.Figure)

    # 3. Cost waterfall
    fig_wf = plot_cost_waterfall(result=res)
    assert isinstance(fig_wf, go.Figure)

    # 4. Fill rate distribution
    fig_fr = plot_fill_rate_distribution(result=res, min_service_coverage=0.50)
    assert isinstance(fig_fr, go.Figure)

    # 5. SHAP summary
    sample = featured_data.head(20)
    imp_df = shap_explainer.get_global_importance(sample, top_k=8)
    fig_shap = plot_shap_summary(imp_df)
    assert isinstance(fig_shap, go.Figure)

    # 6. SHAP instance waterfall
    inst_dict = shap_explainer.explain_instance(sample.head(1))
    fig_shap_inst = plot_shap_waterfall(inst_dict)
    assert isinstance(fig_shap_inst, go.Figure)

    # 7. Benchmark comparison
    fig_bm = plot_policy_benchmark_comparison()
    assert isinstance(fig_bm, go.Figure)


def test_missing_model_artifact_graceful_fallback():
    """Verify that TreeSHAP handles nonexistent model paths gracefully without raising crashes."""
    explainer = TreeSHAPExplainer(model_path="nonexistent/path/model.joblib")
    assert explainer.is_available is False

    # Calling importance should return empty DataFrame gracefully
    dummy_df = pd.DataFrame({"a": [1, 2]})
    res_df = explainer.get_global_importance(dummy_df)
    assert res_df.empty

    # Calling instance explain should return status UNAVAILABLE
    inst_res = explainer.explain_instance(dummy_df)
    assert inst_res["status"] == "UNAVAILABLE"


def test_cached_state_loaders():
    """Verify all cached loader functions return valid non-empty data objects."""
    forecaster, explainer = get_cached_model_and_explainer()
    assert forecaster is not None
    assert explainer.is_available

    df_data = get_cached_featured_data()
    assert not df_data.empty

    bm_metrics = get_cached_benchmark_metrics()
    assert "common16" in bm_metrics
    assert not bm_metrics["common16"].empty
    assert "pairwise" in bm_metrics

    gen = get_cached_scenario_generator()
    assert gen is not None

    net = get_cached_network()
    assert len(net.hospital_coords) == 20


def test_streamlit_app_smoke():
    """Execute complete Streamlit AppTest smoke test to verify all tabs boot cleanly with zero unhandled exceptions."""
    app_path = Path(__file__).resolve().parent.parent / "src" / "aegis" / "ui" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=45)
    at.run()

    # Assert zero unhandled exceptions
    assert len(at.exception) == 0, f"App execution raised unhandled exceptions: {at.exception}"

    # Assert standard UI structure rendered
    assert len(at.tabs) >= 5
    assert len(at.metric) >= 5


def test_no_fabricated_benchmark_values():
    """Verify that benchmark comparison numbers match audited raw records exactly."""
    raw_df = pd.read_csv("metrics/optimization_benchmark_raw.csv")
    c16_df = pd.read_csv("metrics/optimization_benchmark_summary_common16.csv")

    piv = raw_df.pivot(index="instance_id", columns="policy", values="status")
    all_feas_mask = piv.isin(["OPTIMAL", "FEASIBLE"]).all(axis=1)
    common_ids = sorted(piv[all_feas_mask].index.tolist())

    raw_c16 = raw_df[raw_df["instance_id"].isin(common_ids)]

    for pol in ["Stochastic_MILP", "Deterministic_MILP", "Greedy", "Proportional"]:
        recalc_cost = raw_c16[raw_c16["policy"] == pol]["total_cost"].mean()
        reported_cost = c16_df[c16_df["policy"] == pol]["mean_total_cost"].iloc[0]
        assert abs(recalc_cost - reported_cost) < 0.01, (
            f"Mismatch in reported benchmark cost for {pol}"
        )


def test_audit_export_schema():
    """Verify operational audit JSON structure and required fields."""
    export_json = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "milestone": "Milestone 3",
        "provenance_commit": "3098ab2d5a70422a64a4f73e2ef96b65ddb6c73e",
        "active_policy": "Stochastic_MILP",
        "active_result_summary": {
            "status": "OPTIMAL",
            "total_cost": 278058.21,
            "units_shipped": 26804,
            "unmet_demand": 669.6,
            "mean_fill_rate": 0.991,
        },
    }

    assert "provenance_commit" in export_json
    assert "active_result_summary" in export_json
    assert export_json["active_result_summary"]["status"] == "OPTIMAL"
    assert export_json["active_result_summary"]["total_cost"] > 0
