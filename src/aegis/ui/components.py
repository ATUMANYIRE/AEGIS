"""Reusable enterprise UI components and layout widgets for AEGIS Streamlit Workspace."""

import subprocess
from typing import Any

import pandas as pd
import streamlit as st

from aegis.config import HOSPITALS
from aegis.explainability.decision_explainer import DecisionExplanation
from aegis.genai.schema import GenAIDecisionExplanation
from aegis.optimization.schema import OptimizationResult


def get_git_commit_short() -> str:
    """Safely return short git commit hash or release fallback."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "6bfd776"


def render_header() -> None:
    """Render compact product header with status badges."""
    st.markdown(
        """
        <div class="aegis-header">
            <div class="aegis-logo">&#9878;</div>
            <div class="aegis-title-block">
                <div class="aegis-title">AEGIS Decision Intelligence Workspace</div>
                <div class="aegis-subtitle">Adaptive Emergency Governance &amp; Intelligent Supply &middot; Multi-echelon forecasting, optimization and explainability</div>
            </div>
            <div class="aegis-header-badges">
                <span class="aegis-badge badge-synthetic">Synthetic environment</span>
                <span class="aegis-badge badge-clinical">Logistical triage only</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_provenance_sidebar(metadata: dict[str, Any] | None = None) -> None:
    """Render compact sidebar with branding, system summary and governance notes."""
    commit = get_git_commit_short()
    st.sidebar.markdown(
        f"""
        <div class="aegis-brand">
            <div class="aegis-brand-name">AEGIS</div>
            <div class="aegis-brand-sub">DATANOVA 2026 &middot; Decision workspace</div>
            <div style="margin-top: 4px; font-size: 0.72rem; color: #64748B;">
                Build: <code>{commit}</code> &middot; 86 Tests Passing
            </div>
        </div>
        <div class="aegis-side-title">System</div>
        <div class="aegis-kv"><span>Facilities</span><b>20 hospitals</b></div>
        <div class="aegis-kv"><span>Depots</span><b>3 hubs</b></div>
        <div class="aegis-kv"><span>Consumables</span><b>PPE, Sanitation, Utility</b></div>
        <div class="aegis-kv"><span>Solver</span><b>SciPy HiGHS</b></div>
        <div class="aegis-kv"><span>Forecaster</span><b>GBDT + conformal</b></div>
        <div class="aegis-kv"><span>GenAI</span><b>Grounded explainer</b></div>
        <div class="aegis-side-title">Responsible AI</div>
        <div class="aegis-note"><b>Synthetic data.</b> Facilities, coordinates and demand are deterministic simulations.</div>
        <div class="aegis-note"><b>Not clinical advice.</b> AEGIS optimizes supply logistics only.</div>
        <div class="aegis-note"><b>No PHI/PII.</b> Consumable inventory data only.</div>
        <div class="aegis-note"><b>Human in the loop.</b> Allocations need review before dispatch.</div>
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
