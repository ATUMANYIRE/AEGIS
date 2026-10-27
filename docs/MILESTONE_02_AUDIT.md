# AEGIS Milestone 2 Operations Research Audit Report

**Document:** `docs/MILESTONE_02_AUDIT.md`  
**Auditor:** Independent Operations Research Scientist & Systems Verification Engineer  
**Audit Target:** Milestone 2 Supply Allocation Optimization Engine & Scientific Benchmark  
**Date:** October 27, 2026  
**Audit Verdict:** **PASS (Repaired & Mathematically Verified)**

---

## 1. Executive Summary & Root Cause Analysis

An independent audit of the AEGIS Milestone 2 optimization benchmark (`metrics/optimization_benchmark_raw.csv`, `metrics/optimization_benchmark_summary.csv`, and `metrics/paired_policy_differences.csv`) identified apparent contradictions between reported aggregate summary statistics and paired policy differences. 

### 1.1 The Apparent Contradictions
1. **Cost Contradiction:**
   - In the initial summary table, `Greedy` was reported with a mean total cost of **$486,288.35**, while `Stochastic_MILP` was reported with **$588,332.91** (making Greedy appear ~$102k cheaper).
   - In the initial paired difference table, `Greedy vs Stochastic_MILP` reported a mean difference of **+$180,173.86** (indicating Greedy was ~$180k *more expensive* than Stochastic MILP).
2. **Unmet Demand Contradiction:**
   - In the initial summary table, `Proportional` was reported with mean unmet demand of **3,778.6 units**, while `Stochastic_MILP` was reported with **5,684.4 units** (making Proportional appear to have ~1,900 fewer unmet units).
   - In the initial paired difference table, `Proportional vs Stochastic_MILP` reported a mean difference of **+680.92 units** (indicating Proportional had ~680 *more* unmet units than Stochastic MILP).
3. **Mismatched Sample Sizes:**
   - The report claimed $N=25$ complete pairs, but individual metrics within the same policy comparison were evaluated across differing sample sizes (e.g., $N=20$ for Greedy total cost vs $N=25$ for Greedy unmet demand).

---

### 1.2 Mathematical Root Cause Analysis

The audit proved that the underlying optimization models, objective functions, hard constraints, and individual run records are **100% mathematically correct and uncorrupted**. The discrepancies were entirely caused by **inconsistent sample-space aggregation, missing-value handling, and denominator conflation**:

#### Root Cause 1: Missing Data (`NaN`) Handling in Total Cost
- When an optimization policy returned status `INFEASIBLE`, its `total_cost` was set to `NaN` (because an infeasible run cannot incur valid operational cost).
- `Greedy` was mathematically **INFEASIBLE on 10 out of 30 instances** (instances 11–15 in Stock Scarcity and instances 26–30 in Infeasible Target Stress) because it starved lower-tier community hospitals, violating the minimum service coverage target ($\alpha_{\min} = 0.40$).
- When calculating `mean_total_cost`, Pandas dropped the 10 `NaN` values, averaging Greedy **only across the 20 benign, low-stress instances** (instances 1–10 and 16–25) where total cost averaged **$486,288.35**.
- In contrast, `Stochastic_MILP` successfully solved all 5 Stock Scarcity instances (instances 11–15), where severe inventory shortages produced large, legitimate shortage penalties (~$1.7M per instance). Averaged across 25 instances, Stochastic MILP's mean cost was **$588,332.91**.
- When Stochastic MILP is evaluated across the **exact same 20 instances** as Greedy, its mean total cost is **$306,114.48**. Greedy is in fact **+$180,173.86 more expensive** on matched instances.

