"""Supervised regression forecasting models: Regularized Ridge and XGBoost."""

from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from aegis.models.intervals import ConformalIntervalCalibrator


class RegularizedRegressionForecaster:
    """Regularized Ridge Regression forecaster with temporal scaling and conformal intervals."""

    def __init__(self, alphas: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)) -> None:
        self.alphas = alphas
        self.scaler = StandardScaler()
        self.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self.model = RidgeCV(alphas=list(self.alphas))
        self.conformal = ConformalIntervalCalibrator(confidence_level=0.80)
        self.numeric_cols_: list[str] = []
        self.cat_cols_: list[str] = []

    def _prepare_features(self, df: pd.DataFrame, is_fit: bool = False) -> np.ndarray:
        """Extract and preprocess features strictly preventing future leakage."""
        if is_fit:
            self.cat_cols_ = [
                c for c in ["hospital_id", "category_id", "tier", "warehouse_id"] if c in df.columns
            ]
            exclude = set(self.cat_cols_) | {
                "date",
                "demand_units",
                "observed_consumption_units",
                "reported_inventory_units",
                "stockout_flag",
                "surge_factor",
                "is_synthetic",
                "synthetic_scenario",
                "missing_report_flag",
            }
            self.numeric_cols_ = [
                c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
            ]

        X_num = df[self.numeric_cols_].fillna(0.0).values
        if is_fit:
            X_num_scaled = self.scaler.fit_transform(X_num)
        else:
            X_num_scaled = self.scaler.transform(X_num)

        if self.cat_cols_:
            X_cat = df[self.cat_cols_].astype(str).values
            if is_fit:
                X_cat_encoded = self.encoder.fit_transform(X_cat)
            else:
                X_cat_encoded = self.encoder.transform(X_cat)
            return np.hstack([X_num_scaled, X_cat_encoded])
        return X_num_scaled

    def fit(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame | None = None,
        target_col: str = "demand_units",
    ) -> "RegularizedRegressionForecaster":
        """Fit scaler, encoder, and Ridge regressor strictly on training fold."""
        X_train = self._prepare_features(df_train, is_fit=True)
        y_train = df_train[target_col].values
        self.model.fit(X_train, y_train)

        # Calibrate conformal prediction intervals on development (validation) fold
        if df_val is not None and not df_val.empty:
            y_val_pred = self.predict_point(df_val)
            self.conformal.calibrate(df_val[target_col].values, y_val_pred)
        else:
            y_train_pred = self.predict_point(df_train)
            self.conformal.calibrate(y_train, y_train_pred)

        return self

    def predict_point(self, df: pd.DataFrame) -> np.ndarray:
        """Generate point demand predictions."""
        X = self._prepare_features(df, is_fit=False)
        preds = self.model.predict(X)
        return np.maximum(0.0, preds)

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point forecasts and calibrated 80% prediction intervals."""
        preds = self.predict_point(df)
        q_lower, q_upper = self.conformal.predict_intervals(preds, symmetric=False)
        return preds, q_lower, q_upper


class XGBoostDemandForecaster:
    """Extreme Gradient Boosting forecaster with hyperparameter tuning on validation fold."""

    def __init__(
        self,
        n_estimators: int = 150,
        max_depth: int = 5,
        learning_rate: float = 0.08,
        subsample: float = 0.85,
        colsample_bytree: float = 0.85,
        random_state: int = 42,
    ) -> None:
        self.params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
            "n_jobs": -1,
        }
        self.model = xgb.XGBRegressor(objective="reg:squarederror", **self.params)
        self.q10_model: xgb.XGBRegressor | None = None
        self.q90_model: xgb.XGBRegressor | None = None
        self.conformal = ConformalIntervalCalibrator(confidence_level=0.80)
        self.feature_names_: list[str] = []
        self.best_params_: dict[str, Any] = self.params.copy()

    def _prepare_features(self, df: pd.DataFrame, is_fit: bool = False) -> pd.DataFrame:
        """Create categorical encodings and feature matrix."""
        df_copy = df.copy()
        cat_cols = [
            c
            for c in ["hospital_id", "category_id", "tier", "warehouse_id"]
            if c in df_copy.columns
        ]
        for c in cat_cols:
            df_copy[c] = df_copy[c].astype("category")

        exclude = {
            "date",
            "demand_units",
            "observed_consumption_units",
            "reported_inventory_units",
            "stockout_flag",
            "surge_factor",
            "is_synthetic",
            "synthetic_scenario",
            "missing_report_flag",
        }
        if is_fit:
            self.feature_names_ = [c for c in df_copy.columns if c not in exclude]

        return df_copy[self.feature_names_]

    def tune_and_fit(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
        target_col: str = "demand_units",
    ) -> "XGBoostDemandForecaster":
        """Hyperparameter tuning strictly on validation fold to prevent test leakage."""
        X_train = self._prepare_features(df_train, is_fit=True)
        y_train = df_train[target_col].values
        X_val = self._prepare_features(df_val, is_fit=False)
        y_val = df_val[target_col].values

        best_score = float("inf")
        candidate_depths = [3, 5, 6]
        candidate_lrs = [0.04, 0.08, 0.12]

        for depth in candidate_depths:
            for lr in candidate_lrs:
                trial = xgb.XGBRegressor(
                    n_estimators=self.params["n_estimators"],
                    max_depth=depth,
                    learning_rate=lr,
                    subsample=self.params["subsample"],
                    colsample_bytree=self.params["colsample_bytree"],
                    random_state=self.params["random_state"],
                    enable_categorical=True,
                    n_jobs=-1,
                )
                trial.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                val_preds = trial.predict(X_val)
                val_mae = float(np.mean(np.abs(y_val - val_preds)))
                if val_mae < best_score:
                    best_score = val_mae
                    self.best_params_["max_depth"] = depth
                    self.best_params_["learning_rate"] = lr

        # Fit final point regressor with optimal params
        self.model = xgb.XGBRegressor(
            objective="reg:squarederror",
            enable_categorical=True,
            **self.best_params_,
        )
        self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # Fit dedicated quantile regressors for pinball & intervals
        # Alpha 0.10
        self.q10_model = xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=0.10,
            enable_categorical=True,
            **self.best_params_,
        )
        self.q10_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # Alpha 0.90
        self.q90_model = xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=0.90,
            enable_categorical=True,
            **self.best_params_,
        )
        self.q90_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # Also calibrate conformal calibrator on validation fold
        val_point = np.maximum(0.0, self.model.predict(X_val))
        self.conformal.calibrate(y_val, val_point)

        return self

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point forecasts, 10th percentile, and 90th percentile bounds."""
        X = self._prepare_features(df, is_fit=False)
        point_preds = np.maximum(0.0, self.model.predict(X))

        if self.q10_model is not None and self.q90_model is not None:
            q_lower = np.maximum(0.0, self.q10_model.predict(X))
            q_upper = np.maximum(q_lower, self.q90_model.predict(X))
        else:
            q_lower, q_upper = self.conformal.predict_intervals(point_preds, symmetric=False)

        return point_preds, q_lower, q_upper
