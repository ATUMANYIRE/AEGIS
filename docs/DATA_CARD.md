# AEGIS Data Card: Synthetic Medical Consumable Supply Benchmark

**Dataset Name:** AEGIS Multi-Facility Medical Consumable Panel  
**Version:** 1.0.0  
**Scope:** Milestone 1 (Foundation, Data Engineering, Forecasting and Scientific Validation)  
**Target:** Non-patient-specific medical consumable demand forecasting  

---

## 1. Motivation & Context

In healthcare supply chain logistics, hospital facilities experience complex non-stationary demand patterns driven by annual infection waves, weekly elective surgical schedules, sudden disease surges, and delivery disruptions. Forecasting non-patient-specific consumables (e.g., examination gloves, disinfectant wipe canisters, sharps disposal boxes) is critical to prevent stockouts while avoiding excessive stockpiling costs.

The AEGIS benchmark was developed for DATANOVA 2026 to provide a transparent, reproducible, and leakage-safe testbed for multi-facility forecasting algorithms before coupling with multi-echelon Mixed-Integer Linear Programming (MILP) inventory optimization.

---

## 2. Dataset Composition & Topology

The dataset comprises daily longitudinal observations across a simulated regional health authority network:

- **Simulation Horizon:** 365 consecutive days (January 1, 2025 to December 31, 2025).
- **Hospitals ($N = 20$):**
  - **Level 1 Trauma Centers ($n = 4$):** H01–H04 (bed capacities 580–850). High base consumption, trauma volatility, high surge sensitivity.
  - **Regional Referral Centers ($n = 6$):** H05–H10 (bed capacities 340–480). Moderate-high consumption, regional hubs.
  - **Community Hospitals ($n = 7$):** H11–H17 (bed capacities 150–260). Stable baseline demand, lower variance.
  - **Specialty & Ambulatory Clinics ($n = 3$):** H18–H20 (bed capacities 90–120). Procedural consumption, strong weekend dips.
- **Regional Warehouses ($M = 3$):**
  - **W01:** Central Logistics Center (Capacity 150,000 units).
  - **W02:** Northern Regional Depot (Capacity 80,000 units).
  - **W03:** Southern Regional Depot (Capacity 80,000 units).
- **Consumable Product Categories ($C = 3$):**
  - **PPE:** Personal Protective Equipment (gloves, surgical masks, gowns). Winter surge multiplier: $1.45\times$, weekend ratio: $0.75\times$.
  - **Sanitation:** Surface disinfectants and autoclave supplies. Winter surge multiplier: $1.30\times$, weekend ratio: $0.70\times$.
  - **Medical_Utility:** Sharps containers, biohazard liners, utility gauze. Winter surge multiplier: $1.15\times$, weekend ratio: $0.80\times$.
- **Total Record Count:** $20 \times 3 \times 365 = 21,900$ daily panel observations.

---

## 3. Data Schema & Field Definitions

All records conform strictly to the Pydantic `DailyDemandRecord` schema:

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `date` | Date | YYYY-MM-DD | Daily observation timestamp |
| `hospital_id` | String | Regex `^H(0[1-9]\|1[0-9]\|20)$` | Unique hospital facility identifier |
| `warehouse_id` | String | Regex `^W0[1-3]$` | Assigned regional fulfillment warehouse |
| `category_id` | String | Enum `[PPE, Sanitation, Medical_Utility]` | Medical consumable category |
| `demand_units` | Float | $\ge 0.0$ | **Target variable**: True unconstrained demand |
| `observed_consumption_units` | Float | $\ge 0.0$ | Consumption recorded (constrained by stockouts) |
| `reported_inventory_units` | Float | $\ge 0.0$ | On-hand inventory at end of day |
| `stockout_flag` | Integer | $\{0, 1\}$ | Indicator of supply exhaustion ($1$ if stockout) |
| `surge_factor` | Float | $\ge 1.0$ | Surge intensity multiplier |
| `lead_time_days` | Integer | $[1, 14]$ | Transport lead time from warehouse to facility |
| `is_synthetic` | Boolean | Must be `True` | Flag verifying synthetic origin |
| `synthetic_scenario` | String | e.g. `baseline` | Simulation scenario parameterization |
| `missing_report_flag` | Integer | $\{0, 1\}$ | Telemetry / sensor transmission dropout indicator |

---

## 4. Generative Dynamics & Physical Realism

The generator incorporates five coupled physical mechanisms:

1. **Facility Scale & Tier Sizing:** Baseline demand scales with hospital bed capacity and tier multiplier $\mu = \text{Beds} \times \text{Rate} \times \text{TierMult}$.
2. **Dual Seasonality:**
   - *Annual:* Sinusoidal winter respiratory surge peaking in mid-January.
   - *Weekly:* Healthcare operational rhythm (routine elective drops on weekends).
3. **Surge Phenomena:** Stochastic Poisson arrival of localized disease outbreaks or mass casualty drills, producing multi-day surge multipliers.
4. **Supply Chain Delay & Stockouts:** Multi-day transport lead times and facility inventory exhaustion. When local inventory is exhausted, `observed_consumption_units` drops to zero or available stock, capturing right-censored latent demand.
5. **Sensor Missingness:** Telemetry dropouts (~3% rate) simulating barcode scanning and EDI failures.

---

## 5. Provenance, Licensing & Ethical Integrity

- **Provenance Statement:** Generated deterministically via AEGIS Generator Engine v1.0.0.
- **Public Data Integrity:** In accordance with rigorous scientific protocol, no unverified public health datasets or private HIPAA/EHR records were claimed or merged into this benchmark. All statistical patterns are generative.
- **No Medical Claim:** This dataset is designed exclusively for algorithmic benchmarking and supply chain decision-support research. It is **not** validated for actual patient treatment, clinical prescription, or hospital administration.
