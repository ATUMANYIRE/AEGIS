"""Baseline forecasting models: Seasonal-Naive and Moving-Average."""

import numpy as np
import pandas as pd


class SeasonalNaiveForecaster:
    """Seasonal Naive forecaster predicting demand based on identical day of prior cycle.

    In hospital operations with 7-day weekly rhythms, y_hat(t) = y(t - 7).
    """

    def __init__(self, season_length: int = 7) -> None:
        self.season_length = season_length
        self.history_: dict[tuple[str, str], list[float]] = {}
        self.residual_quantiles_: tuple[float, float] = (0.0, 0.0)

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "demand_units",
        group_cols: list[str] | None = None,
    ) -> "SeasonalNaiveForecaster":
        """Record historical values and estimate empirical residual quantiles on training set."""
        if group_cols is None:
            group_cols = ["hospital_id", "category_id"]

        df_sorted = df_train.sort_values(by=group_cols + ["date"]).reset_index(drop=True)

        residuals = []
        for grp_keys, grp in df_sorted.groupby(group_cols):
            y_vals = grp[target_col].tolist()
            self.history_[grp_keys] = y_vals

            # Compute in-sample residuals for seasons after the first season_length
            if len(y_vals) > self.season_length:
                y_arr = np.array(y_vals)
                preds = y_arr[: -self.season_length]
                actuals = y_arr[self.season_length :]
                residuals.extend((actuals - preds).tolist())

        if residuals:
            self.residual_quantiles_ = (
                float(np.percentile(residuals, 10)),
                float(np.percentile(residuals, 90)),
            )
        else:
            self.residual_quantiles_ = (-5.0, 5.0)

        return self

    def predict(
        self,
        df: pd.DataFrame,
        target_col: str = "demand_units",
        group_cols: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point forecasts and prediction intervals using lag-7.

        Returns (point_predictions, lower_bounds, upper_bounds).
        """
        if group_cols is None:
            group_cols = ["hospital_id", "category_id"]

        # If lag_7 feature exists in df, use it directly (strict leakage safe)
        lag_col = f"lag_{self.season_length}"
        if lag_col in df.columns:
            preds = df[lag_col].copy()
            # If missing, fall back to lag_1 or mean
            if "lag_1" in df.columns:
                preds = preds.fillna(df["lag_1"])
            default_val = (
                float(df[target_col].mean())
                if target_col in df and not df[target_col].isna().all()
                else 50.0
            )
            preds = preds.fillna(default_val).values
        else:
            # Fallback using recorded history
            preds = []
            for _, row in df.iterrows():
                key = tuple(row[col] for col in group_cols)
                hist = self.history_.get(key, [])
                if len(hist) >= self.season_length:
                    preds.append(hist[-self.season_length])
                elif hist:
                    preds.append(hist[-1])
                else:
                    preds.append(50.0)
            preds = np.array(preds, dtype=np.float64)

        preds = np.nan_to_num(preds, nan=50.0)
        preds = np.maximum(0.0, preds)
        q_lower = np.maximum(0.0, preds + self.residual_quantiles_[0])
        q_upper = np.maximum(q_lower, preds + self.residual_quantiles_[1])
        return preds, q_lower, q_upper


class MovingAverageForecaster:
    """Moving Average forecaster predicting demand based on shifted historical window."""

    def __init__(self, window: int = 7) -> None:
        self.window = window
        self.residual_quantiles_: tuple[float, float] = (0.0, 0.0)

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "demand_units",
        group_cols: list[str] | None = None,
    ) -> "MovingAverageForecaster":
        """Compute empirical residual quantiles on the training partition."""
        if group_cols is None:
            group_cols = ["hospital_id", "category_id"]

        roll_col = f"rolling_mean_{self.window}"
        if roll_col in df_train.columns:
            valid = df_train.dropna(subset=[roll_col, target_col])
            residuals = (valid[target_col] - valid[roll_col]).values
        else:
            # Calculate shifted rolling mean
            grouped = df_train.groupby(group_cols)[target_col].shift(1)
            roll = (
                grouped.groupby([df_train[c] for c in group_cols])
                .rolling(self.window, min_periods=1)
                .mean()
                .reset_index(drop=True)
            )
            residuals = (df_train[target_col] - roll).dropna().values

        if len(residuals) > 0:
            self.residual_quantiles_ = (
                float(np.percentile(residuals, 10)),
                float(np.percentile(residuals, 90)),
            )
        else:
            self.residual_quantiles_ = (-5.0, 5.0)

        return self

    def predict(
        self,
        df: pd.DataFrame,
        target_col: str = "demand_units",
        group_cols: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point forecasts and prediction intervals.

        Returns (point_predictions, lower_bounds, upper_bounds).
        """
        roll_col = f"rolling_mean_{self.window}"
        if roll_col in df.columns:
            fallback = df["lag_1"] if "lag_1" in df.columns else 50.0
            default_val = (
                float(df[target_col].mean())
                if target_col in df and not df[target_col].isna().all()
                else 50.0
            )
            preds = df[roll_col].fillna(fallback).fillna(default_val).values
        else:
            if group_cols is None:
                group_cols = ["hospital_id", "category_id"]
            grouped = df.groupby(group_cols)[target_col].shift(1)
            preds = (
                grouped.groupby([df[c] for c in group_cols])
                .rolling(self.window, min_periods=1)
                .mean()
                .reset_index(drop=True)
                .fillna(50.0)
                .values
            )

        preds = np.nan_to_num(preds, nan=50.0)
        preds = np.maximum(0.0, preds)
        q_lower = np.maximum(0.0, preds + self.residual_quantiles_[0])
        q_upper = np.maximum(q_lower, preds + self.residual_quantiles_[1])
        return preds, q_lower, q_upper
