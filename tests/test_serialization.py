"""Unit tests for model artifact persistence and deserialization."""

from pathlib import Path

import numpy as np
import pandas as pd

from aegis.models.baselines import SeasonalNaiveForecaster
from aegis.models.serialization import ModelSerializer


def test_model_serialization_roundtrip(tmp_path: Path, sample_featured_df: pd.DataFrame) -> None:
    """Test saving and loading a trained forecaster preserves exact numerical outputs."""
    forecaster = SeasonalNaiveForecaster(season_length=7)
    forecaster.fit(sample_featured_df)

    preds_orig, ql_orig, qu_orig = forecaster.predict(sample_featured_df)

    # Save artifact
    meta = {"experiment": "test_roundtrip", "records": len(sample_featured_df)}
    artifact_path = ModelSerializer.save(
        forecaster,
        output_dir=tmp_path,
        model_name="test_seasonal_naive",
        metadata=meta,
    )
    assert artifact_path.exists()
    assert (tmp_path / "test_seasonal_naive_metadata.json").exists()

    # Load artifact
    loaded_model, loaded_meta = ModelSerializer.load(artifact_path)
    assert loaded_meta["experiment"] == "test_roundtrip"

    preds_loaded, ql_loaded, qu_loaded = loaded_model.predict(sample_featured_df)

    np.testing.assert_allclose(preds_orig, preds_loaded, rtol=1e-6)
    np.testing.assert_allclose(ql_orig, ql_loaded, rtol=1e-6)
    np.testing.assert_allclose(qu_orig, qu_loaded, rtol=1e-6)
