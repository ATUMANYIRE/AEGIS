"""Unit tests validating mathematical correctness of evaluation metrics."""

import numpy as np
import pytest

from aegis.metrics.evaluation import (
    calculate_interval_coverage,
    calculate_interval_width,
    calculate_mae,
    calculate_pinball_loss,
    calculate_rmse,
    calculate_wape,
    evaluate_forecast,
)


def test_calculate_mae() -> None:
    """Test MAE against hand-calculated ground truth."""
    yt = np.array([10.0, 20.0, 30.0])
    yp = np.array([12.0, 18.0, 33.0])
    # Diffs: |10-12|=2, |20-18|=2, |30-33|=3 -> sum=7, mean=7/3
    assert calculate_mae(yt, yp) == pytest.approx(7.0 / 3.0)


def test_calculate_rmse() -> None:
    """Test RMSE against hand-calculated ground truth."""
    yt = np.array([10.0, 20.0, 30.0])
    yp = np.array([10.0, 24.0, 30.0])
    # Sq diffs: 0, 16, 0 -> mean=16/3 -> sqrt(16/3) = 4 / sqrt(3)
    assert calculate_rmse(yt, yp) == pytest.approx(np.sqrt(16.0 / 3.0))


def test_calculate_wape() -> None:
    """Test WAPE against hand-calculated ground truth."""
    yt = np.array([100.0, 100.0])
    yp = np.array([110.0, 90.0])
    # Abs diffs: 10 + 10 = 20. Total true: 200. WAPE = 20 / 200 = 0.10
    assert calculate_wape(yt, yp) == pytest.approx(0.10)


def test_calculate_pinball_loss() -> None:
    """Test Pinball / Quantile loss on over-prediction and under-prediction."""
    # Under-prediction: y=20, q=15 -> diff=5 > 0 -> loss = alpha * 5
    assert calculate_pinball_loss(np.array([20.0]), np.array([15.0]), alpha=0.90) == pytest.approx(
        4.50
    )
    assert calculate_pinball_loss(np.array([20.0]), np.array([15.0]), alpha=0.10) == pytest.approx(
        0.50
    )

    # Over-prediction: y=10, q=15 -> diff=-5 < 0 -> loss = (1 - alpha) * 5
    assert calculate_pinball_loss(np.array([10.0]), np.array([15.0]), alpha=0.90) == pytest.approx(
        0.50
    )
    assert calculate_pinball_loss(np.array([10.0]), np.array([15.0]), alpha=0.10) == pytest.approx(
        4.50
    )


def test_calculate_interval_coverage() -> None:
    """Test prediction interval empirical coverage."""
    yt = np.array([10.0, 20.0, 30.0, 40.0])
    ql = np.array(
        [8.0, 15.0, 35.0, 35.0]
    )  # 10 in [8,12]: Yes. 20 in [15,25]: Yes. 30 in [35,45]: No. 40 in [35,45]: Yes.
    qu = np.array([12.0, 25.0, 45.0, 45.0])
    # Covered: 3 out of 4 -> 0.75
    assert calculate_interval_coverage(yt, ql, qu) == pytest.approx(0.75)


def test_calculate_interval_width() -> None:
    """Test MPIW and median interval width."""
    ql = np.array([10.0, 20.0, 30.0])
    qu = np.array([14.0, 26.0, 42.0])
    # Widths: 4, 6, 12 -> mean = 22/3, median = 6.0
    mean_w, med_w = calculate_interval_width(ql, qu)
    assert mean_w == pytest.approx(22.0 / 3.0)
    assert med_w == pytest.approx(6.0)


def test_evaluate_forecast_integration() -> None:
    """Test full evaluation pipeline dictionary."""
    yt = np.array([50.0, 60.0, 70.0])
    yp = np.array([52.0, 58.0, 71.0])
    ql = np.array([45.0, 55.0, 65.0])
    qu = np.array([55.0, 65.0, 75.0])

    res = evaluate_forecast(yt, yp, ql, qu)
    assert "MAE" in res
    assert "RMSE" in res
    assert "WAPE" in res
    assert "interval_coverage" in res
    assert "mean_interval_width" in res
    assert "pinball_loss_p10" in res
    assert "pinball_loss_p90" in res
    assert res["interval_coverage"] == 1.0  # All points inside [ql, qu]
