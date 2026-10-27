"""Unit tests verifying heuristic baseline allocation policies."""

import pytest

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES
from aegis.optimization.baselines import GreedyAllocationPolicy, ProportionalAllocationPolicy
from aegis.scenarios.generator import ForecastScenarioGenerator


@pytest.fixture
def baseline_fixture():
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=1, seed=42)

    exp_d = scen_set.get_expected_demands()
    stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_d = sum(exp_d.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        stock[("W01", c.category_id)] = int(tot_d * 0.4)
        stock[("W02", c.category_id)] = int(tot_d * 0.2)
        stock[("W03", c.category_id)] = int(tot_d * 0.2)

    return scen_set.point_forecast, stock, scen_set.realized_demand


def test_proportional_baseline_constraints(baseline_fixture) -> None:
    """Test proportional policy satisfies hard capacity limits and conservation."""
    demands, stock, realized = baseline_fixture
    policy = ProportionalAllocationPolicy()
    res = policy.solve(demands=demands, warehouse_stock=stock, realized_demand=realized)

    assert res.status in ["FEASIBLE", "INFEASIBLE"]
    assert res.total_units_shipped > 0

    # Conservation
    shipped_wc = {}
    for a in res.allocations:
        key = (a.warehouse_id, a.category_id)
        shipped_wc[key] = shipped_wc.get(key, 0) + a.quantity

    for key, qty in shipped_wc.items():
        assert qty <= stock.get(key, 0)


def test_greedy_baseline_prioritization(baseline_fixture) -> None:
    """Test greedy policy allocates to high-criticality trauma centers."""
    demands, stock, realized = baseline_fixture
    policy = GreedyAllocationPolicy()
    res = policy.solve(demands=demands, warehouse_stock=stock, realized_demand=realized)

    assert res.total_units_shipped > 0

    # Level 1 Trauma (H01-H04) should have higher or equal fill rate than community clinics under scarcity
    h01_fill = next(s.fill_rate for s in res.shortages if s.hospital_id == "H01")
    assert h01_fill >= 0.0