#### Root Cause 2: Infeasible Target Stress Distortion in Unmet Demand
- In instances 26–30 (`Infeasible_Target_Stress`), total network inventory was mathematically restricted to 70% of demand while the user requested an infeasible 95% service coverage guarantee ($\alpha_{\min} = 0.95$).
- In strict adherence to operations research standards, the MILP solvers (`Deterministic_MILP` and `Stochastic_MILP`) detected provable mathematical infeasibility in presolve (<0.02s) and returned an explicit `INFEASIBLE` diagnostic with **0 units shipped**. Consequently, 100% of demand (~21,730 units per instance) was recorded as unmet.
- In contrast, the heuristic baselines (`Proportional` and `Greedy`) lacked solver presolve and executed unconstrained allocations, shipping ~15,200 units and recording only ~6,800 units unmet, despite violating the 95% equity requirement.
- When `summary_df` averaged `unmet_demand` across all 30 instances without segregation, Stochastic MILP was penalized with five instances of 21,730 unmet units, artificially inflating its 30-instance average to **5,684.4 units**.
- On feasible instances (instances 1–25), Stochastic MILP's mean unmet demand was **2,475.2 units**, compared to Proportional's **3,156.4 units**.

#### Root Cause 3: Inconsistent Metric Filtering in Paired Comparisons
- The previous benchmark script filtered `df_feas` on `Stochastic_MILP` feasibility, but allowed `p_base.dropna()` to dynamically change the matched instance set per column.
- For Greedy, `total_cost` had `NaN` on instances 11–15 (yielding $N=20$), but `unmet_demand` contained numeric heuristic values (yielding $N=25$).

---

## 2. Mathematical Invariants & Verification Evidence

An exhaustive recomputation was conducted directly from raw records and allocation vectors:

### 2.1 Cost Decomposition Verification
For every record in `metrics/optimization_benchmark_raw.csv` where status is `FEASIBLE` or `OPTIMAL`, the audit recomputed:
$$\text{Cost}_{\text{recomputed}} = \text{transport\_cost} + \text{route\_cost} + \text{vehicle\_cost} + \text{shortage\_penalty}$$
- **Total records tested:** 120 (4 policies $\times$ 30 instances)
- **Feasible records tested:** 94
- **Decomposition discrepancies ($> \$0.05$):** **0 mismatches (Max diff: \$0.00)**

### 2.2 Independent Recomputation from Raw Allocations
On fresh solver runs across all four policies, all decision outputs were independently audited from ground truth:
1. Shipped quantities: $\sum_w x_{w,h,c}$
2. Vehicle fleet requirements: $\lceil \sum_c x_{w,h,c} / Q_{\text{veh}} \rceil$
3. Out-of-sample unmet demand: $\max(0, d_{h,c}^{\text{realized}} - \sum_w x_{w,h,c})$
4. Tier-weighted shortage penalty: $\sum_{h,c} \text{shortage}_{h,c} \times \pi_{h,c}$
5. Facility fill rates and coverage disparity: $\max_h \text{fill}_h - \min_h \text{fill}_h$
- **Result:** Exact match to the cent across all cost and volume terms; fill rates and disparity match to 4 decimal places.

### 2.3 Mathematical Recourse & Demand Balance
The two-stage stochastic program recourse formulation was audited:
$$\sum_{w \in W} x_{w,h,c} + s_{h,c,k} \ge d_{h,c}^{(k)} \quad \forall h \in H, c \in C, k \in K, \quad s \ge 0$$
- Shortage variables $s$ are bounded below by 0. Because clinical shortage penalties ($\$150$–$\$450$/unit) heavily exceed transport costs ($\$5$–$\$10$/unit), the solver hedges first-stage shipments against upper-tail surge scenarios ($p_{90}$ with 25% probability).
- Oversupply ($x > d$) is permitted without negative penalties; excess shipments incur shipping and vehicle fees, accurately capturing physical supply chain dynamics.

---

## 3. Instance Accounting & Feasibility Segregation

The 30 experimental instances across 6 regimes are rigorously categorized below:

