"""Uncertainty scenario generator integrating XGBoost quantile forecasts."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aegis.models.regressor import XGBoostDemandForecaster
from aegis.models.serialization import ModelSerializer


@dataclass
class DemandScenario:
    """A discrete demand scenario with an associated subjective or empirical probability."""

    name: str
    probability: float
    demands: dict[tuple[str, str], float]  # (hospital_id, category_id) -> demand_units


@dataclass
class ScenarioSet:
    """Collection of optimization scenarios alongside out-of-sample ground truth."""

    target_date: str
    point_forecast: dict[tuple[str, str], float]
    lower_bound: dict[tuple[str, str], float]
    upper_bound: dict[tuple[str, str], float]
    scenarios: list[DemandScenario]
    realized_demand: dict[
        tuple[str, str], float
    ]  # Strict out-of-sample realization for evaluation only

    @property
    def num_scenarios(self) -> int:
        return len(self.scenarios)

    def get_expected_demands(self) -> dict[tuple[str, str], float]:
        """Compute probability-weighted expected demand across all scenarios."""
        expected: dict[tuple[str, str], float] = {}
        for sc in self.scenarios:
            for key, val in sc.demands.items():
                expected[key] = expected.get(key, 0.0) + sc.probability * val
        return {k: round(v, 2) for k, v in expected.items()}


class ForecastScenarioGenerator:
    """Constructs calibrated uncertainty scenarios using trained XGBoost quantile forecaster."""

    def __init__(
        self,
        model_path: str | Path = "models/xgboost_demand.joblib",
        data_path: str | Path = "data/processed/featured_dataset.parquet",
    ) -> None:
        self.model_path = Path(model_path)
        self.data_path = Path(data_path)
        self.model: XGBoostDemandForecaster | None = None
        self.metadata: dict[str, Any] = {}
        self.df_featured: pd.DataFrame | None = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load serialized model and featured dataset."""
        if self.model_path.exists():
            self.model, self.metadata = ModelSerializer.load(self.model_path)
        if self.data_path.exists():
            self.df_featured = pd.read_parquet(self.data_path)

    def generate_scenario_set(
        self,
        target_date: str | date = "2025-11-15",
        num_scenarios: int = 5,
        seed: int = 42,
        surge_multiplier: float = 1.0,
    ) -> ScenarioSet:
        """Generate point forecasts, quantile intervals, and discrete demand scenarios.

        Parameters
        ----------
        target_date : str | date
            Observation date from held-out test split (>= 2025-11-07).
        num_scenarios : int
            Number of stochastic scenarios to construct (default 5).
        seed : int
            PRNG seed for reproducible scenario generation.
        surge_multiplier : float
            Stress-test demand scaling factor (default 1.0).

        Returns
        -------
        ScenarioSet
            Calibrated demand scenarios with out-of-sample realized demand.
        """
        if self.df_featured is None or self.model is None:
            raise RuntimeError("Model or dataset not loaded.")

        target_dt = pd.to_datetime(target_date).date()
        date_mask = pd.to_datetime(self.df_featured["date"]).dt.date == target_dt
        df_target = self.df_featured[date_mask].copy()

        if df_target.empty:
            raise ValueError(f"No records found for date {target_date} in {self.data_path}")

        # 1. Generate model point forecast and prediction intervals
        preds, q_lower, q_upper = self.model.predict(df_target)

        point_dict: dict[tuple[str, str], float] = {}
        lower_dict: dict[tuple[str, str], float] = {}
        upper_dict: dict[tuple[str, str], float] = {}
        realized_dict: dict[tuple[str, str], float] = {}

        df_target_reset = df_target.reset_index(drop=True)
        for idx, row in df_target_reset.iterrows():
            key = (str(row["hospital_id"]), str(row["category_id"]))
            p = max(1.0, float(preds[idx]) * surge_multiplier)
            ql = max(0.5, float(q_lower[idx]) * surge_multiplier)
            qu = max(p, float(q_upper[idx]) * surge_multiplier)
            actual = float(row["demand_units"]) * surge_multiplier

            point_dict[key] = round(p, 2)
            lower_dict[key] = round(ql, 2)
            upper_dict[key] = round(qu, 2)
            realized_dict[key] = round(actual, 2)

        # 2. Build structured scenarios
        rng = np.random.default_rng(seed)
        scenarios: list[DemandScenario] = []

        if num_scenarios == 1:
            # Deterministic scenario: Point forecast
            scenarios.append(
                DemandScenario(
                    name="expected_point",
                    probability=1.0,
                    demands=point_dict.copy(),
                )
            )
        elif num_scenarios == 3:
            # Three-point distribution: Baseline (50%), Lower (25%), Upper (25%)
            scenarios.append(DemandScenario("baseline_p50", 0.50, point_dict.copy()))
            scenarios.append(DemandScenario("lower_p10", 0.25, lower_dict.copy()))
            scenarios.append(DemandScenario("upper_p90", 0.25, upper_dict.copy()))
        else:
            # Multi-scenario stochastic set (e.g. 5 scenarios):
            # Baseline, Upper surge, Lower lull, and 2 intermediate stochastic draws
            weights = np.array([0.35, 0.25, 0.15, 0.15, 0.10][:num_scenarios])
            weights = weights / weights.sum()

            scenarios.append(
                DemandScenario("baseline_median", float(weights[0]), point_dict.copy())
            )
            scenarios.append(DemandScenario("surge_p90", float(weights[1]), upper_dict.copy()))
            scenarios.append(DemandScenario("lull_p10", float(weights[2]), lower_dict.copy()))

            for s_idx in range(3, num_scenarios):
                sampled_demands: dict[tuple[str, str], float] = {}
                for key in point_dict:
                    mu = point_dict[key]
                    # Sigma estimated from 80% interval width: (q90 - q10) / (2 * 1.28)
                    sigma = max(2.0, (upper_dict[key] - lower_dict[key]) / 2.56)
                    val = max(1.0, rng.normal(loc=mu, scale=sigma))
                    sampled_demands[key] = round(float(val), 2)

                scenarios.append(
                    DemandScenario(
                        name=f"stochastic_sample_{s_idx - 2}",
                        probability=float(weights[s_idx]),
                        demands=sampled_demands,
                    )
                )

        return ScenarioSet(
            target_date=str(target_dt),
            point_forecast=point_dict,
            lower_bound=lower_dict,
            upper_bound=upper_dict,
            scenarios=scenarios,
            realized_demand=realized_dict,
        )
