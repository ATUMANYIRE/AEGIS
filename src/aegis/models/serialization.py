"""Serialization and persistence utilities for AEGIS forecasting models."""

import json
from pathlib import Path
from typing import Any

import joblib


class ModelSerializer:
    """Safely serializes and restores model artifacts and metadata."""

    @staticmethod
    def save(
        model: Any,
        output_dir: str | Path,
        model_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Persist model artifact and companion JSON metadata.

        Parameters
        ----------
        model : Any
            Fitted forecaster instance.
        output_dir : str | Path
            Target directory.
        model_name : str
            Base identifier (e.g., 'xgboost_baseline' or 'ridge_baseline').
        metadata : dict[str, Any] | None, optional
            Model hyperparameters and dataset context.

        Returns
        -------
        Path
            Path to saved model file.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        model_file = out_path / f"{model_name}.joblib"
        meta_file = out_path / f"{model_name}_metadata.json"

        # Save binary artifact
        joblib.dump(model, model_file, compress=3)

        # Save metadata
        meta = metadata or {}
        meta["model_name"] = model_name
        meta["artifact_file"] = model_file.name
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return model_file

    @staticmethod
    def load(model_path: str | Path) -> tuple[Any, dict[str, Any]]:
        """Load model artifact and companion metadata.

        Returns (model, metadata_dict).
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at {path}")

        model = joblib.load(path)
        meta_path = path.with_name(f"{path.stem}_metadata.json")
        metadata = {}
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as f:
                metadata = json.load(f)

        return model, metadata
