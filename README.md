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

---

## 8. Milestone 2: Multi-Echelon Uncertainty-Aware Optimization Engine

Milestone 2 operationalizes the probabilistic demand forecasts produced in Milestone 1 into mathematically optimal, operationally feasible supply allocations across 20 hospitals, 3 fulfillment warehouses, and 3 medical consumable categories.

### 8.1 Mathematical Programming Formulation (SciPy HiGHS MILP)

The core optimization engine implements a Mixed-Integer Linear Program (MILP) formulated and solved using the High Performance Mixed Integer Programming solver (`scipy.optimize.milp` HiGHS branch-and-cut / simplex dual).

#### Sets & Indices
- $w \in W = \{W01, W02, W03\}$: Regional fulfillment warehouses.
- $h \in H = \{H01, \dots, H20\}$: Hospitals across 4 operational tiers.
- $c \in C = \{PPE, Sanitation, Medical\_Utility\}$: Medical consumable categories.
- $k \in K$: Plausible demand scenarios ($k \in \{1, \dots, K\}$ with probabilities $p_k, \sum_k p_k = 1$).

#### Decision Variables
- $x_{w,h,c} \in \mathbb{Z}_{\ge 0}$: First-stage integer shipment quantity from warehouse $w$ to hospital $h$ for product $c$.
- $y_{w,h} \in \{0, 1\}$: Binary route activation variable (1 if route $w \to h$ is opened, 0 otherwise).
- $v_{w,h} \in \mathbb{Z}_{\ge 0}$: Integer vehicle dispatch count assigned to route $w \to h$.
- $s_{h,c,k} \ge 0$: Second-stage continuous unmet demand (recourse shortage) for hospital $h$, product $c$ under scenario $k$.

#### Objective Function
$$\min \sum_{w \in W} \sum_{h \in H} \left[ \sum_{c \in C} c_{w,h}^{\text{ship}} x_{w,h,c} + c_{w,h}^{\text{route}} y_{w,h} + c^{\text{veh}} v_{w,h} \right] + \sum_{k \in K} p_k \sum_{h \in H} \sum_{c \in C} \pi_{h,c}^{\text{short}} s_{h,c,k}$$

Where:
- $c_{w,h}^{\text{ship}} = 0.045 \cdot D_{w,h}$ (\$/unit transport cost over Euclidean distance with 1.25 road circuity).
- $c_{w,h}^{\text{route}} = 150 + 1.20 \cdot D_{w,h}$ (\$/dispatch fixed route activation fee).
- $c^{\text{veh}} = 200.0$ (\$/vehicle trip fee).
- $\pi_{h,c}^{\text{short}} = \text{base\_penalty}_c \times \text{tier\_weight}_h$ (clinical criticality penalty: Level 1 Trauma = 3.0×, Regional = 2.0×, Community = 1.2×, Specialty = 1.0×).

#### Hard Physical & Operational Constraints
1. **Warehouse Inventory Conservation:**
   $$\sum_{h \in H} x_{w,h,c} \le I_{w,c} \quad \forall w \in W, c \in C$$
2. **Warehouse Dispatch Throughput:**
   $$\sum_{h \in H} \sum_{c \in C} x_{w,h,c} \le Cap_w \quad \forall w \in W$$
3. **Vehicle Fleet Capacity & Route Activation:**
   $$\sum_{c \in C} x_{w,h,c} \le Q_{\text{veh}} \cdot v_{w,h} \quad \forall w \in W, h \in H$$
   $$v_{w,h} \le M \cdot y_{w,h} \quad \forall w \in W, h \in H \quad (M = \lceil \frac{\sum_c Cap_w}{Q_{\text{veh}}} \rceil)$$
4. **Demand Balance with Recourse:**
   $$\sum_{w \in W} x_{w,h,c} + s_{h,c,k} \ge d_{h,c}^{(k)} \quad \forall h \in H, c \in C, k \in K$$
5. **Configurable Minimum Service Coverage (Fairness Target):**
   $$\sum_{w \in W} x_{w,h,c} \ge \alpha_{\min} \cdot \bar{d}_{h,c} \quad \forall h \in H, c \in C$$

---

### 8.2 Infeasibility Detection & Fairness Relaxation Analysis

