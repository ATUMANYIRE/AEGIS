# AEGIS Model Card: Medical Consumable Demand Forecasters

**Model Family:** AEGIS Demand Forecasting Suite  
**Version:** 1.0.0  
**Milestone:** Milestone 1 (Foundation, Data Engineering, Forecasting and Scientific Validation)  
**Authors:** DATUMANYIRE  

---

## 1. Model Overview & Architectures

AEGIS Milestone 1 evaluates four distinct demand forecasting architectures for non-patient-specific medical consumables:

1. **Seasonal-Naive Forecaster (`SeasonalNaiveForecaster`):**
   - *Equation:* $\hat{y}_{t} = y_{t-7}$
   - Exploits the dominant 7-day cyclical operating rhythm of hospital operations (e.g., scheduled elective procedures, weekend staffing schedules). Fallback to $y_{t-1}$ or series mean for initial boundary periods.
   - *Interval Estimation:* In-sample empirical residual quantiles at 10th and 90th percentiles.

2. **Moving-Average Forecaster (`MovingAverageForecaster`):**
   - *Equation:* $\hat{y}_t = \frac{1}{K} \sum_{k=1}^K y_{t-k}$ ($K = 7$ days).
   - Strictly shifted rolling mean preventing observation $y_t$ from leaking into prediction for $t$.
   - *Interval Estimation:* Historical residual quantiles.

3. **Regularized Ridge Regression (`RegularizedRegressionForecaster`):**
   - *Formulation:* $\min_{\beta} \|y - X\beta\|_2^2 + \alpha \|\beta\|_2^2$.
   - Multi-feature linear baseline with standard feature normalization (`StandardScaler`) fit strictly on the training partition.
   - *Categorical Handling:* `OneHotEncoder(handle_unknown='ignore')` applied to facility IDs, product categories, tiers, and warehouse nodes.
   - *Interval Estimation:* Split Conformal Prediction calibrated on the held-out validation partition, guaranteeing finite-sample marginal coverage.

4. **Extreme Gradient Boosting Regressor (`XGBoostDemandForecaster`):**
   - GBDT with tree-depth regularization and subsampling.
   - *Point Estimator:* `objective='reg:squarederror'`, hyperparameters (depth, learning rate) tuned exclusively on the development fold.
   - *Interval Estimator:* Dual quantile gradient boosted trees with `objective='reg:quantileerror'` at $\alpha = 0.10$ and $\alpha = 0.90$, supplemented by conformal residual checks.

---

## 2. Feature Schema & Leakage Safety

All feature transformations satisfy strict time-series causality constraints:

- **Lagged Observations:** $y_{t-1}, y_{t-2}, y_{t-3}, y_{t-7}, y_{t-14}, y_{t-21}, y_{t-28}$.
- **Rolling Aggregations:** 7-day, 14-day, and 28-day rolling mean, std, min, and max. Computed by **first** shifting series by 1 period ($\text{shift}(1)$), ensuring zero target leakage.
- **Calendar Signals:** Cyclical sin/cos encodings of Day of Week and Day of Year, month, and weekend indicator.
- **Supply & Network Metadata:** Bed capacity, facility operational tier, baseline demand multipliers, lagged on-hand inventory, and lagged delivery lead times.

---

## 3. Training & Validation Strategy

To prevent temporal leakage:
- **Chronological Split:**
  - **Training Partition:** Day 1 to Day 260 (~8.5 months).
  - **Validation Partition (Development):** Day 261 to Day 310 (~50 days). Used exclusively for hyperparameter tuning and conformal calibration.
  - **Held-Out Test Partition:** Day 311 to Day 365 (~55 days). Untouched until final scientific evaluation.
- **Zero Shuffling:** Random cross-validation is strictly disallowed for time-series observations.

---

## 4. Evaluation Metrics & Scientific Validation

Performance is quantified using:

- **Point Accuracy:**
  - $\text{MAE} = \frac{1}{N} \sum |y_i - \hat{y}_i|$
  - $\text{RMSE} = \sqrt{\frac{1}{N} \sum (y_i - \hat{y}_i)^2}$
  - $\text{WAPE} = \frac{\sum |y_i - \hat{y}_i|}{\sum y_i}$
- **Prediction Interval Rigor:**
  - **Empirical Coverage (Nominal 80%):** $\frac{1}{N} \sum \mathbf{1}\{q_{0.10} \le y_i \le q_{0.90}\}$
  - **Mean Prediction Interval Width (MPIW):** $\frac{1}{N} \sum (q_{0.90} - q_{0.10})$
  - **Pinball Loss (Quantile Loss):** Evaluated at 10th, 50th, and 90th percentiles.
- **Segmented Granularity:** Per-facility (20 hospitals) and per-product (3 categories) breakdown metrics stored in machine-readable CSV format.

---

## 5. Limitations & Caveats

1. **Synthetic Data Generalizability:** Models are trained on simulated facility dynamics. While the generator implements realistic empirical supply chain patterns (seasonality, lead times, stockout right-censoring), synthetic distributions do not account for real-world idiosyncrasies such as sudden administrative protocol shifts or global geopolitical embargoes.
2. **Clinical Disclaimer:** AEGIS forecasts inventory unit demand for logistics planning. It must not be interpreted as clinical advice or used for patient triage or drug dosages.
3. **Honest Reporting Guarantee:** If non-parametric baselines (such as Seasonal-Naive) outperform gradient boosting during specific stable operational regimes, this behavior is preserved and documented without cosmetic tuning.