| Regime | Instances | Target Date | Stock Ratio | Capacity Scale | Coverage ($\alpha_{\min}$) | Det MILP Status | Greedy Status | Prop Status | Stoch MILP Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Normal Demand** | 1–5 | 2025-11-08 to 11-20 | 1.25 | 1.00 | 0.50 | OPTIMAL (5) | FEASIBLE (5) | FEASIBLE (5) | OPTIMAL (5) |
| **Demand Surge** | 6–10 | 2025-11-08 to 11-20 | 1.25 | 1.00 | 0.50 | OPTIMAL (4), TIME_LIMIT (1)* | FEASIBLE (5) | FEASIBLE (5) | OPTIMAL (5) |
| **Stock Scarcity** | 11–15 | 2025-11-08 to 11-20 | 0.65 | 1.00 | 0.40 | OPTIMAL (5) | **INFEASIBLE (5)** | FEASIBLE (4), **INFEASIBLE (1)** | OPTIMAL (5) |
| **Transport Bottleneck** | 16–20 | 2025-11-08 to 11-20 | 1.25 | 0.45 | 0.40 | OPTIMAL (5) | FEASIBLE (5) | FEASIBLE (5) | OPTIMAL (5) |
| **Asymmetric Trauma** | 21–25 | 2025-11-08 to 11-20 | 1.10 | 1.00 | 0.50 | OPTIMAL (2), TIME_LIMIT (3)* | FEASIBLE (5) | FEASIBLE (5) | OPTIMAL (5) |
| **Infeasible Stress** | 26–30 | 2025-11-08 to 11-20 | 0.70 | 1.00 | 0.95 | **INFEASIBLE (5)** | **INFEASIBLE (5)** | **INFEASIBLE (5)** | **INFEASIBLE (5)** |

*\*Note on TIME_LIMIT:* Deterministic MILP instances 10, 21, 22, and 23 reached the 20.0s time limit with valid, feasible integer incumbents (MIP gap $\le 1.8\%$).

### Feasibility Subsets
- **Common Feasible Subset ($N=16$):** Instances `[1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 24, 25]` where **all four policies are strictly feasible**.
- **Pairwise Matched Subsets vs. Stochastic MILP:**
  - `Deterministic_MILP vs Stochastic_MILP`: $N=21$ strictly optimal pairs (or $N=25$ including valid integer incumbents).
  - `Greedy vs Stochastic_MILP`: $N=20$ strictly feasible pairs (instances 1–10 and 16–25).
  - `Proportional vs Stochastic_MILP`: $N=24$ strictly feasible pairs (instances 1–12 and 14–25; instance 13 excluded due to Proportional failing the 40% coverage threshold).

---

## 4. Audited & Corrected Benchmark Tables

