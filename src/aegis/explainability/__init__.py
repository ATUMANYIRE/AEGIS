"""Explainability engines for AEGIS forecasting and allocation decision intelligence."""

from aegis.explainability.decision_explainer import (
    AllocationDecisionExplainer,
    DecisionExplanation,
    RouteExplanation,
    ShortageAttribution,
)
from aegis.explainability.tree_shap import TreeSHAPExplainer

__all__ = [
    "AllocationDecisionExplainer",
    "DecisionExplanation",
    "RouteExplanation",
    "ShortageAttribution",
    "TreeSHAPExplainer",
]
