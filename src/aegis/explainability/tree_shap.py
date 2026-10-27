"""TreeSHAP explainability engine for XGBoost demand forecasting."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap

from aegis.models.regressor import XGBoostDemandForecaster
from aegis.models.serialization import ModelSerializer
from aegis.utils.logging import setup_logger

logger = setup_logger("aegis.explainability.shap")


class TreeSHAPExplainer:
    """Computes and validates TreeSHAP feature attributions for trained XGBoost demand forecasters."""

    def __init__(
        self,
        model_path: str | Path = "models/xgboost_demand.joblib",
        forecaster: XGBoostDemandForecaster | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.forecaster = forecaster
        self.metadata: dict[str, Any] = {}
        self.explainer: shap.TreeExplainer | None = None
        self.feature_names: list[str] = []
        self._initialize()

    def _initialize(self) -> None:
        """Load forecaster if needed and initialize TreeExplainer."""
        if self.forecaster is None and self.model_path.exists():
            try:
                loaded, meta = ModelSerializer.load(self.model_path)
                if isinstance(loaded, XGBoostDemandForecaster):
                    self.forecaster = loaded
                    self.metadata = meta
                else:
                    logger.warning(
                        "Loaded model is not an XGBoostDemandForecaster: %s", type(loaded)
                    )
            except Exception as e:
                logger.error("Failed to load model from %s: %s", self.model_path, e)

        if self.forecaster is not None and hasattr(self.forecaster, "model"):
            try:
                self.feature_names = list(self.forecaster.feature_names_)
                self.explainer = shap.TreeExplainer(self.forecaster.model)
                logger.info(
                    "TreeExplainer successfully initialized with %d features.",
                    len(self.feature_names),
                )
            except Exception as e:
                logger.error("Failed to construct shap.TreeExplainer: %s", e)

    @property
    def is_available(self) -> bool:
        """Return True if forecaster and TreeExplainer are loaded and ready."""
        return self.explainer is not None and self.forecaster is not None

    def explain_dataset(self, df: pd.DataFrame) -> tuple[np.ndarray, float]:
        """Compute SHAP values and base value for a dataset.

        Returns
        -------
        tuple[np.ndarray, float]
            (shap_matrix of shape [N, num_features], expected_value)
        """
        if not self.is_available:
            raise RuntimeError("TreeSHAPExplainer is not initialized or model is missing.")

        assert self.forecaster is not None
        assert self.explainer is not None

        X = self.forecaster._prepare_features(df, is_fit=False)
        shap_values = self.explainer(X)
        base_val = float(self.explainer.expected_value)
        return shap_values.values, base_val

    def get_global_importance(self, df: pd.DataFrame, top_k: int = 15) -> pd.DataFrame:
        """Compute mean absolute SHAP feature importance across the dataset.

        Parameters
        ----------
        df : pd.DataFrame
            Featured dataset sample.
        top_k : int
            Number of top features to return.

        Returns
        -------
        pd.DataFrame
            Columns: [feature, mean_abs_shap, mean_shap]
        """
        if not self.is_available:
            return pd.DataFrame(columns=["feature", "mean_abs_shap", "mean_shap"])

        shap_matrix, _ = self.explain_dataset(df)
        mean_abs = np.mean(np.abs(shap_matrix), axis=0)
        mean_signed = np.mean(shap_matrix, axis=0)

        importance_df = pd.DataFrame(
            {
                "feature": self.feature_names,
                "mean_abs_shap": mean_abs,
                "mean_shap": mean_signed,
            }
        ).sort_values("mean_abs_shap", ascending=False)

        return importance_df.head(top_k).reset_index(drop=True)

    def explain_instance(self, df_row: pd.DataFrame) -> dict[str, Any]:
        """Compute local feature attributions for a single hospital-product observation.

        Parameters
        ----------
        df_row : pd.DataFrame
            Single-row DataFrame.

        Returns
        -------
        dict[str, Any]
            Detailed breakdown containing base value, prediction, and feature contributions.
        """
        if not self.is_available:
            return {"status": "UNAVAILABLE", "error": "Model or explainer not loaded."}

        assert self.forecaster is not None
        assert self.explainer is not None

        if len(df_row) != 1:
            df_row = df_row.head(1)

        X = self.forecaster._prepare_features(df_row, is_fit=False)
        shap_res = self.explainer(X)

        shap_vals = shap_res.values[0]
        base_val = float(self.explainer.expected_value)
        preds, q_lower, q_upper = self.forecaster.predict(df_row)
        pred_val = float(preds[0])

        feature_vals = [X.iloc[0][f] for f in self.feature_names]

        # Sort feature contributions
        contribs = []
        for f_name, f_val, s_val in zip(self.feature_names, feature_vals, shap_vals, strict=False):
            contribs.append(
                {
                    "feature": f_name,
                    "value": str(f_val),
                    "shap_value": round(float(s_val), 4),
                    "abs_shap": round(abs(float(s_val)), 4),
                }
            )

        contribs_sorted = sorted(contribs, key=lambda c: c["abs_shap"], reverse=True)
        top_pos = [c for c in contribs_sorted if c["shap_value"] > 0][:5]
        top_neg = [c for c in contribs_sorted if c["shap_value"] < 0][:5]

        # Verify additivity
        shap_sum = base_val + float(np.sum(shap_vals))
        additivity_error = abs(pred_val - shap_sum)

        return {
            "status": "SUCCESS",
            "base_value": round(base_val, 2),
            "prediction": round(pred_val, 2),
            "lower_interval_p10": round(float(q_lower[0]), 2),
            "upper_interval_p90": round(float(q_upper[0]), 2),
            "shap_sum": round(shap_sum, 2),
            "additivity_error": round(additivity_error, 6),
            "is_additive": bool(additivity_error < 0.05),
            "top_positive_features": top_pos,
            "top_negative_features": top_neg,
            "all_contributions": contribs_sorted,
        }
