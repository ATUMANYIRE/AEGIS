"""Shared pytest fixtures for AEGIS test suite."""

import pandas as pd
import pytest

from aegis.config import AegisConfig
from aegis.data.generator import DeterministicSyntheticGenerator
from aegis.features.engineer import FeatureEngineer


@pytest.fixture
def small_config() -> AegisConfig:
    """Config with short 30-day simulation for fast unit tests."""
    return AegisConfig(
        seed=123,
        start_date="2025-01-01",
        simulation_days=30,
        train_end_day=20,
        val_end_day=25,
    )


@pytest.fixture
def sample_raw_df(small_config: AegisConfig) -> pd.DataFrame:
    """Sample raw synthetic dataset generated with small config."""
    generator = DeterministicSyntheticGenerator(config=small_config)
    return generator.generate(scenario="baseline")


@pytest.fixture
def sample_featured_df(sample_raw_df: pd.DataFrame) -> pd.DataFrame:
    """Sample featured dataset with lagged and rolling columns."""
    engineer = FeatureEngineer()
    return engineer.generate_features(sample_raw_df)
