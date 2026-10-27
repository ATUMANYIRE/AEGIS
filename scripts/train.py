"""Training pipeline for baseline and gradient boosted demand forecasting models."""

import argparse
import json
from pathlib import Path

import pandas as pd

from aegis.features.engineer import FeatureEngineer
from aegis.metrics.evaluation import evaluate_forecast
from aegis.models.baselines import MovingAverageForecaster, SeasonalNaiveForecaster
from aegis.models.regressor import RegularizedRegressionForecaster, XGBoostDemandForecaster
from aegis.models.serialization import ModelSerializer
from aegis.utils.logging import setup_logger

logger = setup_logger("aegis.train")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AEGIS Forecasting Model Training Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to JSON training config file",
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/processed/featured_dataset.parquet",
        help="Path to preprocessed featured dataset",
    )
    parser.add_argument(
        "--train-end-date",
        type=str,
        default="2025-09-17",
        help="End date for training split (inclusive)",
    )
    parser.add_argument(
        "--val-end-date",
        type=str,
        default="2025-11-06",
        help="End date for validation split (inclusive)",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default="models",
        help="Directory to persist trained model artifacts",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="metrics",
        help="Directory to save validation metrics",
    )
    args = parser.parse_args()
    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            for k, v in cfg_data.items():
                attr_name = k.replace("-", "_")
                if hasattr(args, attr_name):
                    setattr(args, attr_name, v)
    return args


def main() -> None:
    args = parse_args()
    logger.info("Loading preprocessed dataset from %s", args.data)
    df = pd.read_parquet(args.data)

    # 1. Chronological Partitioning (Strict temporal boundaries)
    logger.info(
        "Partitioning dataset chronologically: train <= %s, val <= %s",
        args.train_end_date,
        args.val_end_date,
    )
    train_df, val_df, test_df = FeatureEngineer.chronological_split(
        df, train_end_date=args.train_end_date, val_end_date=args.val_end_date
    )
    logger.info(
        "Partition sizes: Train=%d (%s to %s), Val=%d (%s to %s), Test=%d (%s to %s)",
        len(train_df),
        train_df["date"].min(),
        train_df["date"].max(),
        len(val_df),
        val_df["date"].min(),
        val_df["date"].max(),
        len(test_df),
        test_df["date"].min(),
        test_df["date"].max(),
    )

    models_dir = Path(args.models_dir)
    metrics_dir = Path(args.metrics_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    y_val = val_df["demand_units"].values
    val_results = {}

    # 2. Train Seasonal-Naive Forecaster
    logger.info("Fitting Seasonal-Naive baseline forecaster...")
    sn_model = SeasonalNaiveForecaster(season_length=7)
    sn_model.fit(train_df)
    sn_pred, sn_lower, sn_upper = sn_model.predict(val_df)
    val_results["Seasonal_Naive"] = evaluate_forecast(y_val, sn_pred, sn_lower, sn_upper)
    ModelSerializer.save(
        sn_model,
        models_dir,
        "seasonal_naive",
        {
            "model_type": "SeasonalNaiveForecaster",
            "season_length": 7,
            "train_records": len(train_df),
        },
    )

    # 3. Train Moving-Average Forecaster
    logger.info("Fitting Moving-Average baseline forecaster...")
    ma_model = MovingAverageForecaster(window=7)
    ma_model.fit(train_df)
    ma_pred, ma_lower, ma_upper = ma_model.predict(val_df)
    val_results["Moving_Average"] = evaluate_forecast(y_val, ma_pred, ma_lower, ma_upper)
    ModelSerializer.save(
        ma_model,
        models_dir,
        "moving_average",
        {"model_type": "MovingAverageForecaster", "window": 7, "train_records": len(train_df)},
    )

    # 4. Train Regularized Ridge Regression Forecaster
    logger.info("Fitting Regularized Ridge regression forecaster with validation calibration...")
    ridge_model = RegularizedRegressionForecaster()
    ridge_model.fit(train_df, val_df)
    ridge_pred, ridge_lower, ridge_upper = ridge_model.predict(val_df)
    val_results["Ridge_Regression"] = evaluate_forecast(y_val, ridge_pred, ridge_lower, ridge_upper)
    ModelSerializer.save(
        ridge_model,
        models_dir,
        "ridge_regression",
        {
            "model_type": "RegularizedRegressionForecaster",
            "best_alpha": float(ridge_model.model.alpha_),
            "train_records": len(train_df),
        },
    )

    # 5. Train XGBoost Forecaster (Tuned strictly on validation fold)
    logger.info("Tuning and fitting XGBoost demand forecaster...")
    xgb_model = XGBoostDemandForecaster()
    xgb_model.tune_and_fit(train_df, val_df)
    xgb_pred, xgb_lower, xgb_upper = xgb_model.predict(val_df)
    val_results["XGBoost"] = evaluate_forecast(y_val, xgb_pred, xgb_lower, xgb_upper)
    ModelSerializer.save(
        xgb_model,
        models_dir,
        "xgboost_demand",
        {
            "model_type": "XGBoostDemandForecaster",
            "best_params": xgb_model.best_params_,
            "train_records": len(train_df),
        },
    )

    # Save validation metrics
    val_metrics_file = metrics_dir / "validation_summary.json"
    with val_metrics_file.open("w", encoding="utf-8") as f:
        json.dump(val_results, f, indent=2)

    logger.info("Validation fold results summary:")
    for m_name, m_dict in val_results.items():
        logger.info(
            "[%s] MAE=%.3f, RMSE=%.3f, WAPE=%.3f, Coverage=%.3f, MPIW=%.3f",
            m_name,
            m_dict["MAE"],
            m_dict["RMSE"],
            m_dict["WAPE"],
            m_dict.get("interval_coverage", 0.0),
            m_dict.get("mean_interval_width", 0.0),
        )
    logger.info("Model training pipeline finished successfully.")


if __name__ == "__main__":
    main()