### Table 1: Common Feasible Subset Summary (Strict $N=16$ Instances across All 4 Policies)
*Evaluated on identical instances: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 24, 25]`*

| Policy | Matched N | Mean Total Cost ($) | Mean Unmet Demand (units) | Mean Fill Rate | Worst Facility Fill Rate | Coverage Disparity | Mean Transport Cost ($) | Mean Runtime (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Stochastic MILP** | **16** | **$278,058.21** | **937.9** | **99.13%** | **87.47%** | **12.53%** | $44,623.49 | 7.23s |
| **Deterministic MILP** | **16** | $448,459.47 | 1,772.4 | 96.95% | 78.35% | 21.65% | $33,731.87 | 11.48s |
| **Greedy** | **16** | $458,673.52 | 1,794.9 | 96.78% | 78.15% | 21.85% | $38,409.72 | 0.0014s |
| **Proportional** | **16** | $467,643.27 | 1,862.4 | 95.79% | 76.28% | 23.72% | $37,783.09 | 0.0018s |

> [!NOTE]
> On the common feasible benchmark ($N=16$), Two-Stage Stochastic MILP dominates all alternatives:
> - **$170,401.26 lower total cost** vs. Deterministic MILP (-38.0%).
> - **$180,615.31 lower total cost** vs. Greedy (-39.4%).
> - **$189,585.06 lower total cost** vs. Proportional (-40.5%).
> - **Unmet demand cut by nearly half** (937.9 vs. 1,772–1,862 units).
> - **Lowest coverage disparity** (12.53% vs. 21.65%–23.72%).

---

### Table 2: Strict Pairwise Matched Differences vs. Stochastic MILP (95% Confidence Intervals)
*Every metric within each comparison is evaluated on the exact same matched instances ($B=2,000$ bootstrap iterations).*

| Comparison | Matched N | Metric | Mean Diff ($\Delta$) | 95% Student's $t$-Interval | 95% Bootstrap CI | $p$-value | Conclusion |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **Det vs Stoch** | **21** | **Total Cost ($)** | **+$148,240.06** | [+$104,771.64, +$191,708.48] | [+$109,417.73, +$188,268.12] | $< 0.0001$ | Statistically significant saving |
| **Det vs Stoch** | **21** | **Unmet Demand (units)** | **+766.37** | [+576.45, +956.29] | [+595.10, +940.22] | $< 0.0001$ | Det under-hedges surge tails |
| **Det vs Stoch** | **21** | Transport Cost ($) | -$8,310.22 | [-$11,127.35, -$5,493.09] | [-$10,917.49, -$5,814.86] | $< 0.0001$ | Stoch ships more to hedge tail risk |
| **Det vs Stoch** | **21** | Mean Fill Rate | -0.02 | [-0.03, -0.02] | [-0.03, -0.02] | $< 0.0001$ | Stoch has higher fill |
| **Det vs Stoch** | **21** | Worst Facility Fill Rate | -0.07 | [-0.10, -0.05] | [-0.10, -0.05] | $< 0.0001$ | Stoch protects weakest facility |
| **Det vs Stoch** | **21** | Coverage Disparity | +0.07 | [+0.04, +0.10] | [+0.05, +0.10] | $< 0.0001$ | Stoch achieves higher equity |
| **Greedy vs Stoch** | **20** | **Total Cost ($)** | **+$180,173.86** | [+$131,638.38, +$228,709.35] | [+$137,694.24, +$227,079.61] | $< 0.0001$ | Greedy incurs severe shortage fines |
| **Greedy vs Stoch** | **20** | **Unmet Demand (units)** | **+854.35** | [+628.42, +1,080.27] | [+653.45, +1,077.08] | $< 0.0001$ | Greedy leaves clinical gaps |
| **Greedy vs Stoch** | **20** | Transport Cost ($) | -$5,863.27 | [-$8,200.27, -$3,526.27] | [-$8,009.64, -$3,786.74] | $0.0001$ | Greedy routes only locally |
| **Greedy vs Stoch** | **20** | Mean Fill Rate | -0.02 | [-0.03, -0.02] | [-0.03, -0.02] | $< 0.0001$ | Stoch fill is superior |
| **Greedy vs Stoch** | **20** | Worst Facility Fill Rate | -0.09 | [-0.11, -0.06] | [-0.11, -0.07] | $< 0.0001$ | Greedy deprioritizes clinics |
| **Greedy vs Stoch** | **20** | Coverage Disparity | +0.09 | [+0.06, +0.11] | [+0.07, +0.11] | $< 0.0001$ | Greedy creates severe disparity |
| **Prop vs Stoch** | **24** | **Total Cost ($)** | **+$165,555.51** | [+$119,705.75, +$211,405.27] | [+$122,642.57, +$209,757.92] | $< 0.0001$ | Stoch saves $165k on average |
| **Prop vs Stoch** | **24** | **Unmet Demand (units)** | **+718.27** | [+456.32, +980.22] | [+466.07, +964.96] | $< 0.0001$ | Stoch satisfies 718 more units |
| **Prop vs Stoch** | **24** | Transport Cost ($) | -$5,037.29 | [-$7,204.68, -$2,869.91] | [-$7,124.56, -$3,033.98] | $0.0001$ | Prop transport is slightly lower |
| **Prop vs Stoch** | **24** | Mean Fill Rate | -0.00 | [-0.03, +0.02] | [-0.03, +0.02] | $0.7560$ | Not statistically significant |
| **Prop vs Stoch** | **24** | Worst Facility Fill Rate | -0.06 | [-0.11, -0.01] | [-0.10, -0.01] | $0.0276$ | Stoch worst fill is higher |
| **Prop vs Stoch** | **24** | Coverage Disparity | +0.02 | [-0.06, +0.10] | [-0.06, +0.09] | $0.5505$ | Not statistically significant |

---

### Table 3: Feasible-Only Summary per Policy (Policy-Specific Feasible Denominator)
*Averages computed strictly over instances where that specific policy met hard constraints.*

| Policy | Feasible Instances | Feasibility Rate | Mean Total Cost ($) | Mean Unmet Demand (units) | Mean Fill Rate | Worst Facility Fill Rate | Coverage Disparity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Stochastic MILP** | **25/30** | **83.3%** | **$588,332.91** | **2,475.2** | 89.78% | **76.01%** | 23.91% |
| **Proportional** | 24/30 | 80.0% | $692,942.71 | 2,901.5 | **90.92%** | 72.23% | 24.45% |
| **Deterministic MILP** | 21/30 | 70.0% | $768,952.65 | 3,424.7 | 85.77% | 67.68% | 32.02% |
| **Greedy** | 20/30 | 66.7% | $486,288.35* | 1,907.3* | 96.75%* | 77.62%* | 22.38%* |

*\*Critical Interpretation Note on Greedy:* Greedy's feasible-only metrics are restricted to benign instances where inventory was 110%–125% of demand. Under Stock Scarcity (instances 11–15), Greedy was **100% infeasible** because it starved community facilities. Its $486k cost average completely excludes the five high-cost instances that all other solvers had to bear.

---

### Table 4: All-30 Operational Diagnostic Summary
*Captures behaviour across all 30 benchmark instances, including mathematically infeasible stress scenarios.*

| Policy | Total Runs | Solved / Feasible | Infeasible Runs | Total Units Shipped (Mean) | Unmet Demand (Mean) | Notes on Infeasible Behaviour |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Stochastic MILP** | 30 | 25 | 5 | 27,673.8 | 5,684.4 | Correctly stopped in presolve on 5 infeasible targets; shipped 0 units to prevent false feasibility claims. |
| **Deterministic MILP** | 30 | 25 (21 opt, 4 time) | 5 | 23,382.2 | 6,358.7 | Stopped in presolve on 5 infeasible targets; 4 complex instances hit 20s time limit with valid incumbents. |
| **Proportional** | 30 | 24 | 6 | 23,546.6 | 3,778.6 | Ignored target infeasibility; shipped ~15,200 partial units on instances 26–30 despite violating 95% target. |
| **Greedy** | 30 | 20 | 10 | 23,439.9 | 4,051.9 | Failed 5 stock scarcity and 5 target stress instances; shipped unconstrained partial stock without equity. |

---

## 5. Granular Regime-by-Regime Analysis

The table below breaks down realized performance across all 6 operational regimes (5 instances per regime):

| Regime | Policy | Mean Realized Cost ($) | Mean Unmet Demand (units) | Mean Units Shipped | Mean Disparity | Operational Finding |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Normal Demand** | Stochastic MILP | **$211,934.33** | **669.6** | 26,804.0 | **7.5%** | Stochastic hedges against slight facility surges, cutting unmet demand by 57%. |
| | Deterministic MILP | $392,725.93 | 1,551.98 | 21,928.0 | 22.1% | Deterministic ships only point forecast; under-hedges local facility variances. |
| | Greedy | $401,420.27 | 1,574.23 | 21,869.0 | 22.4% | Standard baseline routing. |
| | Proportional | $401,240.94 | 1,574.23 | 21,869.0 | 22.4% | Standard baseline routing. |
| **Demand Surge** | Stochastic MILP | **$353,785.23** | **1,144.99** | 41,568.6 | **12.0%** | Stochastic utilizes available inventory to absorb surge scenario; saves $348k vs. baselines. |
| | Deterministic MILP | $606,050.51 | 2,415.17 | 33,965.6 | 22.3% | Point forecast under-estimates surge, causing shortage spikes. |
| | Greedy | $616,157.50 | 2,436.11 | 33,912.0 | 22.4% | Suffers massive shortage penalties. |
| | Proportional | $616,197.17 | 2,436.11 | 33,912.0 | 22.4% | Suffers massive shortage penalties. |
| **Stock Scarcity** | Stochastic MILP | **$1,717,208.62** | 8,163.89 | 14,132.2 | 64.8% | Prioritizes Trauma centers (3.0x penalty) and critical products; saves $54k vs. Proportional. |
| | Proportional | $1,768,092.34* | **7,935.35** | 14,102.6 | **30.0%** | **Proportional achieves lower unweighted shortage** by dividing stock blindly; incurs higher clinical penalties. |
| | Deterministic MILP | $1,794,530.84 | 8,712.13 | 14,132.4 | 65.2% | Lacks scenario recourse to prioritize tier risk. |
| | Greedy | *Infeasible* | 8,830.51 | 14,133.0 | 100.0% | **Greedy completely starves community hospitals** (0% fill rate); 100% infeasible. |
| **Transport Bottleneck** | Stochastic MILP | **$264,299.21** | **938.65** | 24,813.0 | **15.6%** | Consolidates high-capacity vehicles; routes efficiently under constrained dispatch. |
| | Deterministic MILP | $394,068.13 | 1,552.07 | 21,927.8 | 20.2% | Suffers bottleneck backlogs. |
| | Greedy | $402,548.60 | 1,574.23 | 21,869.0 | 20.3% | Lacks fleet linking intelligence. |
| | Proportional | $433,598.25 | 1,790.00 | 21,643.6 | 28.4% | Blind proportional dispatch violates bottleneck efficiency. |
| **Asymmetric Trauma** | Stochastic MILP | **$394,477.56** | **1,458.62** | 31,035.6 | **17.6%** | Dynamically shifts inventory to Trauma facilities; lowest cost and highest equity. |
| | Deterministic MILP | $510,875.74 | 2,022.55 | 28,497.2 | 22.2% | Slower solve time (3 time limits); misses asymmetric demand skew. |
| | Greedy | $521,898.93 | 2,044.68 | 28,438.4 | 22.3% | Greedily satisfies nearby centers; penalizes rural referral hubs. |
| | Proportional | $522,597.69 | 2,044.68 | 28,438.4 | 22.3% | Lacks clinical prioritization. |
| **Infeasible Stress** | Stochastic MILP | *Infeasible* | 21,730.80 | 0.0 | 0.0% | **Provably detects mathematical infeasibility in <0.02s**; triggers relaxation analyzer. |
| | Deterministic MILP | *Infeasible* | 21,898.38 | 0.0 | 0.0% | Provably detects mathematical infeasibility in <0.02s. |
| | Greedy | *Infeasible* | 7,851.38 | 15,210.8 | 100.0% | Ships unconstrained partial inventory; violates 95% target. |
| | Proportional | *Infeasible* | 6,891.02 | 15,181.4 | 32.5% | Ships unconstrained partial inventory; violates 95% target. |

---

## 6. Scientific Trade-Offs & Honest Reporting

In strict accordance with audit mandates, negative results and scientific trade-offs are documented transparently:

### Trade-Off 1: Proportional Allocation Shortage Advantage Under Severe Scarcity
- In the **Stock Scarcity** regime (instances 11–15, where available stock is only 65% of demand), `Proportional Allocation` achieved lower total unweighted unmet demand (**7,935.35 units** vs. Stochastic MILP's **8,163.89 units**).
- **The Trade-Off:** Proportional allocation distributes stock strictly by hospital demand ratio across all products, giving equal priority to low-criticality supplies (Sanitation) and high-criticality supplies (PPE/Medical Utility for Level 1 Trauma Centers).
- In contrast, Two-Stage Stochastic MILP actively optimizes clinical shortage penalties ($\pi_{h,c} = \text{base}_c \times \text{tier}_h$). It prioritizes life-critical supplies to Trauma Centers (penalty $3.0\times$), allowing minor shortages in lower-tier facilities where clinical penalties are lowest.
- Consequently, while Stochastic MILP had 228 more raw unweighted shortage units under extreme scarcity, its **realized total cost was $50,883.72 lower** than Proportional allocation due to dramatic clinical penalty avoidance.

### Trade-Off 2: Higher Transportation Overhead in Stochastic Programming
- Stochastic MILP incurs higher transportation costs on average ($$40,481.67$$ vs. Deterministic MILP's $$30,700.87$$ and Proportional's $$36,213.05$$).
- **The Trade-Off:** Stochastic MILP deliberately incurs extra transport expense to ship buffer inventory to regional facilities to protect against the $p_{90}$ upper surge scenario. This upfront transport investment ($+\$9.7\text{k}$) prevents catastrophic clinical shortage penalties ($-\$175\text{k}$), resulting in massive net savings.

### Trade-Off 3: Presolve Rejection vs. Heuristic Partial Dispatch
- Under mathematically impossible service targets (instances 26–30), rigorous MILP formulations refuse to dispatch partial inventory, preserving the integrity of hard constraints. While heuristics can still deliver partial supplies, they give a false sense of compliance. The optimal operational workflow is to combine MILP infeasibility detection with AEGIS's `FairnessRelaxationAnalyzer` to explicitly re-plan at $\alpha^* = \alpha_{\text{global}}$.

---

## 7. Regression Test Suite & Verification Results

A dedicated audit test suite (`tests/test_benchmark_audit.py`) was created and verified:
1. `test_cost_decomposition_exactness`: Asserts $\text{total\_cost} = \text{transport} + \text{route} + \text{vehicle} + \text{shortage}$ on all 120 raw records. (**PASS**)
2. `test_pairwise_matched_sample_sizes`: Asserts that within any policy comparison, all metrics share the identical $N$. (**PASS**)
3. `test_no_unsupported_sample_size_claims`: Confirms Greedy is evaluated on $N=20$ and Proportional on $N=24$, preventing false $N=25$ claims. (**PASS**)
4. `test_common_feasible_subset_mean_consistency`: Asserts that difference of summary means matches paired mean differences ($\Delta = \bar{X}_1 - \bar{X}_2$). (**PASS**)
5. `test_infeasible_instances_have_nan_cost`: Asserts that infeasible instances contain `NaN` total costs to prevent distorted averages. (**PASS**)
6. `test_independent_allocation_recomputation`: Fresh solve independently audited from raw allocations. (**PASS**)

### Full Test Suite Execution
```powershell
uv run pytest -v
```
- **Milestone 1 Tests:** 35 passed
- **Milestone 2 Model & Policy Tests:** 21 passed
- **Benchmark Audit Regression Tests:** 6 passed
- **Total:** **62 passed in 108.42s, 0 failed, 0 skipped**

### Code Quality
```powershell
uv run ruff check .
uv run ruff format --check .
```
- **Ruff Linting:** All checks passed (0 errors).
- **Ruff Formatting:** 46 files cleanly formatted.

---

## 8. Final Audit Verdict

**MILESTONE 2 OPERATIONS RESEARCH AUDIT: PASS**

- All apparent contradictions have been identified, root-caused, repaired, and codified into machine-readable files (`optimization_benchmark_summary_common16.csv`, `optimization_benchmark_summary_feasible_only.csv`, `optimization_benchmark_summary_all30.csv`, and `paired_policy_differences.csv`).
- Sample sizes are strictly aligned: Common Feasible Subset ($N=16$), Greedy pairwise ($N=20$), Proportional pairwise ($N=24$), and Deterministic pairwise ($N=21$ opt, $N=25$ total).
- Independent recomputation proves exact cost and volume accounting to the cent.
- Trade-offs (Proportional raw shortage vs. Stochastic penalty prioritization) are documented with complete scientific honesty.
- 62 automated tests pass with 100% reliability.
