"""Unit tests for feature engineering transformations and boundaries."""

import pandas as pd

from aegis.config import HOSPITALS


def test_cyclical_feature_boundaries(sample_featured_df: pd.DataFrame) -> None:
    """Test trigonometric sin/cos features are strictly bounded within [-1.0, 1.0]."""
    for col in ["sin_dow", "cos_dow", "sin_doy", "cos_doy"]:
        vals = sample_featured_df[col].values
        assert (vals >= -1.0 - 1e-6).all(), f"{col} has values below -1.0"
        assert (vals <= 1.0 + 1e-6).all(), f"{col} has values above 1.0"


def test_weekend_flag_consistency(sample_featured_df: pd.DataFrame) -> None:
    """Test is_weekend aligns exactly with Saturday and Sunday."""
    dates = pd.to_datetime(sample_featured_df["date"])
    dow_attr = "day_of_week" if hasattr(dates.dt, "day_of_week") else "dayofweek"
    expected_weekend = (getattr(dates.dt, dow_attr) >= 5).astype(int)
    pd.testing.assert_series_equal(
        sample_featured_df["is_weekend"],
        expected_weekend,
        check_names=False,
    )


def test_facility_metadata_enrichment(sample_featured_df: pd.DataFrame) -> None:
    """Test bed_capacity and operational tier are correctly mapped from static topology."""
    hosp_map = {h.hospital_id: h for h in HOSPITALS}

    sample_sub = sample_featured_df.drop_duplicates(subset=["hospital_id"])
    for _, row in sample_sub.iterrows():
        hid = row["hospital_id"]
        expected_beds = hosp_map[hid].bed_capacity
        expected_tier = hosp_map[hid].tier

        assert row["bed_capacity"] == expected_beds
        assert row["tier"] == expected_tier
