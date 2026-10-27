"""Scientific evaluation metrics for point and interval demand forecasting."""

import numpy as np
import pandas as pd


def calculate_mae(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Calculate Mean Absolute Error (MAE)."""
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    if len(yt) == 0:
        return 0.0
    return float(np.mean(np.abs(yt - yp)))


def calculate_rmse(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Calculate Root Mean Squared Error (RMSE)."""
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    if len(yt) == 0:
        return 0.0
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def calculate_wape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Calculate Weighted Absolute Percentage Error (WAPE).

    WAPE = sum(|y_true - y_pred|) / sum(y_true)
    """
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    total_true = np.sum(yt)
    if total_true == 0.0:
        return 0.0 if np.sum(np.abs(yt - yp)) == 0.0 else float("inf")
    return float(np.sum(np.abs(yt - yp)) / total_true)


def calculate_pinball_loss(
    y_true: np.ndarray | pd.Series,
    q_pred: np.ndarray | pd.Series,
    alpha: float,
) -> float:
    """Calculate Pinball Loss (Quantile Loss) for quantile alpha.

    L_alpha(y, q) = max(alpha * (y - q), (1 - alpha) * (q - y))
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"Quantile alpha must be in (0, 1), got {alpha}")
    yt = np.asarray(y_true, dtype=np.float64)
    qp = np.asarray(q_pred, dtype=np.float64)
    if len(yt) == 0:
        return 0.0
    diff = yt - qp
    loss = np.maximum(alpha * diff, (alpha - 1.0) * diff)
    return float(np.mean(loss))


def calculate_interval_coverage(
    y_true: np.ndarray | pd.Series,
    q_lower: np.ndarray | pd.Series,
    q_upper: np.ndarray | pd.Series,
) -> float:
    """Calculate empirical coverage probability of prediction intervals.

    Coverage = P(q_lower <= y_true <= q_upper)
    """
    yt = np.asarray(y_true, dtype=np.float64)
    ql = np.asarray(q_lower, dtype=np.float64)
    qu = np.asarray(q_upper, dtype=np.float64)
    if len(yt) == 0:
        return 0.0
    covered = (yt >= ql) & (yt <= qu)
    return float(np.mean(covered))


def calculate_interval_width(
    q_lower: np.ndarray | pd.Series,
    q_upper: np.ndarray | pd.Series,
) -> tuple[float, float]:
    """Calculate Mean Prediction Interval Width (MPIW) and Median Width.

    Returns (mean_width, median_width).
    """
    ql = np.asarray(q_lower, dtype=np.float64)
    qu = np.asarray(q_upper, dtype=np.float64)
    if len(ql) == 0:
        return 0.0, 0.0
    width = qu - ql
    return float(np.mean(width)), float(np.median(width))


def evaluate_forecast(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    q_lower: np.ndarray | pd.Series | None = None,
    q_upper: np.ndarray | pd.Series | None = None,
    alpha_lower: float = 0.10,
    alpha_upper: float = 0.90,
) -> dict[str, float]:
    """Compute comprehensive point and interval validation metrics."""
    metrics = {
        "MAE": round(calculate_mae(y_true, y_pred), 4),
        "RMSE": round(calculate_rmse(y_true, y_pred), 4),
        "WAPE": round(calculate_wape(y_true, y_pred), 4),
    }

    if q_lower is not None and q_upper is not None:
        mean_w, median_w = calculate_interval_width(q_lower, q_upper)
        metrics["interval_coverage"] = round(
            calculate_interval_coverage(y_true, q_lower, q_upper), 4
        )
        metrics["mean_interval_width"] = round(mean_w, 4)
        metrics["median_interval_width"] = round(median_w, 4)
        metrics["pinball_loss_p10"] = round(calculate_pinball_loss(y_true, q_lower, alpha_lower), 4)
        metrics["pinball_loss_p90"] = round(calculate_pinball_loss(y_true, q_upper, alpha_upper), 4)
        # Median pinball loss
        metrics["pinball_loss_p50"] = round(calculate_pinball_loss(y_true, y_pred, 0.50), 4)

    return metrics


def evaluate_breakdowns(
    df: pd.DataFrame,
    y_true_col: str,
    y_pred_col: str,
    q_lower_col: str | None = None,
    q_upper_col: str | None = None,
    group_col: str = "hospital_id",
) -> pd.DataFrame:
    """Compute metrics broken down by facility (hospital) or product category."""
    rows = []
    for grp_val, grp_df in df.groupby(group_col):
        yt = grp_df[y_true_col].values
        yp = grp_df[y_pred_col].values
        ql = grp_df[q_lower_col].values if q_lower_col and q_lower_col in grp_df else None
        qu = grp_df[q_upper_col].values if q_upper_col and q_upper_col in grp_df else None

        res = evaluate_forecast(yt, yp, ql, qu)
        res[group_col] = grp_val
        res["sample_size"] = len(grp_df)
        rows.append(res)

    res_df = pd.DataFrame(rows)
    # Reorder so group_col is first
    cols = [group_col, "sample_size", "MAE", "RMSE", "WAPE"]
    remaining = [c for c in res_df.columns if c not in cols]
    return res_df[cols + remaining]
