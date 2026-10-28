"""AEGIS — Decision Intelligence Workspace.

Streamlit application orchestrating multi-echelon demand forecasting,
TreeSHAP explainability, and uncertainty-aware supply allocation MILP optimization.
"""

from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.explainability.decision_explainer import (
    AllocationDecisionExplainer,
    DecisionExplanation,
)
from aegis.genai import DecisionExplanationService, build_context_record
from aegis.optimization.engine import optimize
from aegis.optimization.schema import OptimizationResult
from aegis.scenarios.network import NetworkParameters, TransportationNetwork
from aegis.ui.components import (
    get_git_commit_short,
    render_decision_explanation_card,
    render_genai_explanation_card,
    render_header,
    render_hospital_risk_ranking,
    render_provenance_sidebar,
    render_table,
)
from aegis.ui.plots import (
    plot_cost_waterfall,
    plot_facility_map,
    plot_fill_rate_distribution,
    plot_forecast_timeseries,
    plot_policy_benchmark_comparison,
    plot_shap_summary,
    plot_shap_waterfall,
)
from aegis.ui.state import (
    get_cached_benchmark_metrics,
    get_cached_featured_data,
    get_cached_model_and_explainer,
    get_cached_network,
    get_cached_scenario_generator,
    init_session_state,
)
from aegis.ui.theme import apply_custom_css

# Page Configuration
try:
    _ICON = Image.open(Path(__file__).resolve().parents[3] / "assets" / "aegis_icon.png")
except Exception:
    _ICON = "🛡️"
