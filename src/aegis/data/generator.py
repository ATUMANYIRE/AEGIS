"""Deterministic synthetic medical consumable demand and supply chain generator."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, AegisConfig


class DeterministicSyntheticGenerator:
    """Synthetic medical consumable demand and inventory telemetry generator.

    Produces realistic daily time-series data for multi-hospital healthcare networks
    with explicit deterministic random seeds.
    """

    def __init__(self, config: AegisConfig | None = None) -> None:
        self.config = config or AegisConfig()

    def generate(self, scenario: str = "baseline") -> pd.DataFrame:
        """Generate full synthetic dataset across all hospitals, categories, and days.

        Parameters
        ----------
        scenario : str
            Scenario identifier: 'baseline', 'outbreak_surge', or 'supply_disruption'.

        Returns
        -------
        pd.DataFrame
            Simulated daily panel data.
        """
        rng = np.random.default_rng(self.config.seed)
        start_dt = datetime.strptime(self.config.start_date, "%Y-%m-%d").date()
        days = self.config.simulation_days

        # Scenario tuning parameters
        surge_prob_mult = 1.0
        lead_time_delay_mult = 1.0
        stock_buffer_mult = 1.0

        if scenario == "outbreak_surge":
            surge_prob_mult = 2.5
        elif scenario == "supply_disruption":
            lead_time_delay_mult = 2.5
            stock_buffer_mult = 0.5

        records = []

        # Generate per hospital and category to simulate coupled inventory and demand
        for h in HOSPITALS:
            for c in PRODUCT_CATEGORIES:
                # Facility & category baseline demand scale
                base_daily = h.bed_capacity * c.base_daily_demand_per_bed * h.base_demand_multiplier

                # Initial safety stock at facility (approx 4-6 days baseline demand)
                initial_stock = base_daily * 5.0 * stock_buffer_mult
                current_inventory = initial_stock

                # Pipeline of in-transit orders: list of (arrival_day, order_quantity)
                in_transit_orders: list[tuple[int, float]] = []

                # Active surge tracker: remaining days and multiplier
                surge_remaining_days = 0
                current_surge_factor = 1.0

                for day_idx in range(days):
                    current_date = start_dt + timedelta(days=day_idx)
                    day_of_year = current_date.timetuple().tm_yday
                    is_weekend = current_date.weekday() >= 5

                    # 1. Annual seasonality (sinusoidal, peaking in mid-January winter respiratory wave)
                    # Phase offset: Day 20 is winter peak
                    annual_phase = 2.0 * np.pi * (day_of_year - 20) / 365.25
                    annual_seasonal_mult = 1.0 + (c.winter_surge_multiplier - 1.0) * (
                        0.5 * (1.0 + np.cos(annual_phase))
                    )

                    # 2. Day-of-week seasonality (routine elective dip on weekends)
                    if is_weekend:
                        weekly_mult = c.weekend_ratio
                    else:
                        # Normalize weekday so 7-day average remains ~1.0
                        weekly_mult = 1.0 + (1.0 - c.weekend_ratio) * (2.0 / 5.0)

                    # 3. Dynamic surge events (outbreaks, mass casualty, or inspection drills)
                    if surge_remaining_days > 0:
                        surge_remaining_days -= 1
                    else:
                        p_surge = self.config.surge_probability * surge_prob_mult
                        if rng.random() < p_surge:
                            # Surge lasts 2 to 6 days
                            surge_remaining_days = int(rng.integers(2, 7))
                            current_surge_factor = float(
                                rng.uniform(1.25, 2.10) * h.surge_sensitivity
                            )
                        else:
                            current_surge_factor = 1.0

                    # 4. Stochastic daily noise (log-normal with small dispersion)
                    stochastic_noise = float(rng.lognormal(mean=-0.005, sigma=0.09))

                    # Calculate latent true unconstrained demand
                    latent_demand = (
                        base_daily
                        * annual_seasonal_mult
                        * weekly_mult
                        * current_surge_factor
                        * stochastic_noise
                    )
                    demand_units = round(max(1.0, latent_demand), 2)

                    # 5. Process arriving shipments
                    arrived_qty = 0.0
                    new_in_transit = []
                    for arr_day, qty in in_transit_orders:
                        if arr_day <= day_idx:
                            arrived_qty += qty
                        else:
                            new_in_transit.append((arr_day, qty))
                    in_transit_orders = new_in_transit
                    current_inventory += arrived_qty

                    # 6. Check stockout and observe consumption
                    if current_inventory >= demand_units:
                        observed_consumption = demand_units
                        current_inventory -= demand_units
                        stockout_flag = 0
                    else:
                        # Stockout occurs: demand is truncated
                        observed_consumption = round(max(0.0, current_inventory), 2)
                        current_inventory = 0.0
                        stockout_flag = 1

                    reported_inventory = round(current_inventory, 2)

                    # 7. Replenishment logic & transport lead time
                    # Facility orders replenishment to maintain safety stock target
                    target_stock = base_daily * 4.5 * stock_buffer_mult
                    if current_inventory < target_stock:
                        reorder_qty = round(target_stock * 1.25, 2)
                        # Lead time: base lead time + random congestion/weather delay
                        delay_prob = 0.15 * lead_time_delay_mult
                        extra_delay = 0
                        r = rng.random()
                        if r < delay_prob * 0.7:
                            extra_delay = 1
                        elif r < delay_prob:
                            extra_delay = 2

                        lead_time = h.base_lead_time_days + c.lead_time_buffer_days + extra_delay
                        arrival_day = day_idx + lead_time
                        in_transit_orders.append((arrival_day, reorder_qty))
                    else:
                        lead_time = h.base_lead_time_days + c.lead_time_buffer_days

                    # 8. Missingness simulation (telemetry drops, barcode scanner failures)
                    missing_report = 1 if rng.random() < self.config.missingness_rate else 0

                    records.append(
                        {
                            "date": current_date.isoformat(),
                            "hospital_id": h.hospital_id,
                            "warehouse_id": h.assigned_warehouse_id,
                            "category_id": c.category_id,
                            "demand_units": demand_units,
                            "observed_consumption_units": observed_consumption,
                            "reported_inventory_units": reported_inventory,
                            "stockout_flag": stockout_flag,
                            "surge_factor": round(current_surge_factor, 3),
                            "lead_time_days": int(lead_time),
                            "is_synthetic": True,
                            "synthetic_scenario": scenario,
                            "missing_report_flag": missing_report,
                        }
                    )

        df = pd.DataFrame(records)

        # Sort chronologically by date and facility/category
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.sort_values(by=["date", "hospital_id", "category_id"]).reset_index(drop=True)
        return df
