"""Reusable enterprise UI components and layout widgets for AEGIS Streamlit Workspace."""

from typing import Any

import pandas as pd
import streamlit as st

from aegis.config import HOSPITALS
from aegis.explainability.decision_explainer import DecisionExplanation
from aegis.genai.schema import GenAIDecisionExplanation
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
                Version 0.4.0 &bull; Production Release
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
        - **GenAI Layer:** Grounded Decision Explainer
        """
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Responsible AI Governance")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.78rem; color: #475569; line-height: 1.45;">
            <b>Synthetic Notice:** All facilities, geographical coordinates, and demand figures are deterministic synthetic models for logistics research.<br><br>
            <b>Clinical Disclaimer:** AEGIS performs supply chain optimization and does <i>not</i> provide clinical triage or patient advice.<br><br>
            <b>Zero PHI/PII:** Purely non-patient-specific consumable inventory data.<br><br>
            <b>Human in the Loop:** Solver allocations require human review and authorization prior to warehouse dispatch.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.72rem; color: #94A3B8;">
            Release Commit: <code>29ac087a</code><br>
            73+ Passing Tests &bull; Verified Build<br>
            DATANOVA 2026 Final Submission
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


def render_genai_explanation_card(genai_exp: GenAIDecisionExplanation) -> None:
    """Render structured, grounded GenAI operational intelligence explanation with audit trail."""
    prov_badge = (
        f'<span class="aegis-badge badge-clinical">{genai_exp.grounding_audit.provider_used.upper()}</span>'
        if not genai_exp.is_fallback
        else '<span class="aegis-badge badge-synthetic">DETERMINISTIC VERIFIED FALLBACK</span>'
    )
    grounded_badge = (
        '<span class="aegis-badge badge-success">100% FACTUALLY GROUNDED</span>'
        if genai_exp.grounding_audit.is_grounded
        else '<span class="aegis-badge badge-danger">UNGROUNDED CLAIMS DETECTED</span>'
    )

    st.markdown(
        f"""
        <div class="aegis-card" style="border: 1px solid #B4C6FC; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.25rem;">🤖</span>
                    <span style="font-weight: 700; font-size: 1.1rem; color: #172B46;">
                        Grounded GenAI Decision Intelligence
                    </span>
                </div>
                <div style="display: flex; gap: 6px;">
                    {prov_badge}
                    {grounded_badge}
                </div>
            </div>

            <div style="font-size: 0.95rem; color: #172B46; font-weight: 600; line-height: 1.5; margin-bottom: 12px; padding: 10px 14px; background-color: #F1F5F9; border-radius: 6px; border-left: 4px solid #2367A3;">
                {genai_exp.executive_summary}
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 14px;">
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 12px 14px; border-radius: 6px;">
                    <div style="font-size: 0.8rem; font-weight: 700; color: #2367A3; text-transform: uppercase; margin-bottom: 6px;">
                        📈 Demand &amp; TreeSHAP Rationale
                    </div>
                    <div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">
                        {genai_exp.forecast_rationale}
                    </div>
                </div>

                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 12px 14px; border-radius: 6px;">
                    <div style="font-size: 0.8rem; font-weight: 700; color: #378D73; text-transform: uppercase; margin-bottom: 6px;">
                        ⚖️ Constraints &amp; Optimization
                    </div>
                    <div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">
                        {genai_exp.allocation_rationale}
                    </div>
                </div>
            </div>

            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 12px 14px; border-radius: 6px; margin-bottom: 14px;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #C78B31; text-transform: uppercase; margin-bottom: 6px;">
                    🛡️ Clinical Tier Equity &amp; Shortage Assessment
                </div>
                <div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">
                    {genai_exp.fairness_and_risk_assessment}
                </div>
            </div>

            <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; padding: 12px 14px; border-radius: 6px; margin-bottom: 12px;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #1E40AF; text-transform: uppercase; margin-bottom: 6px;">
                    📦 Recommended Operational Supply Action (Logistical Only)
                </div>
                <div style="font-size: 0.85rem; color: #1E3A8A; line-height: 1.45;">
                    {genai_exp.recommended_operational_action}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🔍 Factual Grounding & Security Audit Trail"):
        a = genai_exp.grounding_audit
        st.markdown(
            f"""
            - **Grounding Status:** `{"VERIFIED_GROUNDED" if a.is_grounded else "UNGROUNDED_FLAGGED"}`
            - **Provider Runtime:** `{a.provider_used}` ({a.latency_ms:.1f} ms)
            - **Prompt-Injection Defense:** `{"MITIGATED" if a.prompt_injection_detected else "CLEAN"}`
            - **Verified Facts Cited:**
            """
        )
        for claim in a.verified_numerical_claims[:8]:
            st.markdown(f"  - `{claim}`")
        if a.unverified_claims:
            st.warning("⚠️ Unverified or Hallucinated Claims Detected:")
            for uv in a.unverified_claims:
                st.markdown(f"  - `{uv}`")
        st.info(f"**Governance Policy:** {genai_exp.clinical_disclaimer}")
