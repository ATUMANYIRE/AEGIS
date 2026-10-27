"""AEGIS GenAI Decision Explanation Layer."""

from aegis.genai.grounding import GroundingValidator
from aegis.genai.schema import (
    BindingConstraintContext,
    DecisionContextRecord,
    FairnessOutcomeContext,
    ForecastUncertaintyContext,
    GenAIDecisionExplanation,
    GroundingAudit,
    OptimizationResultContext,
    ProvenanceContext,
    ScenarioDifferenceContext,
    SHAPContributionContext,
)
from aegis.genai.service import DecisionExplanationService, build_context_record

__all__ = [
    "BindingConstraintContext",
    "DecisionContextRecord",
    "DecisionExplanationService",
    "FairnessOutcomeContext",
    "ForecastUncertaintyContext",
    "GenAIDecisionExplanation",
    "GroundingAudit",
    "GroundingValidator",
    "OptimizationResultContext",
    "ProvenanceContext",
    "ScenarioDifferenceContext",
    "SHAPContributionContext",
    "build_context_record",
]