When equity targets ($\alpha_{\min}$) or physical throughput limits make a problem mathematically infeasible, AEGIS **never silently discards constraints**. Instead:
1. The solver reports an explicit `Infeasible` status and raises no false optimality claims.
2. An automated relaxation analyzer computes:
   - Global maximum feasible coverage: $\alpha_{\text{global}}^* = \min\left(1.0, \frac{\sum_{w,c} I_{w,c}}{\sum_{h,c} d_{h,c}}, \frac{\sum_w Cap_w}{\sum_{h,c} d_{h,c}}\right)$.
   - Product-specific bottleneck coverage: $\alpha_c^* = \min\left(1.0, \frac{\sum_w I_{w,c}}{\sum_h d_{h,c}}\right)$.
   - Physical resource deficits: exact additional units of inventory and warehouse throughput required to achieve the requested $\alpha_{\min}$.

---

### 8.3 Benchmarked Allocation Policies

AEGIS implements four distinct allocation policies evaluated on identical physical constraints and held-out realized demand:
1. **Proportional Inventory Allocation:** Distributes available warehouse stock in direct proportion to hospital demand ratios.
2. **Demand-Priority Greedy Allocation:** Iteratively routes inventory to high-severity clinical tiers (Trauma Centers) and nearby facilities first.
3. **Deterministic MILP:** Solves the full integer program using point forecasts ($p_{50}$ median).
4. **Two-Stage Stochastic MILP:** Simultaneously optimizes first-stage shipments across 5 discrete forecast scenarios ($p_{10}$ lull, $p_{50}$ baseline, $p_{90}$ surge, and intermediate Monte Carlo realizations) with recourse shortage penalties, enforcing nonanticipativity.

---

### 8.4 PowerShell Execution Commands for Milestone 2

```powershell
# Run the complete test suite including operations research audit regression tests (62 tests across M1 & M2)
uv run pytest -v

# Execute the 30-instance scientific benchmark across 6 operational regimes
uv run python scripts/run_optimization_benchmark.py --output-dir metrics --num-instances 30
```

---

### 8.5 Operations Research Audit & Verification

