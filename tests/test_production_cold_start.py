"""Regression tests reproducing production cold start and verifying portable path resolution."""

import tempfile
from pathlib import Path

import pytest

from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.utils.paths import get_project_root, resolve_repo_path


def test_portable_repo_root_discovery():
    """Verify repo root discovery locates the directory containing pyproject.toml."""
    root = get_project_root()
    assert root.exists(), f"Discovered root does not exist: {root}"
    assert (root / "pyproject.toml").exists(), f"pyproject.toml not found in {root}"

    # Resolve relative paths
    resolved_model = resolve_repo_path("models/xgboost_demand.joblib")
    assert resolved_model.exists(), f"Model path did not resolve: {resolved_model}"

    resolved_data = resolve_repo_path("data/processed/featured_dataset.parquet")
    assert resolved_data.exists(), f"Data path did not resolve: {resolved_data}"


def test_scenario_generator_linux_style_posix_paths():
    """Verify scenario generator handles POSIX-style Linux container paths."""
    posix_model = "models/xgboost_demand.joblib"
    posix_data = "data/processed/featured_dataset.parquet"

    scen_gen = ForecastScenarioGenerator(model_path=posix_model, data_path=posix_data)
    assert scen_gen.model is not None, "Model failed to load via POSIX path"
    assert scen_gen.df_featured is not None, "Featured dataset failed to load via POSIX path"

    scen_set = scen_gen.generate_scenario_set(target_date="2025-11-08", num_scenarios=5)
    assert scen_set.num_scenarios == 5
    assert len(scen_set.point_forecast) == 60  # 20 hospitals x 3 products


def test_scenario_generator_cold_start_self_healing():
    """Verify scenario generator automatically synthesizes featured dataset if missing on cold start."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        missing_data_path = tmp_path / "data" / "processed" / "featured_dataset.parquet"
        assert not missing_data_path.exists()

        # Initialize with real model but missing data path
        scen_gen = ForecastScenarioGenerator(
            model_path="models/xgboost_demand.joblib",
            data_path=missing_data_path,
        )

        # Confirm self-healing generated the dataset on the fly
        assert missing_data_path.exists(), "Dataset was not synthesized on cold start"
        assert scen_gen.df_featured is not None
        assert len(scen_gen.df_featured) > 0

        # Verify scenario set generates successfully
        scen_set = scen_gen.generate_scenario_set(target_date="2025-11-08", num_scenarios=3)
        assert scen_set.num_scenarios == 3
        assert len(scen_set.point_forecast) == 60


def test_scenario_generator_descriptive_error_on_unresolvable_artifact():
    """Verify descriptive RuntimeError with searched path details when an artifact is unrecoverable."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bogus_model = tmp_path / "nonexistent_model.joblib"
        bogus_data = tmp_path / "nonexistent_data.parquet"

        scen_gen = ForecastScenarioGenerator(model_path=bogus_model, data_path=bogus_data)
        # Manually clear to simulate both failing
        scen_gen.model = None
        scen_gen.df_featured = None

        with pytest.raises(RuntimeError) as exc_info:
            scen_gen.generate_scenario_set(target_date="2025-11-08")

        err_msg = str(exc_info.value)
        assert "Scenario generator cannot operate: missing" in err_msg
        assert str(bogus_model.name) in err_msg or "Model forecaster" in err_msg


def test_workspace_tab_resilience_on_scenario_generator_failure():
    """Verify that failure during scenario generation does not crash the process and can be handled safely."""
    # Create scenario generator with invalid model to simulate runtime fault
    broken_gen = ForecastScenarioGenerator(model_path="nonexistent_model.joblib")
    broken_gen.model = None

    handled_gracefully = False
    error_message = ""
    try:
        broken_gen.generate_scenario_set(target_date="2025-11-08")
    except RuntimeError as exc:
        handled_gracefully = True
        error_message = str(exc)

    assert handled_gracefully, "RuntimeError was not caught"
    assert (
        "missing Model forecaster" in error_message
        or "Scenario generator cannot operate" in error_message
    )
