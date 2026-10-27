"""Executable script to generate deterministic synthetic medical supply data and features."""

import argparse
from pathlib import Path

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES, AegisConfig
from aegis.data.generator import DeterministicSyntheticGenerator
from aegis.data.preprocessor import LeakageSafePreprocessor
from aegis.data.provenance import ProvenanceRegistry
from aegis.data.schema import DailyDemandRecord
from aegis.features.engineer import FeatureEngineer
from aegis.utils.logging import setup_logger

logger = setup_logger("aegis.generate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AEGIS Synthetic Data Generation Engine")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic PRNG seed")
    parser.add_argument("--days", type=int, default=365, help="Simulation duration in days")
    parser.add_argument(
        "--start-date", type=str, default="2025-01-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="baseline",
        choices=["baseline", "outbreak_surge", "supply_disruption"],
        help="Simulation scenario",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/synthetic_consumables.parquet",
        help="Path for raw generated parquet file",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/raw/manifest.json",
        help="Path for raw dataset manifest",
    )
    parser.add_argument(
        "--featured-output",
        type=str,
        default="data/processed/featured_dataset.parquet",
        help="Path for processed featured parquet file",
    )
    parser.add_argument(
        "--featured-manifest",
        type=str,
        default="data/processed/manifest.json",
        help="Path for processed dataset manifest",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(
        "Initializing synthetic simulation: seed=%d, days=%d, scenario=%s",
        args.seed,
        args.days,
        args.scenario,
    )

    config = AegisConfig(
        seed=args.seed,
        start_date=args.start_date,
        simulation_days=args.days,
    )

    # 1. Generate Raw Data
    generator = DeterministicSyntheticGenerator(config=config)
    df_raw = generator.generate(scenario=args.scenario)
    logger.info(
        "Generated %d synthetic daily records across %d hospitals and %d categories",
        len(df_raw),
        len(HOSPITALS),
        len(PRODUCT_CATEGORIES),
    )

    # 2. Schema Validation on Sample
    sample_records = df_raw.head(50).to_dict(orient="records")
    for r in sample_records:
        DailyDemandRecord(**r)
    logger.info("Schema validation successfully confirmed on data sample.")

    # 3. Save Raw Parquet and Manifest
    raw_path = Path(args.output)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    df_raw.to_parquet(raw_path, index=False)
    logger.info("Saved raw dataset to %s", raw_path)

    raw_manifest = ProvenanceRegistry.create_manifest(
        dataset_name="aegis_synthetic_consumables_raw",
        version="1.0.0",
        seed=args.seed,
        row_count=len(df_raw),
        date_range=[str(df_raw["date"].min()), str(df_raw["date"].max())],
        file_path=raw_path,
        hospitals=[h.hospital_id for h in HOSPITALS],
        warehouses=[w.warehouse_id for w in WAREHOUSES],
        categories=[c.category_id for c in PRODUCT_CATEGORIES],
    )
    ProvenanceRegistry.save_manifest(raw_manifest, args.manifest)
    logger.info("Saved raw dataset manifest to %s", args.manifest)

    # 4. Leakage-safe Preprocessing and Imputation
    df_clean = LeakageSafePreprocessor.clean_and_impute(df_raw)

    # 5. Leakage-Safe Feature Engineering
    engineer = FeatureEngineer()
    df_featured = engineer.generate_features(df_clean)
    logger.info(
        "Constructed %d features across %d rows", df_featured.shape[1], df_featured.shape[0]
    )

    # 6. Save Processed Parquet and Manifest
    feat_path = Path(args.featured_output)
    feat_path.parent.mkdir(parents=True, exist_ok=True)
    df_featured.to_parquet(feat_path, index=False)
    logger.info("Saved processed featured dataset to %s", feat_path)

    feat_manifest = ProvenanceRegistry.create_manifest(
        dataset_name="aegis_featured_consumables_processed",
        version="1.0.0",
        seed=args.seed,
        row_count=len(df_featured),
        date_range=[str(df_featured["date"].min()), str(df_featured["date"].max())],
        file_path=feat_path,
        hospitals=[h.hospital_id for h in HOSPITALS],
        warehouses=[w.warehouse_id for w in WAREHOUSES],
        categories=[c.category_id for c in PRODUCT_CATEGORIES],
    )
    ProvenanceRegistry.save_manifest(feat_manifest, args.featured_manifest)
    logger.info("Saved featured dataset manifest to %s", args.featured_manifest)
    logger.info("Data generation and feature engineering completed successfully.")


if __name__ == "__main__":
    main()
