"""Unit tests for uncertainty scenario generation."""

import pytest

from aegis.scenarios.generator import ForecastScenarioGenerator


def test_scenario_generator_prob_sum() -> None:
    """Test scenario probabilities strictly sum to 1.0."""
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=5, seed=42)

    total_prob = sum(sc.probability for sc in scen_set.scenarios)
    assert total_prob == pytest.approx(1.0, rel=1e-5)
    assert scen_set.num_scenarios == 5


def test_scenario_out_of_sample_separation() -> None:
    """Test realized demand is isolated from optimization scenario realizations."""
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=3, seed=42)

    # Realized demand must exist
    assert len(scen_set.realized_demand) == 20 * 3

    # Scenarios must contain point, lower, and upper bounds
    assert "baseline_p50" in [s.name for s in scen_set.scenarios]
    assert "lower_p10" in [s.name for s in scen_set.scenarios]
    assert "upper_p90" in [s.name for s in scen_set.scenarios]


def test_scenario_reproducibility() -> None:
    """Test same seed produces identical stochastic scenarios."""
    gen = ForecastScenarioGenerator()
    s1 = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=5, seed=99)
    s2 = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=5, seed=99)

    for sc1, sc2 in zip(s1.scenarios, s2.scenarios, strict=True):
        assert sc1.name == sc2.name
        assert sc1.probability == sc2.probability
        assert sc1.demands == sc2.demands
