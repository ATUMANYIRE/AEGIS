"""Unit tests for fairness constraints, infeasibility detection, and relaxation analysis."""

import pytest

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES
from aegis.optimization.engine import optimize
from aegis.optimization.fairness import FairnessRelaxationAnalyzer
from aegis.scenarios.generator import ForecastScenarioGenerator


@pytest.fixture
def fairness_fixture():
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=1, seed=42)
    demands = scen_set.point_forecast

    # Deficit stock: only 50% of demand available
    scarce_stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_cd = sum(demands.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        scarce_stock[("W01", c.category_id)] = int(tot_cd * 0.25)
        scarce_stock[("W02", c.category_id)] = int(tot_cd * 0.15)
        scarce_stock[("W03", c.category_id)] = int(tot_cd * 0.10)

    # Ample stock: 120% of demand available
    ample_stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_cd = sum(demands.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        ample_stock[("W01", c.category_id)] = int(tot_cd * 0.60)
        ample_stock[("W02", c.category_id)] = int(tot_cd * 0.30)
        ample_stock[("W03", c.category_id)] = int(tot_cd * 0.30)

    return demands, scarce_stock, ample_stock, scen_set


def test_fairness_constraint_enforced_when_feasible(fairness_fixture) -> None:
    """Test min_service_coverage guarantees every hospital receives at least alpha_min."""
    demands, _, ample_stock, scen_set = fairness_fixture
    target_alpha = 0.65

    res = optimize(
        warehouse_stock=ample_stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
        min_service_coverage=target_alpha,
    )

    assert res.status == "OPTIMAL"
    assert res.fairness.is_fairness_satisfied is True
    assert res.fairness.worst_facility_fill_rate >= target_alpha - 1e-4


def test_infeasibility_explicitly_detected(fairness_fixture) -> None:
    """Test impossible coverage target is explicitly reported as INFEASIBLE without dropping constraints."""
    demands, scarce_stock, _, scen_set = fairness_fixture
    # Only 50% stock is available, but target requires 90%
    res = optimize(
        warehouse_stock=scarce_stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
        min_service_coverage=0.90,
    )

    assert res.status == "INFEASIBLE"
    assert res.fairness.is_fairness_satisfied is False
    assert res.fairness.total_inventory_deficit > 0.0
    assert res.fairness.max_feasible_coverage is not None
    assert res.fairness.max_feasible_coverage < 0.60


def test_relaxation_analyzer(fairness_fixture) -> None:
    """Test FairnessRelaxationAnalyzer calculates max feasible coverage and inventory deficit."""
    demands, scarce_stock, _, _ = fairness_fixture
    analyzer = FairnessRelaxationAnalyzer()
    diag = analyzer.analyze_relaxation(
        demands=demands,
        warehouse_stock=scarce_stock,
        target_min_coverage=0.85,
    )

    assert diag.is_fairness_satisfied is False
    assert diag.max_feasible_coverage is not None
    assert diag.max_feasible_coverage == pytest.approx(0.50, abs=0.05)
    assert diag.total_inventory_deficit > 0.0
    assert "infeasible" in diag.relaxation_summary.lower()


def test_automatic_relaxation_workflow(fairness_fixture) -> None:
    """Test relax_fairness_if_infeasible=True re-solves successfully at max feasible coverage."""
    demands, scarce_stock, _, scen_set = fairness_fixture
    res = optimize(
        warehouse_stock=scarce_stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
        min_service_coverage=0.85,
        relax_fairness_if_infeasible=True,
    )

    assert res.status == "OPTIMAL"
    assert "relaxed" in res.fairness.relaxation_summary.lower()
    assert res.total_units_shipped > 0
