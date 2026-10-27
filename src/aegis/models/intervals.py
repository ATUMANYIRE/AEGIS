"""Prediction interval estimation via Conformal Prediction and Quantile Estimation."""

import numpy as np
import pandas as pd


class ConformalIntervalCalibrator:
    """Split Conformal Prediction for distribution-free, finite-sample prediction intervals.

    Given a point predictor f_hat and a held-out calibration (validation) set (X_val, y_val),
    computes the nonconformity scores R_i = |y_i - f_hat(X_i)|.
    Guarantees 1 - alpha coverage on exchangeable test observations.
    """

    def __init__(self, confidence_level: float = 0.80) -> None:
        """Parameters
        ----------
        confidence_level : float, optional
            Target prediction interval coverage (e.g., 0.80 for 80% coverage), by default 0.80.
        """
        self.confidence_level = confidence_level
        self.alpha = 1.0 - confidence_level
        self.q_hat: float = 0.0
        self.lower_bias: float = 0.0
        self.upper_bias: float = 0.0

    def calibrate(
        self, y_val: np.ndarray | pd.Series, y_val_pred: np.ndarray | pd.Series
    ) -> "ConformalIntervalCalibrator":
        """Compute conformal nonconformity quantile on held-out development fold."""
        yt = np.asarray(y_val, dtype=np.float64)
        yp = np.asarray(y_val_pred, dtype=np.float64)
        n = len(yt)
        if n == 0:
            self.q_hat = 10.0
            return self

        # Nonconformity scores: absolute residuals
        residuals = yt - yp
        abs_residuals = np.abs(residuals)

        # Finite-sample adjusted quantile: ceil((n + 1) * (1 - alpha)) / n
        p = min(1.0, np.ceil((n + 1) * (1.0 - self.alpha)) / n)
        self.q_hat = float(np.quantile(abs_residuals, min(1.0, p), method="higher"))

        # Asymmetric quantile calibration for pinball evaluation
        p_lower = self.alpha / 2.0
        p_upper = 1.0 - (self.alpha / 2.0)
        self.lower_bias = float(np.percentile(residuals, 100 * p_lower))
        self.upper_bias = float(np.percentile(residuals, 100 * p_upper))

        return self

    def predict_intervals(
        self, y_pred: np.ndarray | pd.Series, symmetric: bool = True
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute lower and upper prediction intervals for point predictions.

        Returns (q_lower, q_upper) clipped to non-negative values.
        """
        yp = np.asarray(y_pred, dtype=np.float64)
        if symmetric:
            q_lower = np.maximum(0.0, yp - self.q_hat)
            q_upper = yp + self.q_hat
        else:
            q_lower = np.maximum(0.0, yp + self.lower_bias)
            q_upper = np.maximum(q_lower, yp + self.upper_bias)
        return q_lower, q_upper
