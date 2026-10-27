# AEGIS — Adaptive Emergency Governance & Intelligent Supply

**Milestone 1: Foundation, Data Engineering, Forecasting and Scientific Validation**

AEGIS is a decision-intelligence platform designed for multi-facility healthcare supply chain networks. Milestone 1 establishes the scientific foundation: a deterministic, physically grounded synthetic demand generator, leakage-safe time-series feature engineering, and a benchmark forecasting suite comparing non-parametric baselines against regularized regression and gradient boosted decision trees with prediction intervals.

---

## 1. Network Topology & Scope

The simulated supply chain network models:
- **20 Hospitals ($H01$ to $H20$):** Spanning 4 operational tiers (Level 1 Trauma Centers, Regional Referral Centers, Community Hospitals, and Specialty Clinics) with capacities ranging from 90 to 850 beds.
- **3 Regional Fulfillment Warehouses ($W01$ to $W03$):** Central Logistics Center, Northern Depot, and Southern Depot.
- **3 Non-Patient-Specific Medical Consumable Categories:**
  1. `PPE`: Personal Protective Equipment (examination gloves, surgical masks, isolation gowns).
  2. `Sanitation`: Surface disinfectants, biocidal wipes, autoclave supplies.
  3. `Medical_Utility`: Sharps containers, biohazard disposal liners, utility gauze.
- **Time Horizon:** 365 daily observations ($20 \times 3 \times 365 = 21,900$ panel records).

---

## 2. Environment Prerequisites

- **Operating System:** Windows 11
- **Python Version:** CPython 3.11
- **Package & Environment Manager:** `uv` (Fast Python package installer)

---

## 3. Windows PowerShell Setup & Run Commands

Execute the following commands in **PowerShell**:

### Step 1: Environment Setup
```powershell
# Create Python 3.11 virtual environment
uv venv --python 3.11

# Activate virtual environment
.venv\Scripts\activate

# Install all dependencies and editable package
uv sync --dev
```

### Step 2: Code Quality & Unit Tests
```powershell
# Run Ruff linting
uv run ruff check .

# Run test suite with strict markers
uv run pytest -v tests/
```

### Step 3: Pipeline Execution
```powershell
# 1. Deterministic Data Generation & Leakage-Safe Feature Extraction
uv run python scripts/generate_data.py --seed 42 --days 365 --scenario baseline

# 2. Train Baselines, Ridge, and XGBoost with Development-Fold Tuning
uv run python scripts/train.py --config configs/train_config.json

# 3. Scientific Evaluation on Held-Out Test Data
uv run python scripts/evaluate.py --config configs/evaluate_config.json
```

---

## 4. Forecasting Architectures & Interval Estimation

AEGIS benchmarks four models:

1. **Seasonal-Naive Forecaster:** $\hat{y}_t = y_{t-7}$ exploiting the 7-day hospital operating rhythm.
2. **Moving-Average Forecaster:** 7-day shifted rolling average ($\text{shift}(1)$).
3. **Regularized Ridge Regression:** Linear model with standard scaling and one-hot encoding fit strictly on training data. Calibrated with Split Conformal Prediction.
4. **XGBoost Demand Forecaster:** GBDT tuned on the development fold. Produces point predictions alongside 10th and 90th percentile bounds via dedicated quantile loss (`reg:quantileerror`).

### Scientific Evaluation Metrics
- **Point Accuracy:** Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and Weighted Absolute Percentage Error (WAPE).
- **Interval Reliability:** Empirical Prediction Interval Coverage (nominal target: 80%), Mean Prediction Interval Width (MPIW), and Pinball / Quantile Loss ($p_{10}$, $p_{50}$, $p_{90}$).
- **Segmented Reporting:** Machine-readable breakdowns per facility (`metrics/per_facility_metrics.csv`) and per product category (`metrics/per_product_metrics.csv`).

---

## 5. Temporal Leakage Prevention Protocol

Time-series observations strictly forbid random splitting. AEGIS enforces:
1. **Chronological Splitting:**
   - **Training Set:** Days 1 to 260 (~8.5 months).
   - **Validation Set (Development):** Days 261 to 310 (~50 days). Used exclusively for hyperparameter tuning and conformal calibration.
   - **Held-Out Test Set:** Days 311 to 365 (~55 days). Completely isolated until final evaluation.
2. **Shifted Rolling Aggregations:** All rolling calculations first apply `shift(1)`, guaranteeing that observation $t$ is mathematically excluded from feature vectors for time $t$.
3. **Imputation Directionality:** Missing telemetry values are forward-filled (`ffill`). Backward-filling (`bfill`) and global full-dataset statistics are prohibited.

---

## 6. Provenance & Cryptographic Auditing

- All generated datasets produce companion `manifest.json` files documenting the exact random seed, scenario parameters, and SHA-256 cryptographic hashes.
- **Genuine Public Data Disclosure:** In strict accordance with scientific integrity guidelines, Milestone 1 operates solely on a parameterized synthetic benchmark. No unverified external public or EHR health records are falsely claimed.

---

## 7. Known Limitations & Caveats

1. **Synthetic Data Generalizability:** Although the generator captures structural dynamics (dual seasonality, Poisson surges, stockout right-censoring, and transport delays), synthetic distributions cannot foresee external geopolitical embargoes, vendor price volatility, or abrupt hospital administrative protocol shifts.
2. **Clinical Disclaimer:** AEGIS forecasts supply unit consumption for logistical supply chain management. It does **not** provide patient-specific clinical recommendations, drug dosages, or medical triage advice.
3. **Honest Reporting Guarantee:** If non-parametric baselines outperform complex models under stable operational periods, those results are reported transparently without artificial adjustments.
