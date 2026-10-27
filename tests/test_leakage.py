"""Unit tests verifying temporal causality and strict absence of data leakage."""

from datetime import date

import pandas as pd
import pytest

from aegis.features.engineer import FeatureEngineer


def test_lag_values_match_historical_shift(sample_featured_df: pd.DataFrame) -> None:
    """Test lag_1 and lag_7 strictly equal observations from t-1 and t-7."""
    df_sorted = sample_featured_df.sort_values(
        by=["hospital_id", "category_id", "date"]
    ).reset_index(drop=True)

    for (h, c), group in df_sorted.groupby(["hospital_id", "category_id"]):
        y = group["demand_units"].values
        lag_1 = group["lag_1"].values
        lag_7 = group["lag_7"].values

        # For index >= 1, lag_1 must match y[idx - 1]
        for idx in range(1, len(y)):
            assert lag_1[idx] == pytest.approx(y[idx - 1]), (
                f"Lag-1 mismatch at index {idx} for {h}-{c}"
            )

        # For index >= 7, lag_7 must match y[idx - 7]
        for idx in range(7, len(y)):
            assert lag_7[idx] == pytest.approx(y[idx - 7]), (
                f"Lag-7 mismatch at index {idx} for {h}-{c}"
            )


def test_rolling_features_do_not_leak_current_target(sample_raw_df: pd.DataFrame) -> None:
    """Verify that altering demand at day t does NOT change rolling statistics for day t.

    This proves that rolling statistics are shifted by at least 1 day prior to windowing.
    """
    engineer = FeatureEngineer()

    # Generate baseline features
    df1 = engineer.generate_features(sample_raw_df)

    # Select specific time series (H01, PPE) and mutate day 10
    sample_mutated = sample_raw_df.copy()
    mask = (sample_mutated["hospital_id"] == "H01") & (sample_mutated["category_id"] == "PPE")
    h01_indices = sample_mutated[mask].index.tolist()
    target_idx = h01_indices[10]
    original_val = sample_mutated.loc[target_idx, "demand_units"]
    sample_mutated.loc[target_idx, "demand_units"] = original_val + 10_000.0

    df2 = engineer.generate_features(sample_mutated)

    # Filter both to H01, PPE series sorted chronologically
    s1 = (
        df1[(df1["hospital_id"] == "H01") & (df1["category_id"] == "PPE")]
        .sort_values("date")
        .reset_index(drop=True)
    )
    s2 = (
        df2[(df2["hospital_id"] == "H01") & (df2["category_id"] == "PPE")]
        .sort_values("date")
        .reset_index(drop=True)
    )

    roll_col = "rolling_mean_7"
    # At index 10 (day t), rolling mean MUST be identical (strictly shifted)
    assert s1.loc[10, roll_col] == pytest.approx(s2.loc[10, roll_col]), (
        "Target leakage detected! Mutating demand at day t altered rolling_mean_7 at day t."
    )

    # At index 11 (day t + 1), the mutation must legitimately appear
    assert s1.loc[11, roll_col] != s2.loc[11, roll_col]


def test_chronological_split_strict_boundaries(sample_featured_df: pd.DataFrame) -> None:
    """Test chronological partitioning guarantees non-overlapping temporal segments."""
    train_end = date(2025, 1, 15)
    val_end = date(2025, 1, 22)

    train_df, val_df, test_df = FeatureEngineer.chronological_split(
        sample_featured_df, train_end_date=train_end, val_end_date=val_end
    )

    assert train_df["date"].max() <= train_end
    assert val_df["date"].min() > train_end
    assert val_df["date"].max() <= val_end
    assert test_df["date"].min() > val_end

    assert train_df["date"].max() < val_df["date"].min()
    assert val_df["date"].max() < test_df["date"].min()


def test_chronological_split_invalid_order_raises(sample_featured_df: pd.DataFrame) -> None:
    """Test splitting raises ValueError if train_end is after or equal to val_end."""
    with pytest.raises(ValueError):
        FeatureEngineer.chronological_split(
            sample_featured_df,
            train_end_date=date(2025, 1, 20),
            val_end_date=date(2025, 1, 15),
        )
