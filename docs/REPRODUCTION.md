# AEGIS Reproduction Guide & Instructions

**Project:** AEGIS — Adaptive Emergency Governance & Intelligent Supply  
**Competition:** DATANOVA 2026  
**Milestone:** 4 — Final Production Release  
**Status:** 100% Deterministic & Reproducible

---

## 1. System Requirements

- **Operating System:** Windows 11, Ubuntu 22.04 LTS, or macOS 14+
- **Python Version:** CPython 3.11
- **Package Manager:** `uv` (Fast Python package manager)
- **Disk Space:** ~500 MB (including virtual environment and serialized artifacts)
- **RAM:** Minimum 4 GB (8 GB recommended)

---

## 2. Windows PowerShell Setup & Execution

Open **PowerShell** in the project root (`E:\Projects\aegis`):

### Step 1: Virtual Environment Setup
```powershell
# 1. Create a fresh Python 3.11 virtual environment
uv venv --python 3.11

# 2. Activate virtual environment
.venv\Scripts\activate

# 3. Install core and dev dependencies
uv sync --extra dev
```

### Step 2: Code Quality & Automated Test Suite
```powershell
# 1. Run Ruff linter
uv run ruff check .

# 2. Verify code formatting
uv run ruff format --check .

# 3. Run complete test suite (78 passing tests across M1, M2, M3, and M4)
uv run pytest -v
```

### Step 3: End-to-End Pipeline Reproduction
```powershell
# 1. Deterministic synthetic data generation (365 days, 20 hospitals, 3 categories)
uv run python scripts/generate_data.py --seed 42 --days 365 --scenario baseline

# 2. Train forecasting models (Seasonal-Naive, Moving-Avg, Ridge, XGBoost Quantile)
uv run python scripts/train.py --config configs/train_config.json

# 3. Scientific evaluation on held-out test data (metrics/test_metrics.csv)
uv run python scripts/evaluate.py --config configs/evaluate_config.json

# 4. Multi-echelon optimization benchmark (30 instances across 6 regimes)
uv run python scripts/run_optimization_benchmark.py --output-dir metrics --num-instances 30

# 5. Generate editable 10-slide PowerPoint presentation
uv run python scripts/generate_presentation.py

# 6. Run browser verification and capture high-resolution screenshots
uv run python scripts/verify_ui_browser.py
```

### Step 4: Launching the Streamlit Decision Workspace
```powershell
# Launch the interactive application on http://localhost:8501
uv run streamlit run app.py
```

---

## 3. Linux & macOS (Bash) Setup & Execution

```bash
# 1. Create and activate environment
uv venv --python 3.11
source .venv/bin/activate

# 2. Install dependencies
uv sync --extra dev

# 3. Run full test suite
uv run pytest -v

# 4. Launch workspace
uv run streamlit run app.py
```

---

## 4. Expected Artifacts and File Checksums

After pipeline execution, verify the following files are populated in the workspace:

| Artifact Path | Expected Description |
| :--- | :--- |
| `data/processed/featured_data.parquet` | Leakage-safe panel dataset with 39 features (21,900 rows) |
| `models/xgboost_demand.joblib` | Serialized XGBoost model binary with quantile calibration |
| `metrics/test_metrics.csv` | Held-out test set accuracy (MAE 54.24, WAPE 14.62%) |
| `metrics/optimization_benchmark_summary.csv` | Audited benchmark results for 4 allocation policies |
| `metrics/paired_policy_differences.csv` | Paired statistical comparisons and bootstrap confidence intervals |
| `presentation/AEGIS_DATANOVA_2026.pptx` | 10-slide PowerPoint presentation with embedded screenshots |
| `docs/screenshots/` | 6 high-resolution browser verification PNG screenshots |
