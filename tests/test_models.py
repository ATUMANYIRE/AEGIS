"""Unit tests for forecasting models and interval calibration."""

from datetime import date

import numpy as np
import pandas as pd

from aegis.features.engineer import FeatureEngineer
from aegis.models.baselines import MovingAverageForecaster, SeasonalNaiveForecaster
from aegis.models.intervals import ConformalIntervalCalibrator
from aegis.models.regressor import RegularizedRegressionForecaster, XGBoostDemandForecaster


def test_conformal_calibrator() -> None:
    """Test ConformalIntervalCalibrator produces valid intervals covering actuals."""
    calibrator = ConformalIntervalCalibrator(confidence_level=0.80)
    y_val = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    y_pred = np.array([11.0, 19.0, 32.0, 38.0, 51.0])

    calibrator.calibrate(y_val, y_pred)
    assert calibrator.q_hat > 0.0

    ql, qu = calibrator.predict_intervals(y_pred, symmetric=True)
    assert (ql <= y_pred).all()
    assert (qu >= y_pred).all()
    assert (ql >= 0.0).all()  # Non-negative clipping


def test_seasonal_naive_forecaster(sample_featured_df: pd.DataFrame) -> None:
    """Test SeasonalNaiveForecaster produces valid predictions and intervals."""
    forecaster = SeasonalNaiveForecaster(season_length=7)
    forecaster.fit(sample_featured_df)

    preds, ql, qu = forecaster.predict(sample_featured_df)
    assert len(preds) == len(sample_featured_df)
    assert (preds >= 0.0).all()
    assert (ql <= qu).all()


def test_moving_average_forecaster(sample_featured_df: pd.DataFrame) -> None:
    """Test MovingAverageForecaster produces valid predictions and intervals."""
    forecaster = MovingAverageForecaster(window=7)
    forecaster.fit(sample_featured_df)

    preds, ql, qu = forecaster.predict(sample_featured_df)
    assert len(preds) == len(sample_featured_df)
    assert (preds >= 0.0).all()
    assert (ql <= qu).all()


def test_ridge_regression_forecaster(sample_featured_df: pd.DataFrame) -> None:
    """Test Regularized Ridge regression fits, scales, and generates intervals."""
    train_df, val_df, test_df = FeatureEngineer.chronological_split(
        sample_featured_df,
        train_end_date=date(2025, 1, 15),
        val_end_date=date(2025, 1, 22),
    )

    ridge = RegularizedRegressionForecaster()
    ridge.fit(train_df, val_df)

    preds, ql, qu = ridge.predict(test_df)
    assert len(preds) == len(test_df)
    assert (preds >= 0.0).all()
    assert (ql <= qu).all()


def test_xgboost_demand_forecaster(sample_featured_df: pd.DataFrame) -> None:
    """Test XGBoost demand forecaster tuning, training, and quantile intervals."""
    train_df, val_df, test_df = FeatureEngineer.chronological_split(
        sample_featured_df,
        train_end_date=date(2025, 1, 15),
        val_end_date=date(2025, 1, 22),
    )

    xgb_model = XGBoostDemandForecaster(n_estimators=10)
    xgb_model.tune_and_fit(train_df, val_df)

    preds, ql, qu = xgb_model.predict(test_df)
    assert len(preds) == len(test_df)
    assert (preds >= 0.0).all()
    assert (ql <= qu).all()
