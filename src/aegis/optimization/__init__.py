"""Optimization engine for multi-echelon medical consumable supply allocation."""

from aegis.optimization.baselines import GreedyAllocationPolicy, ProportionalAllocationPolicy
from aegis.optimization.engine import optimize
from aegis.optimization.fairness import FairnessRelaxationAnalyzer
from aegis.optimization.milp_deterministic import DeterministicMILPSolver
from aegis.optimization.milp_stochastic import StochasticMILPSolver
from aegis.optimization.schema import (
    FacilityShortage,
    FairnessDiagnostics,
    OptimizationResult,
    RouteDispatch,
    ShipmentAllocation,
)

__all__ = [
    "DeterministicMILPSolver",
    "FairnessDiagnostics",
    "FairnessRelaxationAnalyzer",
    "FacilityShortage",
    "GreedyAllocationPolicy",
    "OptimizationResult",
    "ProportionalAllocationPolicy",
    "RouteDispatch",
    "ShipmentAllocation",
    "StochasticMILPSolver",
    "optimize",
]
