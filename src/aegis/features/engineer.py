"""Leakage-safe feature engineering and chronological dataset partitioning."""

from datetime import date

import numpy as np
import pandas as pd

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES


class FeatureEngineer:
    """Feature engineering pipeline strictly enforcing time-series causality.

    Every feature at time t is computed strictly from observations up to t-1.
    No future observations, future statistics, or global statistics across the entire time series
    are permitted.
    """

    LAGS: list[int] = [1, 2, 3, 7, 14, 21, 28]
    ROLLING_WINDOWS: list[int] = [7, 14, 28]

    def __init__(self) -> None:
        self.hospital_meta = {
            h.hospital_id: {
                "bed_capacity": h.bed_capacity,
                "base_multiplier": h.base_demand_multiplier,
                "tier": h.tier,
                "base_lead_time": h.base_lead_time_days,
            }
            for h in HOSPITALS
        }
        self.category_meta = {
            c.category_id: {
                "base_demand_per_bed": c.base_daily_demand_per_bed,
                "weekend_ratio": c.weekend_ratio,
            }
            for c in PRODUCT_CATEGORIES
        }

    def generate_features(
        self,
        df: pd.DataFrame,
        target_col: str = "demand_units",
        group_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Construct leakage-safe features for each facility-product time series.

        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe containing at least ['date', 'hospital_id', 'category_id', target_col].
        target_col : str, optional
            Target demand column, by default 'demand_units'.
        group_cols : list[str], optional
            Grouping columns for time series, by default ['hospital_id', 'category_id'].

        Returns
        -------
        pd.DataFrame
            Augmented dataframe with lagged, rolling, and temporal features.
        """
        if group_cols is None:
            group_cols = ["hospital_id", "category_id"]

        df_feat = df.copy()

        # Ensure datetime type and strict sorting
        df_feat["date"] = pd.to_datetime(df_feat["date"])
        df_feat = df_feat.sort_values(by=group_cols + ["date"]).reset_index(drop=True)

        # 1. Calendar and cyclical features (strictly known at date t)
        dow_attr = "day_of_week" if hasattr(df_feat["date"].dt, "day_of_week") else "dayofweek"
        doy_attr = "day_of_year" if hasattr(df_feat["date"].dt, "day_of_year") else "dayofyear"
        df_feat["day_of_week"] = getattr(df_feat["date"].dt, dow_attr)
        df_feat["day_of_year"] = getattr(df_feat["date"].dt, doy_attr)
        df_feat["month"] = df_feat["date"].dt.month
        df_feat["is_weekend"] = (df_feat["day_of_week"] >= 5).astype(int)

        # Sinusoidal / cosine cyclical encodings
        df_feat["sin_dow"] = np.sin(2.0 * np.pi * df_feat["day_of_week"] / 7.0)
        df_feat["cos_dow"] = np.cos(2.0 * np.pi * df_feat["day_of_week"] / 7.0)
        df_feat["sin_doy"] = np.sin(2.0 * np.pi * df_feat["day_of_year"] / 365.25)
        df_feat["cos_doy"] = np.cos(2.0 * np.pi * df_feat["day_of_year"] / 365.25)

        # 2. Enrich with static facility and product metadata
        df_feat["bed_capacity"] = df_feat["hospital_id"].map(
            lambda h: self.hospital_meta.get(h, {}).get("bed_capacity", 200)
        )
        df_feat["base_multiplier"] = df_feat["hospital_id"].map(
            lambda h: self.hospital_meta.get(h, {}).get("base_multiplier", 1.0)
        )
        df_feat["base_lead_time"] = df_feat["hospital_id"].map(
            lambda h: self.hospital_meta.get(h, {}).get("base_lead_time", 2)
        )
        df_feat["tier"] = df_feat["hospital_id"].map(
            lambda h: self.hospital_meta.get(h, {}).get("tier", "Community")
        )
        df_feat["base_demand_per_bed"] = df_feat["category_id"].map(
            lambda c: self.category_meta.get(c, {}).get("base_demand_per_bed", 0.5)
        )

        # 3. Leakage-safe lagged demand features (shift >= 1)
        # Note: shift(k) inside groupby ensures lag is within that specific hospital & product
        for lag in self.LAGS:
            col_name = f"lag_{lag}"
            df_feat[col_name] = df_feat.groupby(group_cols)[target_col].shift(lag)

        # 4. Leakage-safe rolling statistics (shift by 1 FIRST, then compute rolling stats)
        # Shifting by 1 guarantees observation at day t is NEVER included in rolling stats for day t
        grouped_shifted = df_feat.groupby(group_cols)[target_col].shift(1)

        for w in self.ROLLING_WINDOWS:
            # Grouped rolling calculation on the shifted series
            roll = grouped_shifted.groupby([df_feat[col] for col in group_cols]).rolling(
                window=w, min_periods=1
            )
            df_feat[f"rolling_mean_{w}"] = roll.mean().reset_index(drop=True)
            df_feat[f"rolling_std_{w}"] = roll.std().fillna(0.0).reset_index(drop=True)
            df_feat[f"rolling_max_{w}"] = roll.max().reset_index(drop=True)
            df_feat[f"rolling_min_{w}"] = roll.min().reset_index(drop=True)

        # 5. Inventory and supply chain lag features (strictly lagged)
        if "reported_inventory_units" in df_feat.columns:
            df_feat["lag_inventory_1"] = df_feat.groupby(group_cols)[
                "reported_inventory_units"
            ].shift(1)
        if "stockout_flag" in df_feat.columns:
            df_feat["lag_stockout_1"] = df_feat.groupby(group_cols)["stockout_flag"].shift(1)
        if "lead_time_days" in df_feat.columns:
            df_feat["lag_lead_time_1"] = df_feat.groupby(group_cols)["lead_time_days"].shift(1)

        # Convert back date column to date object for clean filtering
        df_feat["date"] = df_feat["date"].dt.date
        return df_feat

    @staticmethod
    def chronological_split(
        df: pd.DataFrame,
        train_end_date: str | date,
        val_end_date: str | date,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split dataframe chronologically without random shuffling or future leakage.

        Parameters
        ----------
        df : pd.DataFrame
            Dataset containing a 'date' column.
        train_end_date : str | date
            Last inclusive date for the training partition.
        val_end_date : str | date
            Last inclusive date for the validation (development) partition.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
            (train_df, val_df, test_df)

        Raises
        ------
        ValueError
            If date partitions overlap or ordering is invalid.
        """
        df_copy = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_copy["date"]):
            df_copy["date"] = pd.to_datetime(df_copy["date"]).dt.date

        if isinstance(train_end_date, str):
            train_end = pd.to_datetime(train_end_date).date()
        else:
            train_end = train_end_date

        if isinstance(val_end_date, str):
            val_end = pd.to_datetime(val_end_date).date()
        else:
            val_end = val_end_date

        if train_end >= val_end:
            raise ValueError(
                f"train_end_date ({train_end}) must be strictly earlier than val_end_date ({val_end})"
            )

        train_df = df_copy[df_copy["date"] <= train_end].copy().reset_index(drop=True)
        val_df = (
            df_copy[(df_copy["date"] > train_end) & (df_copy["date"] <= val_end)]
            .copy()
            .reset_index(drop=True)
        )
        test_df = df_copy[df_copy["date"] > val_end].copy().reset_index(drop=True)

        # Verification of zero temporal overlap
        if not train_df.empty and not val_df.empty:
            assert train_df["date"].max() < val_df["date"].min(), (
                "Temporal boundary violated between train and val"
            )
        if not val_df.empty and not test_df.empty:
            assert val_df["date"].max() < test_df["date"].min(), (
                "Temporal boundary violated between val and test"
            )

        return train_df, val_df, test_df
