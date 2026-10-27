"""AEGIS Streamlit decision workspace and visualization UI."""

from aegis.ui.components import (
    render_decision_explanation_card,
    render_header,
    render_hospital_risk_ranking,
    render_provenance_sidebar,
)
from aegis.ui.plots import (
    plot_cost_waterfall,
    plot_facility_map,
    plot_fill_rate_distribution,
    plot_forecast_timeseries,
    plot_policy_benchmark_comparison,
    plot_shap_summary,
    plot_shap_waterfall,
)
from aegis.ui.theme import apply_custom_css

__all__ = [
    "apply_custom_css",
    "plot_cost_waterfall",
    "plot_facility_map",
    "plot_fill_rate_distribution",
    "plot_forecast_timeseries",
    "plot_policy_benchmark_comparison",
    "plot_shap_summary",
    "plot_shap_waterfall",
    "render_decision_explanation_card",
    "render_header",
    "render_hospital_risk_ranking",
    "render_provenance_sidebar",
]
