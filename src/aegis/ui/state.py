"""State management and safe caching protocols for AEGIS Streamlit Workspace."""

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from aegis.explainability.tree_shap import TreeSHAPExplainer
from aegis.models.regressor import XGBoostDemandForecaster
from aegis.models.serialization import ModelSerializer
from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.scenarios.network import TransportationNetwork


@st.cache_resource
def get_cached_model_and_explainer() -> tuple[XGBoostDemandForecaster | None, TreeSHAPExplainer]:
    """Cache immutable model artifact and TreeSHAP explainer safely across app sessions."""
    model_path = Path("models/xgboost_demand.joblib")
    forecaster: XGBoostDemandForecaster | None = None
    if model_path.exists():
        try:
            loaded, _ = ModelSerializer.load(model_path)
            if isinstance(loaded, XGBoostDemandForecaster):
                forecaster = loaded
        except Exception:
            forecaster = None

    explainer = TreeSHAPExplainer(model_path=model_path, forecaster=forecaster)
    return forecaster, explainer


@st.cache_data
def get_cached_featured_data() -> pd.DataFrame:
    """Load featured time-series dataset with safe in-memory caching."""
    data_path = Path("data/processed/featured_dataset.parquet")
    if data_path.exists():
        return pd.read_parquet(data_path)
    return pd.DataFrame()


@st.cache_data
def get_cached_benchmark_metrics() -> dict[str, pd.DataFrame]:
    """Load verified benchmark metrics and paired statistics."""
    res: dict[str, pd.DataFrame] = {}
    c16_path = Path("metrics/optimization_benchmark_summary_common16.csv")
    pairwise_path = Path("metrics/paired_policy_differences.csv")
    raw_path = Path("metrics/optimization_benchmark_raw.csv")

    if c16_path.exists():
        res["common16"] = pd.read_csv(c16_path)
    if pairwise_path.exists():
        res["pairwise"] = pd.read_csv(pairwise_path)
    if raw_path.exists():
        res["raw"] = pd.read_csv(raw_path)

    return res


@st.cache_resource
def get_cached_scenario_generator() -> ForecastScenarioGenerator:
    """Cache forecast scenario generator linked to serialized XGBoost model."""
    return ForecastScenarioGenerator()


@st.cache_resource
def get_cached_network() -> TransportationNetwork:
    """Cache transportation network topology."""
    return TransportationNetwork()


def init_session_state() -> None:
    """Initialize user session state with default operational parameters."""
    defaults: dict[str, Any] = {
        "target_date": "2025-11-15",
        "policy": "Stochastic_MILP",
        "surge_pct": 0,
        "stock_availability_pct": 100,
        "vehicle_capacity_units": 2500,
        "transport_throttle_pct": 100,
        "min_service_coverage": 0.50,
        "active_result": None,
        "active_explanation": None,
        "active_scenario_set": None,
        "last_stress_scenario": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