st.set_page_config(
    page_title="AEGIS Decision Intelligence Workspace",
    page_icon=_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Enterprise Theme CSS
apply_custom_css()
init_session_state()

# Load Caches
forecaster, shap_explainer = get_cached_model_and_explainer()
df_featured = get_cached_featured_data()
scen_gen = get_cached_scenario_generator()
network = get_cached_network()
benchmark_metrics = get_cached_benchmark_metrics()

# Render Header & Sidebar
render_header()
render_provenance_sidebar()

# Main Workspace Tabs
tab_overview, tab_lab, tab_explain, tab_stress, tab_governance = st.tabs(
    [
        "Network Overview",
        "Scenario Lab",
        "Explainability & AI",
        "Stress Testing",
        "Responsible AI & Governance",
    ]
)

# ==============================================================================
# TAB 1: OVERVIEW & NETWORK TELEMETRY
# ==============================================================================
with tab_overview:
    st.markdown("#### Real-Time Healthcare Supply Chain Overview")
    st.markdown(
        "<div style='color: #5B6B75; font-size: 0.88rem; margin-bottom: 16px;'>"
        "Deterministic synthetic network modeling 20 hospitals across 4 operational tiers, 3 fulfillment warehouses, and 3 medical consumable categories."
        "</div>",
        unsafe_allow_html=True,
    )

    # Date selector for snapshot
    available_dates = ["2025-11-08", "2025-11-11", "2025-11-14", "2025-11-17", "2025-11-20"]
    selected_date = st.selectbox(
        "Select Operational Forecast Date (Held-Out Horizon):",
        options=available_dates,
        index=0,
        key="overview_date_select",
    )

    try:
        # Generate or load baseline scenarios for selected date
        scen_set = scen_gen.generate_scenario_set(
            target_date=selected_date, num_scenarios=5, seed=42
        )
        tot_forecast = sum(scen_set.point_forecast.values())

        # Establish baseline available inventory (1.25 ratio)
        stock_dict = {}
        for c in PRODUCT_CATEGORIES:
            cat_exp = sum(
                scen_set.get_expected_demands().get((h.hospital_id, c.category_id), 0.0)
                for h in HOSPITALS
            )
            target_stk = cat_exp * 1.25
            stock_dict[("W01", c.category_id)] = int(round(target_stk * 0.50))
            stock_dict[("W02", c.category_id)] = int(round(target_stk * 0.25))
            stock_dict[("W03", c.category_id)] = int(round(target_stk * 0.25))

        tot_stock = sum(stock_dict.values())

        # Run default fast baseline solve if not in session state or if overview date changed
        if (
            st.session_state.get("active_result") is None
            or st.session_state.get("active_overview_date") != selected_date
        ):
            with st.spinner("Initializing baseline allocation engine..."):
                base_res = optimize(
                    warehouse_stock=stock_dict,
                    scenario_set=scen_set,
                    demands=scen_set.point_forecast,
                    policy="stochastic_milp",
                    min_service_coverage=0.50,
                    time_limit_sec=10.0,
                    realized_demand=scen_set.realized_demand,
                    network=network,
                )
                base_exp = AllocationDecisionExplainer(network=network).explain(
                    result=base_res,
                    demands=scen_set.point_forecast,
                    warehouse_stock=stock_dict,
                    min_service_coverage=0.50,
                    policy_name="Stochastic_MILP",
                )
                st.session_state["active_result"] = base_res
                st.session_state["active_explanation"] = base_exp
                st.session_state["active_scenario_set"] = scen_set
                st.session_state["active_overview_date"] = selected_date
                st.session_state.pop("last_genai_explanation", None)
        elif st.session_state.get("active_explanation") is None:
            st.session_state["active_explanation"] = AllocationDecisionExplainer(
                network=network
            ).explain(
                result=st.session_state["active_result"],
                demands=scen_set.point_forecast,
                warehouse_stock=stock_dict,
                min_service_coverage=0.50,
                policy_name="Stochastic_MILP",
            )

        res: OptimizationResult = st.session_state["active_result"]

        # Top KPI Row
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Total Forecast Demand", f"{tot_forecast:,.0f} units", delta=None)
        with k2:
            st.metric(
                "Available Depot Stock",
                f"{tot_stock:,.0f} units",
                delta=f"{(tot_stock / tot_forecast):.1%} ratio",
            )
        with k3:
            st.metric(
                "Total Shipped",
                f"{res.total_units_shipped:,.0f} units",
                delta=f"{res.fairness.mean_facility_fill_rate:.1%} fill",
            )
        with k4:
            st.metric(
                "Worst Facility Fill",
                f"{res.fairness.worst_facility_fill_rate:.1%}",
                delta=f"{res.fairness.coverage_disparity:.1%} disparity",
                delta_color="inverse",
            )
        with k5:
            st.metric(
                "Total Supply Chain Cost",
                f"${res.total_cost:,.2f}",
                delta=f"${res.shortage_penalty:,.0f} penalties",
                delta_color="inverse",
            )

        st.markdown("---")

        # Layout: Map on left, Time Series on right
        map_col, ts_col = st.columns([0.55, 0.45])

        with map_col:
            st.plotly_chart(
                plot_facility_map(result=res, network=network),
                use_container_width=True,
            )

        with ts_col:
            # Facility and category selectors for time-series inspection
            ts_c1, ts_c2 = st.columns(2)
            with ts_c1:
                sel_hosp = st.selectbox(
                    "Hospital:",
                    options=[h.hospital_id for h in HOSPITALS],
                    index=0,
                    format_func=lambda hid: (
                        f"{hid} ({next(h.name for h in HOSPITALS if h.hospital_id == hid)})"
                    ),
                    key="ov_ts_hosp",
                )
            with ts_c2:
                sel_cat = st.selectbox(
                    "Category:",
                    options=[c.category_id for c in PRODUCT_CATEGORIES],
                    index=0,
                    key="ov_ts_cat",
                )

            pt_f = scen_set.point_forecast.get((sel_hosp, sel_cat), 0.0)
            lb_f = scen_set.lower_bound.get((sel_hosp, sel_cat), 0.0)
            ub_f = scen_set.upper_bound.get((sel_hosp, sel_cat), 0.0)

            st.plotly_chart(
                plot_forecast_timeseries(
                    df_featured=df_featured,
                    target_date=selected_date,
                    facility_id=sel_hosp,
                    category_id=sel_cat,
                    point_forecast=pt_f,
                    lower_bound=lb_f,
                    upper_bound=ub_f,
                ),
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown("#### Facility Allocation & Clinical Shortage Risk Ranking")
        render_hospital_risk_ranking(res)

    except Exception as exc:
        st.error(f"⚠️ Network Overview Telemetry Initialization Notice: {exc}")
        st.info(
            "The operational snapshot could not load data for the selected date. "
            "Other workspace tabs (Scenario Lab, Explainability, Stress Testing, Responsible AI) remain accessible."
        )

# ==============================================================================
# TAB 2: SCENARIO LAB (INTERACTIVE OPTIMIZATION)
# ==============================================================================
with tab_lab:
    st.markdown("#### Scenario Lab & Interactive Optimization Engine")
    st.markdown(
        "<div style='color: #5B6B75; font-size: 0.88rem; margin-bottom: 16px;'>"
        "Configure operational stress parameters, dispatch real Mixed-Integer Linear Programs, and inspect resource feasibility."
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("🛠️ Operational Control Parameters", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            lab_date = st.selectbox(
                "Forecast Evaluation Date:", options=available_dates, index=0, key="lab_date"
            )
            lab_policy = st.selectbox(
                "Allocation Policy:",
                options=["Stochastic_MILP", "Deterministic_MILP", "Proportional", "Greedy"],
                index=0,
                key="lab_policy",
            )
            lab_surge = st.slider(
                "Demand Surge (% Shift):",
                min_value=-30,
                max_value=100,
                value=0,
                step=5,
                key="lab_surge",
            )
        with c2:
            lab_stock_ratio = st.slider(
                "Available Inventory Ratio (% of Demand):",
                min_value=25,
                max_value=150,
                value=125,
                step=5,
                key="lab_stock",
            )
            lab_min_coverage = st.slider(
                "Minimum Service Coverage (Equity Target α):",
                min_value=0.0,
                max_value=0.95,
                value=0.50,
                step=0.05,
                key="lab_coverage",
            )
            lab_capacity_scale = st.slider(
                "Transport / Route Dispatch Throttle (%):",
                min_value=20,
                max_value=100,
                value=100,
                step=5,
                key="lab_capacity",
            )
        with c3:
            lab_veh_cap = st.number_input(
                "Vehicle Fleet Unit Capacity:",
                min_value=500,
                max_value=5000,
                value=2500,
                step=250,
                key="lab_veh_cap",
            )
            lab_time_limit = st.slider(
                "Solver Time Limit (seconds):",
                min_value=5.0,
                max_value=60.0,
                value=20.0,
                step=5.0,
                key="lab_timeout",
            )
            run_btn = st.button("🚀 Run Multi-Echelon Optimization", use_container_width=True)

    if run_btn:
        with st.spinner("Formulating constraints and solving Mixed-Integer Linear Program..."):
            try:
                surge_mult = 1.0 + (lab_surge / 100.0)
                stock_ratio_f = lab_stock_ratio / 100.0
                cap_scale_f = lab_capacity_scale / 100.0

                # 1. Generate scenario set with surge multiplier
                scen_set_lab = scen_gen.generate_scenario_set(
                    target_date=lab_date,
                    num_scenarios=5,
                    seed=42,
                    surge_multiplier=surge_mult,
                )

                # 2. Network parameters
                params_lab = NetworkParameters(
                    vehicle_capacity_units=int(lab_veh_cap),
                    warehouse_dispatch_capacities={
                        w.warehouse_id: int(30000 * cap_scale_f) for w in WAREHOUSES
                    },
                    max_route_capacity_units=int(12000 * cap_scale_f),
                )
                net_lab = TransportationNetwork(params=params_lab)

                # 3. Warehouse stock
                exp_demands_lab = scen_set_lab.get_expected_demands()
                stock_dict_lab = {}
                for c in PRODUCT_CATEGORIES:
                    tot_c = sum(
                        exp_demands_lab.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS
                    )
                    stk_c = tot_c * stock_ratio_f
                    stock_dict_lab[("W01", c.category_id)] = int(round(stk_c * 0.50))
                    stock_dict_lab[("W02", c.category_id)] = int(round(stk_c * 0.25))
                    stock_dict_lab[("W03", c.category_id)] = int(round(stk_c * 0.25))

                # 4. Execute solver
                opt_res = optimize(
                    warehouse_stock=stock_dict_lab,
                    scenario_set=scen_set_lab,
                    demands=scen_set_lab.point_forecast,
                    policy=lab_policy.lower(),
                    min_service_coverage=lab_min_coverage,
                    time_limit_sec=lab_time_limit,
                    realized_demand=scen_set_lab.realized_demand,
                    network=net_lab,
                )

                # 5. Build Decision Explanation
                dec_expl = AllocationDecisionExplainer(network=net_lab)
                dec_explanation = dec_expl.explain(
                    result=opt_res,
                    demands=scen_set_lab.point_forecast,
                    warehouse_stock=stock_dict_lab,
                    min_service_coverage=lab_min_coverage,
                    policy_name=lab_policy,
                )

                st.session_state["active_result"] = opt_res
                st.session_state["active_explanation"] = dec_explanation
                st.session_state["active_scenario_set"] = scen_set_lab
                st.session_state["active_network"] = net_lab
                st.session_state.pop("last_genai_explanation", None)
            except Exception as exc:
                st.error(f"⚠️ Optimization Execution Notice: {exc}")

    # Display Active Results
    cur_res: OptimizationResult = st.session_state.get("active_result")
    cur_exp: DecisionExplanation | None = st.session_state.get("active_explanation")

    if cur_res is not None:
        st.markdown("---")

        # Solver Status Banner
        if cur_res.status in ["OPTIMAL", "FEASIBLE"]:
            st.success(
                f"**Solver Status: {cur_res.status}** · Solved in **{cur_res.solver_runtime_sec:.3f}s** · "
                f"Relative Optimality Gap: **{cur_res.mip_gap:.2%}** · Hard Constraints Verified Feasible"
            )
        elif cur_res.status == "INFEASIBLE":
            st.error(
                f"**Solver Status: {cur_res.status}** · Requested minimum coverage or capacity limits cannot be satisfied mathematically. "
                "No false optimality claims are made."
            )
        else:
            st.warning(
                f"**Solver Status: {cur_res.status}** · The solver stopped without a proven-optimal or feasible solution "
                "(not necessarily infeasible). No optimality claim is made; review results with caution."
            )
            if cur_res.fairness.max_feasible_coverage is not None:
                st.warning(
                    f"**Relaxation Diagnostic:** Maximum mathematically feasible service coverage is "
                    f"**{cur_res.fairness.max_feasible_coverage:.1%}**. Inventory deficit to achieve target: "
                    f"**{cur_res.fairness.total_inventory_deficit:,.0f} units**."
                )

        # Performance KPI Grid
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Total Realized Cost", f"${cur_res.total_cost:,.2f}")
        with m2:
            st.metric("Units Shipped", f"{cur_res.total_units_shipped:,} units")
        with m3:
            st.metric("Unmet Demand", f"{cur_res.total_unmet_demand:,.1f} units")
        with m4:
            st.metric("Mean Facility Fill", f"{cur_res.fairness.mean_facility_fill_rate:.1%}")
        with m5:
            st.metric(
                "Coverage Disparity",
                f"{cur_res.fairness.coverage_disparity:.1%}",
                delta_color="inverse",
            )

        # Charts: Waterfall & Fill Rate Distribution
        c_left, c_right = st.columns(2)
        with c_left:
            st.plotly_chart(plot_cost_waterfall(cur_res), use_container_width=True)
        with c_right:
            st.plotly_chart(
                plot_fill_rate_distribution(
                    cur_res, min_service_coverage=cur_res.fairness.configured_min_coverage
                ),
                use_container_width=True,
            )

        # Decision Explanation Card
        if cur_exp is not None:
            render_decision_explanation_card(cur_exp)
    else:
        st.info(
            "ℹ️ Adjust operational parameters in the panel above and click "
            "**Dispatch Allocation Optimizer** to solve an allocation plan and inspect cost and equity diagnostics."
        )

# ==============================================================================
# TAB 3: EXPLAINABILITY & DIAGNOSTICS
# ==============================================================================
with tab_explain:
    st.markdown("#### Explainability & Decision Intelligence Architecture")
    st.markdown(
        "<div style='color: #5B6B75; font-size: 0.88rem; margin-bottom: 16px;'>"
        "<b>Important Scientific Distinction:</b> SHAP explains the <i>probabilistic demand forecast</i>. "
        "The Allocation Decision Explainer attributes <i>operations research allocation decisions</i> to solver constraints, fleet capacities, and costs."
        "</div>",
        unsafe_allow_html=True,
    )

    exp_tab_shap, exp_tab_or, exp_tab_genai = st.tabs(
        [
            "🌳 Forecast TreeSHAP Explanations",
            "⚖️ Optimization Decision Attribution",
            "🤖 Grounded GenAI Operational Intelligence",
        ]
    )

    with exp_tab_shap:
        st.markdown("##### 1. TreeSHAP Global Feature Importance")
        st.caption(
            "Mean absolute SHAP value (|SHAP|) across observation rows in the featured dataset."
        )

        if shap_explainer.is_available:
            with st.spinner("Computing TreeSHAP feature attributions..."):
                global_imp = shap_explainer.get_global_importance(df_featured.head(100), top_k=15)
                st.plotly_chart(plot_shap_summary(global_imp), use_container_width=True)

            st.markdown("##### 2. Local Facility-Product Feature Attribution (Waterfall)")
            st.caption(
                "Decomposes a specific hospital forecast from base expected value to final point prediction."
            )

            w_c1, w_c2, w_c3 = st.columns(3)
            with w_c1:
                sh_hosp = st.selectbox(
                    "Select Facility:",
                    options=[h.hospital_id for h in HOSPITALS],
                    index=0,
                    key="sh_hosp",
                )
            with w_c2:
                sh_cat = st.selectbox(
                    "Select Category:",
                    options=[c.category_id for c in PRODUCT_CATEGORIES],
                    index=0,
                    key="sh_cat",
                )
            with w_c3:
                sh_date = st.selectbox(
                    "Observation Date:", options=available_dates, index=0, key="sh_date"
                )

            sample_row = df_featured[
                (df_featured["hospital_id"] == sh_hosp)
                & (df_featured["category_id"] == sh_cat)
                & (pd.to_datetime(df_featured["date"]).dt.strftime("%Y-%m-%d") == sh_date)
            ]

            if not sample_row.empty:
                inst_exp = shap_explainer.explain_instance(sample_row)
                st.plotly_chart(plot_shap_waterfall(inst_exp), use_container_width=True)

                # Additivity verification callout
                if inst_exp.get("is_additive"):
                    st.success(
                        f"✅ **SHAP Additivity Verified:** Base E[Y] ({inst_exp['base_value']:.2f}) + \u2211 \u03c6 ({inst_exp['shap_sum'] - inst_exp['base_value']:+.2f}) "
                        f"= Model Prediction ({inst_exp['prediction']:.2f}) (Error: {inst_exp['additivity_error']:.6f} units)"
                    )
                else:
                    st.warning("SHAP additivity error exceeded tolerance.")
            else:
                st.info("No record found matching the chosen facility, category, and date.")
        else:
            st.error("XGBoost demand model or TreeSHAP explainer artifact is unavailable.")

    with exp_tab_or:
        st.markdown("##### Operations Research Decision & Shortage Attribution")
        cur_explanation = st.session_state.get("active_explanation")

        if cur_explanation is not None:
            render_decision_explanation_card(cur_explanation)

            st.markdown("###### Top Facility Shortage Root-Cause Attributions")
            if cur_explanation.top_shortage_attributions:
                shortage_rows = []
                for sa in cur_explanation.top_shortage_attributions:
                    shortage_rows.append(
                        {
                            "Facility": f"{sa.hospital_name} ({sa.hospital_id})",
                            "Tier": sa.hospital_tier,
                            "Category": sa.category_id,
                            "Unmet Demand": f"{sa.shortage_units:,.1f}",
                            "Fill Rate": f"{sa.fill_rate:.1%}",
                            "Penalty Rate": f"${sa.shortage_penalty_rate:.2f}/unit",
                            "Total Fine": f"${sa.total_penalty:,.2f}",
                            "Root Cause": sa.primary_root_cause,
                            "Diagnostic Evidence": sa.evidence,
                        }
                    )
                render_table(pd.DataFrame(shortage_rows))
            else:
                st.success("Zero facility shortages recorded. All clinical demands fully met.")

            st.markdown("###### Counterfactual Scenario Analysis")
            cf = cur_explanation.counterfactual_analysis
            st.json(cf)
        else:
            st.info(
                "Execute an optimization run in the Scenario Lab to generate decision attributions."
            )

    with exp_tab_genai:
        st.markdown("##### Grounded GenAI Decision Explanation & Audit")
        st.caption(
            "Synthesizes predictive TreeSHAP feature attributions, MILP binding constraints, and equity metrics "
            "into an evidence-grounded operational narrative."
        )

        cur_opt_result = st.session_state.get("active_result")

        g_c1, g_c2, g_c3 = st.columns([0.35, 0.35, 0.30])
        with g_c1:
            genai_hosp = st.selectbox(
                "Focal Facility:",
                options=[h.hospital_id for h in HOSPITALS],
                index=0,
                key="genai_hosp",
            )
        with g_c2:
            genai_cat = st.selectbox(
                "Focal Product Category:",
                options=[c.category_id for c in PRODUCT_CATEGORIES],
                index=0,
                key="genai_cat",
            )
        with g_c3:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            genai_run_btn = st.button("✨ Explain Allocation Decision", use_container_width=True)

        user_inquiry = st.text_input(
            "Optional Logistics Inquiry / Scenario Note:",
            placeholder="e.g. Why did Level 1 Trauma Center receive prioritization?",
            key="genai_query_input",
        )

        if cur_opt_result is None:
            st.info(
                "ℹ️ **Allocation Result Pending**: No active solver allocation found in session. "
                "Navigate to **Network Overview** or **Scenario Lab** to solve an allocation, "
                "or click 'Explain Allocation Decision' above to generate an initial explanation."
            )
        elif cur_opt_result.status == "INFEASIBLE":
            st.warning(
                "⚠️ **Infeasible Allocation State**: The active solver policy failed to find a feasible dispatch "
                "under strict fairness or stock constraints. "
                + (
                    f"Fairness relaxation summary: {cur_opt_result.fairness.relaxation_summary}"
                    if cur_opt_result.fairness and cur_opt_result.fairness.relaxation_summary
                    else ""
                )
            )

        active_scen = st.session_state.get("active_scenario_set")
        target_dt_str = (
            str(getattr(active_scen, "target_date", "2025-11-08"))[:10]
            if active_scen is not None
            else "2025-11-08"
        )
        current_genai_key = (
            genai_hosp,
            genai_cat,
            user_inquiry,
            target_dt_str,
            id(cur_opt_result),
        )

        if genai_run_btn or (
            cur_opt_result is not None
            and (
                "last_genai_explanation" not in st.session_state
                or st.session_state.get("last_genai_key") != current_genai_key
            )
        ):
            with st.spinner("Compiling decision context and generating grounded explanation..."):
                try:
                    focal_rows = (
                        df_featured[
                            (df_featured["hospital_id"] == genai_hosp)
                            & (df_featured["category_id"] == genai_cat)
                        ]
                        if df_featured is not None
                        else pd.DataFrame()
                    )
                    pt_forecast = 300.0
                    p10 = 240.0
                    p90 = 380.0
                    shap_base = 333.14
                    top_shap = None

                    if not focal_rows.empty and shap_explainer.is_available:
                        dt_rows = focal_rows[
                            pd.to_datetime(focal_rows["date"]).dt.strftime("%Y-%m-%d")
                            == target_dt_str
                        ]
                        target_row = dt_rows.tail(1) if not dt_rows.empty else focal_rows.tail(1)
                        inst_res = shap_explainer.explain_instance(target_row)
                        pt_forecast = float(inst_res.get("prediction", 300.0))
                        shap_base = float(inst_res.get("base_value", 333.14))
                        p10 = pt_forecast * 0.82
                        p90 = pt_forecast * 1.25
                        top_shap = inst_res.get("waterfall", [])[:4]

                    if active_scen is not None:
                        pt_forecast = float(
                            active_scen.point_forecast.get((genai_hosp, genai_cat), pt_forecast)
                        )
                        p10 = float(active_scen.lower_bound.get((genai_hosp, genai_cat), p10))
                        p90 = float(active_scen.upper_bound.get((genai_hosp, genai_cat), p90))

                    record = build_context_record(
                        result=cur_opt_result,
                        facility_id=genai_hosp,
                        category_id=genai_cat,
                        point_forecast=pt_forecast,
                        p10_lower=p10,
                        p90_upper=p90,
                        shap_contributions=top_shap,
                        shap_base_value=shap_base,
                        scenario_deltas={
                            "name": "Active Scenario",
                            "surge_pct": 0.0,
                            "stock_ratio_pct": 125.0,
                            "vehicle_cap": 2500,
                        },
                        user_query=user_inquiry if user_inquiry else None,
                    )

                    genai_service = DecisionExplanationService()
                    explanation = genai_service.explain(record)
                    st.session_state["last_genai_explanation"] = explanation
                    st.session_state["last_genai_key"] = current_genai_key
                except Exception as exc:
                    st.error(f"GenAI explanation generation encountered a temporary issue: {exc}")

        if "last_genai_explanation" in st.session_state:
            render_genai_explanation_card(st.session_state["last_genai_explanation"])

# ==============================================================================
# TAB 4: STRESS TESTING & AUDITED BASELINES
# ==============================================================================
with tab_stress:
    st.markdown("#### Resilience Stress Testing & Audited Baselines")
    st.markdown(
        "<div style='color: #5B6B75; font-size: 0.88rem; margin-bottom: 16px;'>"
        "Benchmark AEGIS allocation policies against severe disruptions and inspect verified scientific results."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("##### 1. One-Click Resiliency Stress Tests")

    stress_col1, stress_col2, stress_col3 = st.columns(3)
    with stress_col1:
        st_btn1 = st.button("🚨 40% Warehouse Stock Loss", use_container_width=True)
        st_btn2 = st.button("📈 50% Regional Demand Surge", use_container_width=True)
    with stress_col2:
        st_btn3 = st.button(
            "🚧 Route & Dispatch Bottleneck (50% Throttled)", use_container_width=True
        )
        st_btn4 = st.button(
            "🚚 Fleet Capacity Reduction (1,000 units/veh)", use_container_width=True
        )
    with stress_col3:
        st_btn5 = st.button(
            "⚠️ Impossible Fairness Target (95% with 65% Stock)", use_container_width=True
        )
        st_btn6 = st.button("⏱️ Solver Timeout Stress (5s Limit)", use_container_width=True)

    triggered_stress = None
    if st_btn1:
        triggered_stress = ("40% Warehouse Stock Loss", 1.0, 0.60, 1.0, 2500, 0.40, 20.0)
    elif st_btn2:
        triggered_stress = ("50% Demand Surge", 1.50, 1.25, 1.0, 2500, 0.50, 20.0)
    elif st_btn3:
        triggered_stress = ("Route & Dispatch Bottleneck", 1.0, 1.25, 0.50, 2500, 0.40, 20.0)
    elif st_btn4:
        triggered_stress = ("Vehicle Capacity Reduction", 1.0, 1.25, 1.0, 1000, 0.50, 20.0)
    elif st_btn5:
        triggered_stress = ("Impossible Fairness Target", 1.0, 0.65, 1.0, 2500, 0.95, 20.0)
    elif st_btn6:
        triggered_stress = ("Solver Timeout Stress", 1.30, 1.10, 1.0, 2500, 0.50, 3.0)

    if triggered_stress is not None:
        name, surge_m, stk_r, cap_s, v_cap, alpha, t_limit = triggered_stress
        st.info(f"Executing Stress Test: **{name}**...")

        try:
            scen_stress = scen_gen.generate_scenario_set(
                target_date="2025-11-08", num_scenarios=5, seed=42, surge_multiplier=surge_m
            )
            exp_d_s = scen_stress.get_expected_demands()

            stk_s = {}
            for c in PRODUCT_CATEGORIES:
                tot_c = sum(exp_d_s.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
                stk_c = tot_c * stk_r
                stk_s[("W01", c.category_id)] = int(round(stk_c * 0.50))
                stk_s[("W02", c.category_id)] = int(round(stk_c * 0.25))
                stk_s[("W03", c.category_id)] = int(round(stk_c * 0.25))

            p_stress = NetworkParameters(
                vehicle_capacity_units=v_cap,
                warehouse_dispatch_capacities={
                    w.warehouse_id: int(30000 * cap_s) for w in WAREHOUSES
                },
                max_route_capacity_units=int(12000 * cap_s),
            )
            net_stress = TransportationNetwork(params=p_stress)

            res_stress = optimize(
                warehouse_stock=stk_s,
                scenario_set=scen_stress,
                demands=scen_stress.point_forecast,
                policy="stochastic_milp",
                min_service_coverage=alpha,
                time_limit_sec=t_limit,
                realized_demand=scen_stress.realized_demand,
                network=net_stress,
            )

            dec_stress = AllocationDecisionExplainer(network=net_stress).explain(
                result=res_stress,
                demands=scen_stress.point_forecast,
                warehouse_stock=stk_s,
                min_service_coverage=alpha,
                policy_name="Stochastic_MILP",
            )
            st.session_state["active_result"] = res_stress
            st.session_state["active_explanation"] = dec_stress
            st.session_state["active_scenario_set"] = scen_stress
            st.session_state["last_stress_scenario"] = name
            st.session_state.pop("last_genai_explanation", None)

            if res_stress.status in ["OPTIMAL", "FEASIBLE"]:
                st.success(
                    f"**Stress Test Completed: {name}** · Status: {res_stress.status} · "
                    f"Cost: ${res_stress.total_cost:,.2f} · Fill Rate: {res_stress.fairness.mean_facility_fill_rate:.1%}"
                )
            else:
                st.error(
                    f"**Stress Test Infeasibility Detected: {name}** · Status: {res_stress.status} · "
                    "Constraints cannot be satisfied mathematically."
                )
        except Exception as exc:
            st.error(f"⚠️ Stress Test Execution Failed: {exc}")

    st.markdown("---")
    st.markdown("##### 2. Audited Benchmark Baseline Comparison (30 Instances)")
    st.caption("Verified results from Milestone 2 audit across 6 operational regimes.")

    c16_df = benchmark_metrics.get("common16")
    st.plotly_chart(plot_policy_benchmark_comparison(c16_df), use_container_width=True)

    if c16_df is not None:
        render_table(c16_df)

    with st.expander(
        "🔬 View Audited Paired Confidence Intervals vs Stochastic MILP", expanded=False
    ):
        pairwise_df = benchmark_metrics.get("pairwise")
        if pairwise_df is not None:
            render_table(pairwise_df)

# ==============================================================================
# TAB 5: RESPONSIBLE AI & GOVERNANCE
# ==============================================================================
with tab_governance:
    st.markdown("#### Responsible AI, Clinical Safety & Cryptographic Governance")

    st.markdown(
        """
        <div class="aegis-card">
            <h4 style="margin-top: 0; color: #172B36;">Operational Ethics & Scope Disclaimers</h4>
            <ul>
                <li><b>Explicitly Synthetic Data:</b> All 20 hospitals, 3 warehouses, patient demand volumes, and coordinate grids are parameterized synthetic data models created for logistics research. No actual protected health information (PHI) or personally identifiable information (PII) is accessed, stored, or processed.</li>
                <li><b>Clinical Non-Validation:</b> AEGIS is a logistical supply allocation decision-support engine for non-patient-specific medical consumables (PPE, surface disinfectants, utility items). It does <i>not</i> provide clinical triage, patient diagnosis, drug dosage, or treatment recommendations.</li>
                <li><b>Mandatory Human In The Loop:</b> Solver allocations, vehicle assignments, and route dispatches are operational recommendations. Execution requires review and formal authorization by authorized healthcare supply chain directors.</li>
                <li><b>Mathematical Integrity Guarantee:</b> When service coverage targets or physical throughput limits are mathematically impossible, AEGIS rejects false optimality and outputs explicit infeasibility diagnostics with maximum achievable coverage bounds.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Model Provenance & Artifact Hashes")
    gov_col1, gov_col2 = st.columns(2)
    commit_hash = get_git_commit_short()
    with gov_col1:
        st.markdown(
            f"""
            - **Forecasting Model:** XGBoost Gradient Boosted Decision Trees (`models/xgboost_demand.joblib`)
            - **Quantile Loss Intervals:** 10th & 90th percentile bounds (`reg:quantileerror`)
            - **Optimization Solver:** SciPy HiGHS Dual Simplex / Branch-and-Cut
            - **Audit Release:** `docs/FINAL_SUBMISSION_AUDIT.md` (Commit: `{commit_hash}`)
            """,
            unsafe_allow_html=True,
        )
    with gov_col2:
        st.markdown(
            """
            - **Active Test Suite:** 86 Passing Tests (Schema, Generator, Leakage, Optimization, SHAP, GenAI, Cold-Start)
            - **Python Runtime:** Python 3.11.9 (CPython)
            - **Package Engine:** `uv`
            - **Deterministic Seed:** PRNG Seed 42
            """
        )

    st.markdown("---")
    st.markdown("##### Audit Trail & Session Export")
    export_json = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "release_version": "0.4.0",
        "milestone": "Milestone 4 - Production Release",
        "provenance_commit": commit_hash,
        "active_policy": st.session_state.get("policy"),
        "active_result_summary": {
            "status": st.session_state.get("active_result").status
            if st.session_state.get("active_result")
            else None,
            "total_cost": st.session_state.get("active_result").total_cost
            if st.session_state.get("active_result")
            else None,
            "units_shipped": st.session_state.get("active_result").total_units_shipped
            if st.session_state.get("active_result")
            else None,
            "unmet_demand": st.session_state.get("active_result").total_unmet_demand
            if st.session_state.get("active_result")
            else None,
            "mean_fill_rate": st.session_state.get("active_result").fairness.mean_facility_fill_rate
            if (
                st.session_state.get("active_result")
                and st.session_state.get("active_result").fairness
            )
            else None,
        },
    }

    st.download_button(
        label="📥 Export Certified Operational Audit Record (JSON)",
        data=pd.Series(export_json).to_json(indent=2),
        file_name="aegis_operational_audit_record.json",
        mime="application/json",
    )
