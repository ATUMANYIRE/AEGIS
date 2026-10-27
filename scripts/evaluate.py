"""Evaluation pipeline evaluating models on held-out test data across facility and product segments."""

import argparse
import json
from pathlib import Path

import pandas as pd

from aegis.features.engineer import FeatureEngineer
from aegis.metrics.evaluation import evaluate_breakdowns, evaluate_forecast
from aegis.models.serialization import ModelSerializer
from aegis.utils.logging import setup_logger

logger = setup_logger("aegis.evaluate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AEGIS Forecasting Evaluation Engine")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to JSON evaluation config file",
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
        help="Directory containing trained model artifacts",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="metrics",
        help="Directory to save machine-readable evaluation metrics",
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
    logger.info("Loading dataset from %s", args.data)
    df = pd.read_parquet(args.data)

    # 1. Extract Held-Out Test Partition
    _, _, test_df = FeatureEngineer.chronological_split(
        df, train_end_date=args.train_end_date, val_end_date=args.val_end_date
    )
    logger.info(
        "Held-out Test Partition: %d records from %s to %s",
        len(test_df),
        test_df["date"].min(),
        test_df["date"].max(),
    )

    models_dir = Path(args.models_dir)
    metrics_dir = Path(args.metrics_dir)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    y_test = test_df["demand_units"].values

    models_to_eval = [
        ("Seasonal_Naive", "seasonal_naive.joblib"),
        ("Moving_Average", "moving_average.joblib"),
        ("Ridge_Regression", "ridge_regression.joblib"),
        ("XGBoost", "xgboost_demand.joblib"),
    ]

    evaluation_summary = {}
    facility_breakdowns = []
    product_breakdowns = []

    for model_name, artifact_filename in models_to_eval:
        artifact_path = models_dir / artifact_filename
        if not artifact_path.exists():
            logger.warning("Artifact %s not found in %s, skipping.", artifact_filename, models_dir)
            continue

        logger.info("Evaluating model: %s", model_name)
        model, _ = ModelSerializer.load(artifact_path)

        # Generate predictions
        preds, q_lower, q_upper = model.predict(test_df)

        # Overall metrics
        metrics = evaluate_forecast(y_test, preds, q_lower, q_upper)
        metrics["model_name"] = model_name
        metrics["test_records"] = len(test_df)
        evaluation_summary[model_name] = metrics

        # Add predictions to temporary df for breakdowns
        test_eval_df = test_df.copy()
        test_eval_df["y_pred"] = preds
        test_eval_df["q_lower"] = q_lower
        test_eval_df["q_upper"] = q_upper

        # Facility (Hospital) Breakdown
        hosp_metrics = evaluate_breakdowns(
            test_eval_df,
            y_true_col="demand_units",
            y_pred_col="y_pred",
            q_lower_col="q_lower",
            q_upper_col="q_upper",
            group_col="hospital_id",
        )
        hosp_metrics["model_name"] = model_name
        facility_breakdowns.append(hosp_metrics)

        # Product Category Breakdown
        prod_metrics = evaluate_breakdowns(
            test_eval_df,
            y_true_col="demand_units",
            y_pred_col="y_pred",
            q_lower_col="q_lower",
            q_upper_col="q_upper",
            group_col="category_id",
        )
        prod_metrics["model_name"] = model_name
        product_breakdowns.append(prod_metrics)

    # 2. Save Machine-Readable Metrics
    summary_path = metrics_dir / "evaluation_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(evaluation_summary, f, indent=2)
    logger.info("Saved evaluation summary to %s", summary_path)

    if facility_breakdowns:
        all_fac_df = pd.concat(facility_breakdowns, ignore_index=True)
        fac_path = metrics_dir / "per_facility_metrics.csv"
        all_fac_df.to_csv(fac_path, index=False)
        logger.info("Saved per-facility evaluation breakdown to %s", fac_path)

    if product_breakdowns:
        all_prod_df = pd.concat(product_breakdowns, ignore_index=True)
        prod_path = metrics_dir / "per_product_metrics.csv"
        all_prod_df.to_csv(prod_path, index=False)
        logger.info("Saved per-product evaluation breakdown to %s", prod_path)

    # 3. Print Scientific Evaluation Table
    print("\n" + "=" * 90)
    print("AEGIS MILESTONE 1 FORECASTING EVALUATION RESULTS (HELD-OUT TEST PARTITION)")
    print("=" * 90)
    header = f"{'Model':<18} | {'MAE':<8} | {'RMSE':<8} | {'WAPE':<8} | {'Coverage':<10} | {'MPIW':<8} | {'P10 Loss':<8} | {'P90 Loss':<8}"
    print(header)
    print("-" * 90)

    for m_name, m in evaluation_summary.items():
        print(
            f"{m_name:<18} | {m['MAE']:<8.3f} | {m['RMSE']:<8.3f} | {m['WAPE']:<8.3f} | "
            f"{m.get('interval_coverage', 0.0):<10.3f} | {m.get('mean_interval_width', 0.0):<8.3f} | "
            f"{m.get('pinball_loss_p10', 0.0):<8.3f} | {m.get('pinball_loss_p90', 0.0):<8.3f}"
        )
    print("=" * 90)

    # Model comparison note
    if "XGBoost" in evaluation_summary and "Seasonal_Naive" in evaluation_summary:
        xgb_mae = evaluation_summary["XGBoost"]["MAE"]
        sn_mae = evaluation_summary["Seasonal_Naive"]["MAE"]
        if xgb_mae < sn_mae:
            improvement = (sn_mae - xgb_mae) / sn_mae * 100
            logger.info(
                "XGBoost outperforms Seasonal-Naive by %.2f%% lower MAE on held-out test data.",
                improvement,
            )
        else:
            logger.info(
                "Honest reporting: Seasonal-Naive outperformed or matched XGBoost (SN MAE=%.3f, XGB MAE=%.3f).",
                sn_mae,
                xgb_mae,
            )

    logger.info("Evaluation completed successfully.")


if __name__ == "__main__":
    main()
