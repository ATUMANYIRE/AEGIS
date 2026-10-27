"""Unit tests for missing data simulation and leakage-safe imputation."""

import pandas as pd

from aegis.data.preprocessor import LeakageSafePreprocessor


def test_missing_data_imputation_forward_only() -> None:
    """Test that missing observations are forward-filled from historical records."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "hospital_id": ["H01"] * 5,
            "category_id": ["PPE"] * 5,
            "observed_consumption_units": [100.0, 105.0, 999.0, 115.0, 120.0],
            "reported_inventory_units": [500.0, 480.0, 999.0, 440.0, 420.0],
            "missing_report_flag": [0, 0, 1, 0, 0],  # Day 3 dropped
        }
    )

    clean_df = LeakageSafePreprocessor.clean_and_impute(df)

    # On day 3 (missing), consumption and inventory should forward-fill day 2's values (105.0 and 480.0), NOT day 4 (115.0)
    assert clean_df.loc[2, "observed_consumption_units"] == 105.0
    assert clean_df.loc[2, "reported_inventory_units"] == 480.0

    # Missing indicator flag must be preserved
    assert clean_df.loc[2, "missing_report_flag"] == 1
