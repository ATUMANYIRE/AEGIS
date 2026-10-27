# AEGIS System Architecture & Technical Specifications

**Project:** AEGIS — Adaptive Emergency Governance & Intelligent Supply  
**Competition:** DATANOVA 2026  
**Milestone:** 4 — Final Production Release  
**Status:** Complete, Verified, & Audited

---

## 1. High-Level Architecture Overview

AEGIS is an enterprise-grade decision-intelligence platform engineered for multi-echelon healthcare supply chain networks. It transforms non-stationary demand signals and physical logistics constraints into mathematically optimal, operationally feasible supply allocations across 20 simulated hospitals, 3 fulfillment warehouses, and 3 consumable categories.

```mermaid
graph TD
    subgraph Data & Simulation Engine
        Gen[Deterministic Synthetic Generator<br>Seed=42, 365 Days, Poisson Surges] --> Raw[Panel Records: 21,900 Rows]
        Raw --> FeatureEng[Leakage-Safe Feature Pipeline<br>Shifted Lags, Rolling Means, Calendar]
        FeatureEng --> Parquet[(Apache PyArrow Parquet<br>SHA-256 Manifest Verified)]
    end

    subgraph Machine Learning & Forecasting
        Parquet --> Split[Chronological Splits<br>Train: 1-260 | Val: 261-310 | Test: 311-365]
        Split --> XGB[Quantile GBDT Forecaster<br>Loss: reg:quantileerror]
        XGB --> Forecasts["Point Forecast (p50) & Intervals (p10, p90)"]
        XGB --> TreeSHAP[TreeSHAP Explainer<br>Additive Efficiency: err < 1e-4]
    end

    subgraph Operations Research Engine
        Forecasts --> ScenGen[ForecastScenarioGenerator<br>Nonanticipativity Scenarios]
        NetworkDef[TransportationNetwork<br>Distances, Fleet, Throughput] --> Solver[SciPy HiGHS MILP Solver<br>Branch-and-Cut, Simplex Dual]
        ScenGen --> Solver
        Solver --> OptResult[Optimal Allocations, Routes, Recourse]
        Solver --> FairnessRelax[FairnessRelaxationAnalyzer<br>Bottleneck Resource Diagnostics]
    end

    subgraph Decision Workspace & Explainability
        OptResult --> DecisionExp[AllocationDecisionExplainer<br>Constraint & Triage Attribution]
        TreeSHAP --> GenAI[GenAI Grounded Explainer<br>Pydantic Record + Injection Filter]
        DecisionExp --> GenAI
        OptResult --> UI[Streamlit Enterprise Decision Workspace<br>5 Interactive Tabs, Plotly Visualizations]
        GenAI --> UI
    end
```

---

## 2. Core Architectural Subsystems

### 2.1 Subsystem 1: Synthetic Demand & Network Simulation
- **Network Scope:** 20 hospitals spanning 4 operational tiers:
  - *Level 1 Trauma Centers (H01, H02):* 750–850 beds, $3.0\times$ shortage penalty multiplier.
  - *Regional Referral Centers (H03–H06):* 450–600 beds, $2.0\times$ penalty multiplier.
  - *Community Hospitals (H07–H14):* 200–350 beds, $1.2\times$ penalty multiplier.
  - *Specialty Clinics (H15–H20):* 90–150 beds, $1.0\times$ penalty multiplier.
- **Fulfillment Topology:** 3 Regional Warehouses ($W01$ Central Logistics Depot, $W02$ Northern Hub, $W03$ Southern Depot).
- **Consumable Categories:** PPE, Sanitation Products, Medical Utility Supplies.
- **Physics-Informed Logistics:** 2D Cartesian spatial coordinates with a 1.25 road circuity factor to model realistic transit friction:
  $$D_{w,h} = 1.25 \times \sqrt{(x_w - x_h)^2 + (y_w - y_h)^2}$$

### 2.2 Subsystem 2: Probabilistic Demand Forecasting & TreeSHAP
- **GBDT Architecture:** Quantile XGBoost regressor trained with `reg:quantileerror` on 39 features.
- **Prediction Intervals:** Dual quantile heads ($p_{10}$ and $p_{90}$) providing calibrated 80% prediction intervals.
  - Validated test WAPE: **14.62%**
  - Empirical 80% interval coverage: **82.3%**
  - Mean Prediction Interval Width (MPIW): 164.2 units
