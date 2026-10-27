"""Reusable enterprise UI components and layout widgets for AEGIS Streamlit Workspace."""

from typing import Any

import pandas as pd
import streamlit as st

from aegis.config import HOSPITALS
from aegis.explainability.decision_explainer import DecisionExplanation
from aegis.optimization.schema import OptimizationResult


def render_header() -> None:
    """Render top enterprise application header."""
    col1, col2 = st.columns([0.75, 0.25])
    with col1:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                <div style="background-color: #2367A3; color: white; width: 38px; height: 38px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem;">
                    &#9878;
                </div>
                <div>
                    <h2 style="margin: 0; padding: 0; color: #172B46; font-size: 1.55rem; font-weight: 700; letter-spacing: -0.01em;">
                        AEGIS &bull; Decision Intelligence Workspace
                    </h2>
                    <p style="margin: 0; color: #64748B; font-size: 0.85rem; font-weight: 500;">
                        Adaptive Emergency Governance &amp; Intelligent Supply &bull; Multi-Echelon Decision Engine
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div style="text-align: right; margin-top: 4px;">
                <span class="aegis-badge badge-synthetic">SYNTHETIC ENVIRONMENT</span>
                <span class="aegis-badge badge-clinical">LOGISTICAL TRIAGE ONLY</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_provenance_sidebar(metadata: dict[str, Any] | None = None) -> None:
    """Render compact enterprise sidebar with navigation, governance metadata, and system status."""
    st.sidebar.markdown(
        """
        <div style="padding: 10px 0 16px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
            <div style="font-size: 1.15rem; font-weight: 800; color: #2367A3; letter-spacing: 0.04em;">
                AEGIS CORE
            </div>
            <div style="font-size: 0.75rem; color: #64748B; font-weight: 500;">
                Version 0.3.0 &bull; Milestone 3 Workspace
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### System Telemetry")
    st.sidebar.markdown(
        """
        - **Facilities:** 20 Simulated Hospitals
        - **Depots:** 3 Fulfillment Hubs
        - **Consumables:** PPE, Sanitation, Utility
        - **Solver:** SciPy HiGHS (Branch-and-Cut)
        - **ML Model:** GBDT (Quantile Conformal)
        """
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Responsible AI Governance")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.78rem; color: #475569; line-height: 1.45;">
            <b>Synthetic Notice:</b> All facilities, geographical coordinates, and demand figures are deterministic synthetic models for logistics research.<br><br>
            <b>Clinical Disclaimer:</b> AEGIS performs supply chain optimization and does <i>not</i> provide clinical triage or patient advice.<br><br>
            <b>Human in the Loop:</b> Solver allocations require human review and authorization prior to warehouse dispatch.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.72rem; color: #94A3B8;">
            Audit Commit: <code>3098ab2d</code><br>
            62 Unit &amp; Audit Tests Passing<br>
            DATANOVA 2026 Milestone 3
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hospital_risk_ranking(result: OptimizationResult) -> None:
    """Render hospital shortage ranking table with clinical criticality tier badges."""
    hosp_dict = {h.hospital_id: h for h in HOSPITALS}

    hosp_summary = {}
    for s in result.shortages:
        if s.hospital_id not in hosp_summary:
            h_def = hosp_dict[s.hospital_id]
            hosp_summary[s.hospital_id] = {
                "Hospital": h_def.name,
                "Facility ID": s.hospital_id,
                "Tier": h_def.tier.replace("_", " "),
                "Beds": h_def.bed_capacity,
                "Total Demand": 0.0,
                "Allocated": 0,
                "Unmet Demand": 0.0,
                "Penalty ($)": 0.0,
            }
        hosp_summary[s.hospital_id]["Total Demand"] += s.demand_units
        hosp_summary[s.hospital_id]["Allocated"] += s.allocated_units
        hosp_summary[s.hospital_id]["Unmet Demand"] += s.shortage_units
        hosp_summary[s.hospital_id]["Penalty ($)"] += s.shortage_penalty

    df_rank = pd.DataFrame(list(hosp_summary.values()))
    df_rank["Fill Rate"] = (df_rank["Allocated"] / df_rank["Total Demand"] * 100).fillna(
        100.0
    ).round(1).astype(str) + "%"
    df_rank["Total Demand"] = df_rank["Total Demand"].round(1)
    df_rank["Unmet Demand"] = df_rank["Unmet Demand"].round(1)
    df_rank["Penalty ($)"] = df_rank["Penalty ($)"].apply(lambda p: f"${p:,.2f}")

    df_rank = df_rank.sort_values("Unmet Demand", ascending=False).reset_index(drop=True)

    st.dataframe(
        df_rank,
        column_config={
            "Facility ID": st.column_config.TextColumn(width="small"),
            "Hospital": st.column_config.TextColumn(width="medium"),
            "Tier": st.column_config.TextColumn(width="small"),
            "Beds": st.column_config.NumberColumn(width="small"),
            "Total Demand": st.column_config.NumberColumn(format="%.1f units"),
            "Allocated": st.column_config.NumberColumn(format="%d units"),
            "Unmet Demand": st.column_config.NumberColumn(format="%.1f units"),
            "Fill Rate": st.column_config.TextColumn(width="small"),
            "Penalty ($)": st.column_config.TextColumn(width="small"),
        },
        hide_index=True,
        use_container_width=True,
    )


def render_decision_explanation_card(explanation: DecisionExplanation) -> None:
    """Render executive decision explanation card grounded in mathematical constraints."""
    status_badge = (
        '<span class="aegis-badge badge-success">OPTIMAL / FEASIBLE</span>'
        if explanation.solver_status in ["OPTIMAL", "FEASIBLE"]
        else '<span class="aegis-badge badge-danger">INFEASIBLE TARGET</span>'
    )

    st.markdown(
        f"""
        <div class="aegis-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="font-weight: 700; font-size: 1.1rem; color: #172B46;">
                    Operational Decision Summary &bull; {explanation.policy}
                </div>
                <div>{status_badge}</div>
            </div>
            <div style="font-size: 0.92rem; color: #334155; line-height: 1.55; margin-bottom: 14px;">
                {explanation.executive_summary}
            </div>
            <div style="background-color: #F8FAFC; border-left: 3px solid #2367A3; padding: 10px 14px; border-radius: 4px;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #2367A3; text-transform: uppercase; margin-bottom: 6px;">
                    Key Optimization Drivers
                </div>
                <ul style="margin: 0; padding-left: 18px; font-size: 0.85rem; color: #475569;">
                    {"".join(f'<li style="margin-bottom: 4px;">{d}</li>' for d in explanation.key_drivers)}
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