All benchmark tables, sample sizes, and paired differences have been audited and verified in [`docs/MILESTONE_02_AUDIT.md`](file:///E:/Projects/aegis/docs/MILESTONE_02_AUDIT.md):
- Strictly aligned pairwise comparisons: Deterministic MILP ($N=21$ opt / $N=25$ valid), Greedy ($N=20$), Proportional ($N=24$), Common 4-way subset ($N=16$).
- Every returned allocation undergoes independent verification by `TransportationNetwork.validate_allocation_feasibility`:
  - Zero warehouse inventory overdraw: $\sum_h x_{w,h,c} \le I_{w,c}$
  - Zero warehouse dispatch limit breach: $\sum_{h,c} x_{w,h,c} \le Cap_w$
  - Integrality verification: all shipment quantities $x \in \mathbb{Z}_{\ge 0}$ and vehicles $v \in \mathbb{Z}_{\ge 0}$
  - Route activation consistency: shipments only flow on activated routes ($x > 0 \implies y = 1$)
  - Vehicle capacity adherence: $\sum_c x \le Q_{\text{veh}} \cdot v$
  - Strict minimum service coverage: $\sum_w x \ge \alpha_{\min} d$ when required.

---

## 9. Milestone 3: Premium Decision Workspace and Explainability

Milestone 3 delivers an enterprise decision workspace built in Streamlit and Plotly, directly powered by the Milestone 1 forecasting models and the Milestone 2 multi-echelon optimization engine.

### 9.1 Design System & Visual Hierarchy

The workspace adopts a clean, high-contrast healthcare operations palette:
- **Background (`#F8FAFC`):** Soft slate canvas minimizing visual fatigue.
- **Card Surface (`#FFFFFF`):** Crisp containers with subtle elevation for tabular and metric views.
- **Primary Typography (`#172B46`):** High-contrast deep navy text adhering to WCAG AAA standards.
- **Primary Accent (`#2367A3`):** Steel blue for key operational metrics, logistics arcs, and warehouse nodes.
- **Clinical Accent (`#378D73`):** Clinical sage designating high fill rates and trauma center priorities.
- **Warning Accent (`#C78B31`):** Amber ocre flagging supply deficits, solver infeasibilities, and equity relaxations.

### 9.2 Five Interactive Workspace Tabs

1. **Overview Tab:**
   - Real-time KPIs: Network Forecast Demand, Total Warehouse Inventory, Projected Shortage Risk, Target Service Coverage.
   - Interactive 2D Cartesian Facility Map (20 hospitals color-coded by clinical tier, 3 fulfillment warehouses, and candidate logistics arcs).
   - Uncertainty-aware demand forecast time series with 80% prediction intervals ($p_{10}$ to $p_{90}$) from quantile GBDT regression.
   - Hospital risk ranking table sorting facilities by bed capacity, clinical tier penalty, and consumption velocity.

2. **Scenario Lab Tab:**
   - Real-time operational controls: Demand Surge ($0-100\%$), Stock Availability ($20-150\%$), Vehicle Capacity ($100-500$), Transport Capacity Throttle ($20-100\%$), Minimum Service Coverage $\alpha_{\min}$ ($0-100\%$), and Shortage Penalty Weight ($0.5-5.0\times$).
   - Policy Selector: Proportional Allocation, Demand-Priority Greedy, Deterministic MILP (SciPy HiGHS), and Two-Stage Stochastic MILP.
   - Live solver execution with feasibility status, runtime, and optimality gap reporting.
   - Cost decomposition waterfall chart (transport + route activation + vehicle trips + recourse penalties) and facility fill rate distributions.
   - Automated infeasibility detection with [`FairnessRelaxationAnalyzer`](file:///E:/Projects/aegis/src/aegis/optimization/fairness.py) computing the maximum achievable coverage $\alpha_{\text{global}}^*$ and physical resource shortfalls.

3. **Explainability Tab:**
   - **Demand Forecasting Attribution (TreeSHAP):** Uses exact polynomial TreeSHAP (`shap.TreeExplainer`) on the fitted XGBoost regressor. Delivers global feature importance rankings and local waterfall decomposition satisfying the Efficiency Axiom:
     $$\hat{y}(x) = \phi_0 + \sum_{i=1}^{39} \phi_i(x) \quad \text{with } |\hat{y} - (\phi_0 + \sum \phi_i)| < 10^{-4}$$
   - **Operations Research Decision Attribution:** Distinct [`AllocationDecisionExplainer`](file:///E:/Projects/aegis/src/aegis/explainability/decision_explainer.py) explaining why shipments occurred, route activation economics, warehouse capacity saturation, and clinical tier prioritization during deficits.

4. **Stress Testing Tab:**
   - 7 pre-configured healthcare shock scenarios: 40% stock loss, 50% demand surge, route disruption, vehicle reduction, infeasible fairness target, missing artifact fallback, and solver timeout.
   - Grounded benchmark comparison chart using audited results from [`metrics/optimization_benchmark_summary.csv`](file:///E:/Projects/aegis/metrics/optimization_benchmark_summary.csv).

5. **Responsible AI & Governance Tab:**
   - Synthetic data provenance notices and clinical non-validation disclaimers (zero patient-specific data or PHI/PII).
   - Cryptographic SHA-256 hashes of dataset manifests and serialized model binaries.
   - One-click session audit JSON export (`aegis_session_audit.json`) for regulatory transparency.

### 9.3 PowerShell Execution Commands for Milestone 3

```powershell
# 1. Run the entire AEGIS test suite (73 passing tests across M1, M2, M2-Audit, and M3)
uv run pytest -v

# 2. Run the specialized UI and Explainability unit & integration tests
uv run pytest -v tests/test_ui_and_explainability.py

# 3. Launch the Streamlit Decision Workspace
uv run streamlit run src/aegis/ui/app.py
```

### 9.4 Milestone 3 Documentation Links

- **UI Architecture & Design System:** [`docs/UI_ARCHITECTURE.md`](file:///E:/Projects/aegis/docs/UI_ARCHITECTURE.md)
- **Explainability & Attribution Mathematics:** [`docs/EXPLAINABILITY.md`](file:///E:/Projects/aegis/docs/EXPLAINABILITY.md)
- **Milestone 3 Verification Report:** [`docs/MILESTONE_03_VERIFICATION.md`](file:///E:/Projects/aegis/docs/MILESTONE_03_VERIFICATION.md)