- **Explainability:** Exact polynomial TreeSHAP (`shap.TreeExplainer`) satisfying the Efficiency Axiom:
  $$\hat{y}(x) = \phi_0 + \sum_{i=1}^{39} \phi_i(x) \quad \text{with } |\hat{y} - (\phi_0 + \sum \phi_i)| < 10^{-4}$$

### 2.3 Subsystem 3: Multi-Echelon MILP Optimization Engine
- **Solver Backend:** SciPy HiGHS Mixed-Integer Linear Programming solver.
- **Formulation:**
  $$\min_{x, y, v, s} \sum_{w,h} \left[ \sum_c c_{w,h}^{\text{ship}} x_{w,h,c} + c_{w,h}^{\text{route}} y_{w,h} + c^{\text{veh}} v_{w,h} \right] + \sum_k p_k \sum_{h,c} \pi_{h,c}^{\text{short}} s_{h,c,k}$$
- **Hard Constraints:**
  - Inventory conservation: $\sum_h x_{w,h,c} \le I_{w,c}$
  - Warehouse dispatch throughput: $\sum_{h,c} x_{w,h,c} \le Cap_w$
  - Vehicle fleet capacity & route activation: $\sum_c x_{w,h,c} \le Q_{\text{veh}} v_{w,h} \le M y_{w,h}$
  - Recourse demand balance: $\sum_w x_{w,h,c} + s_{h,c,k} \ge d_{h,c}^{(k)}$
  - Minimum service coverage equity floor: $\sum_w x_{w,h,c} \ge \alpha_{\min} \bar{d}_{h,c}$

### 2.4 Subsystem 4: Grounded GenAI Decision Explanation Layer
- **Record Serialization:** Compiles predictive TreeSHAP attributions, MILP active constraints, and clinical equity metrics into structured Pydantic `DecisionContextRecord` models.
- **Grounding Verification:** Regex-based numerical extraction and tolerance auditing guaranteeing zero hallucinated metrics.
- **Adversarial Defense:** Detects and redacts prompt-injection attempts (e.g., `ignore previous instructions`, `bypass governance`).
- **Deterministic Offline Fallback:** If no external provider API keys are present, AEGIS executes a fully local deterministic explanation engine.

### 2.5 Subsystem 5: Enterprise Decision Workspace (UI)
- **Framework:** Streamlit 1.66 + Plotly 5.18.
- **Visual Design:** Warm-white enterprise palette (#F8FAFC, #FFFFFF, #172B46, #2367A3, #378D73, #C78B31).
- **Navigation:** 5 interactive tabs (Overview, Scenario Lab, Explainability, Stress Testing, Responsible AI).

---

## 3. Technology Stack & Dependencies

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.11, `uv` Package Manager | High-performance reproducible environment |
| **Data Processing** | Pandas 2.1+, PyArrow 14.0+, NumPy 1.26+ | Fast columnar serialization and feature transformation |
| **Machine Learning** | XGBoost 2.0+, Scikit-Learn 1.3+ | Quantile regression, conformal intervals, ML baselines |
| **Explainable AI** | SHAP 0.51.0+ (TreeExplainer) | Polynomial Shapley feature attribution |
| **Operations Research** | SciPy 1.11+ (HiGHS Branch-and-Cut) | Exact Mixed-Integer Linear Programming |
| **GenAI & Validation** | Pydantic 2.5+, REST Providers | Structured context validation, grounding auditing |
| **Decision Workspace** | Streamlit 1.66+, Plotly 5.18+ | Interactive decision intelligence dashboard |
| **Verification & QA** | Pytest 9.1+, Ruff 0.3+, Chrome CDP | Automated testing, linting, and browser automation |

---

## 4. Latency & Performance Profile

- **Cold Startup Latency:** ~2.1 s (loading Parquet features, serialized GBDT model, and network topology).
- **Warm Interactive Latency:** < 80 ms (via `@st.cache_resource` and `@st.cache_data`).
- **MILP Solver Latency (20 hospitals, 3 warehouses, 3 products):**
  - *Deterministic MILP:* 0.42 s mean runtime
  - *Two-Stage Stochastic MILP (5 scenarios):* 1.85 s mean runtime
  - *Heuristic Baselines (Greedy / Proportional):* < 10 ms
- **TreeSHAP Inference Latency:** ~12 ms per individual hospital-product instance.
- **Memory Consumption:** ~145 MB RSS working set.
