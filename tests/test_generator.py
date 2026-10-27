"""Unit tests for DeterministicSyntheticGenerator."""

import pandas as pd

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES, AegisConfig
from aegis.data.generator import DeterministicSyntheticGenerator


def test_generator_reproducibility() -> None:
    """Test identical random seed produces strictly identical datasets."""
    cfg1 = AegisConfig(seed=999, simulation_days=10)
    cfg2 = AegisConfig(seed=999, simulation_days=10)

    gen1 = DeterministicSyntheticGenerator(config=cfg1)
    gen2 = DeterministicSyntheticGenerator(config=cfg2)

    df1 = gen1.generate(scenario="baseline")
    df2 = gen2.generate(scenario="baseline")

    pd.testing.assert_frame_equal(df1, df2)


def test_generator_seed_diversity() -> None:
    """Test distinct seeds produce different demand realizations."""
    cfg1 = AegisConfig(seed=101, simulation_days=10)
    cfg2 = AegisConfig(seed=202, simulation_days=10)

    df1 = DeterministicSyntheticGenerator(config=cfg1).generate(scenario="baseline")
    df2 = DeterministicSyntheticGenerator(config=cfg2).generate(scenario="baseline")

    assert not df1["demand_units"].equals(df2["demand_units"])


def test_generator_network_coverage(sample_raw_df: pd.DataFrame, small_config: AegisConfig) -> None:
    """Test generator populates all facilities, warehouses, categories, and dates."""
    expected_rows = len(HOSPITALS) * len(PRODUCT_CATEGORIES) * small_config.simulation_days
    assert len(sample_raw_df) == expected_rows

    assert set(sample_raw_df["hospital_id"].unique()) == {h.hospital_id for h in HOSPITALS}
    assert set(sample_raw_df["warehouse_id"].unique()) == {w.warehouse_id for w in WAREHOUSES}
    assert set(sample_raw_df["category_id"].unique()) == {c.category_id for c in PRODUCT_CATEGORIES}


def test_generator_physics_and_constraints(sample_raw_df: pd.DataFrame) -> None:
    """Test physiological and physical constraints."""
    # Demand is strictly positive
    assert (sample_raw_df["demand_units"] >= 1.0).all()

    # Observed consumption is clipped by demand
    assert (
        sample_raw_df["observed_consumption_units"] <= sample_raw_df["demand_units"] + 1e-5
    ).all()

    # Inventory is non-negative
    assert (sample_raw_df["reported_inventory_units"] >= 0.0).all()

    # Lead times are positive
    assert (sample_raw_df["lead_time_days"] >= 1).all()

    # Stockout occurs when observed consumption < demand
    stockouts = sample_raw_df[sample_raw_df["stockout_flag"] == 1]
    if not stockouts.empty:
        assert (stockouts["observed_consumption_units"] <= stockouts["demand_units"]).all()


def test_generator_scenarios() -> None:
    """Test that outbreak and supply disruption scenarios modify generative regimes."""
    cfg = AegisConfig(seed=42, simulation_days=40)
    gen = DeterministicSyntheticGenerator(config=cfg)

    df_base = gen.generate(scenario="baseline")
    df_outbreak = gen.generate(scenario="outbreak_surge")
    df_disrupt = gen.generate(scenario="supply_disruption")

    # Outbreak scenario produces higher mean surge factor
    assert df_outbreak["surge_factor"].mean() > df_base["surge_factor"].mean()

    # Supply disruption scenario produces higher stockout frequency or longer lead times
    assert (
        df_disrupt["lead_time_days"].mean() >= df_base["lead_time_days"].mean()
        or df_disrupt["stockout_flag"].sum() >= df_base["stockout_flag"].sum()
    )
