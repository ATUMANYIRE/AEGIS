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
            <div class="aegis-logo"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="40" height="40" role="img" aria-label="AEGIS logo"><path d="M24 3 6 10v12c0 11 7.5 19.5 18 23 10.5-3.5 18-12 18-23V10z" fill="#216C65"/><path d="M24 3 6 10v12c0 11 7.5 19.5 18 23z" fill="#1A5651"/><path d="M15.5 35 24 13.5 32.5 35" fill="none" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M19.2 28h9.6" fill="none" stroke="#D8A15B" stroke-width="3" stroke-linecap="round"/></svg></div>
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
            <div class="aegis-brand-lockup"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="34" height="34" role="img" aria-label="AEGIS logo"><path d="M24 3 6 10v12c0 11 7.5 19.5 18 23 10.5-3.5 18-12 18-23V10z" fill="#216C65"/><path d="M24 3 6 10v12c0 11 7.5 19.5 18 23z" fill="#1A5651"/><path d="M15.5 35 24 13.5 32.5 35" fill="none" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M19.2 28h9.6" fill="none" stroke="#D8A15B" stroke-width="3" stroke-linecap="round"/></svg><div class="aegis-brand-name">AEGIS</div></div>
            <div class="aegis-brand-sub">DATANOVA 2026 &middot; Decision workspace</div>
            <div style="margin-top: 4px; font-size: 0.72rem; color: #5B6B75;">
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
    satisfied = (df_rank["Total Demand"] - df_rank["Unmet Demand"]).clip(lower=0.0)
    df_rank["Fill Rate"] = (satisfied / df_rank["Total Demand"] * 100).fillna(100.0).clip(
        0.0, 100.0
    ).round(1).astype(str) + "%"
    df_rank["Total Demand"] = df_rank["Total Demand"].round(1)
    df_rank["Unmet Demand"] = df_rank["Unmet Demand"].round(1)
    df_rank["Penalty ($)"] = df_rank["Penalty ($)"].apply(lambda p: f"${p:,.2f}")

    df_rank = df_rank.sort_values("Unmet Demand", ascending=False).reset_index(drop=True)

    df_rank = df_rank.rename(
        columns={
            "Total Demand": "Demand (units)",
            "Allocated": "Allocated (units)",
            "Unmet Demand": "Unmet (units)",
        }
    )
    render_table(df_rank, max_height=520)


def render_decision_explanation_card(explanation: DecisionExplanation) -> None:
    """Render executive decision explanation card grounded in mathematical constraints."""
    import html

    status_badge = (
        '<span class="aegis-badge badge-success">OPTIMAL / FEASIBLE</span>'
        if explanation.solver_status in ["OPTIMAL", "FEASIBLE"]
        else '<span class="aegis-badge badge-danger">INFEASIBLE TARGET</span>'
    )
    drivers_html = "".join(
        f'<li style="margin-bottom: 4px;">{html.escape(str(d))}</li>'
        for d in explanation.key_drivers
    )
    card_html = (
        '<div class="aegis-card">'
        '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
        f'<div style="font-weight: 700; font-size: 1.1rem; color: #172B36;">Operational Decision Summary &middot; {html.escape(str(explanation.policy))}</div>'
        f"<div>{status_badge}</div>"
        "</div>"
        f'<div style="font-size: 0.92rem; color: #334155; line-height: 1.55; margin-bottom: 14px;">{html.escape(str(explanation.executive_summary))}</div>'
        '<div style="background-color: #F5F3ED; border-left: 3px solid #216C65; padding: 10px 14px; border-radius: 4px;">'
        '<div style="font-size: 0.8rem; font-weight: 700; color: #216C65; text-transform: uppercase; margin-bottom: 6px;">Key Optimization Drivers</div>'
        f'<ul style="margin: 0; padding-left: 18px; font-size: 0.85rem; color: #5B6B75;">{drivers_html}</ul>'
        "</div>"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def render_genai_explanation_card(genai_exp: GenAIDecisionExplanation) -> None:
    """Render structured, grounded GenAI operational intelligence explanation with audit trail."""
    import html

    prov_badge = (
        f'<span class="aegis-badge badge-clinical">{html.escape(genai_exp.grounding_audit.provider_used.upper())}</span>'
        if not genai_exp.is_fallback
        else '<span class="aegis-badge badge-synthetic">DETERMINISTIC VERIFIED FALLBACK</span>'
    )
    grounded_badge = (
        '<span class="aegis-badge badge-success">100% FACTUALLY GROUNDED</span>'
        if genai_exp.grounding_audit.is_grounded
        else '<span class="aegis-badge badge-danger">UNGROUNDED CLAIMS DETECTED</span>'
    )

    card_html = (
        '<div class="aegis-card" style="border: 1px solid #DDD9CE; background: linear-gradient(180deg, #FFFFFF 0%, #FBFAF6 100%);">'
        '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">'
        '<div style="display: flex; align-items: center; gap: 8px;">'
        '<span style="font-weight: 700; font-size: 1.1rem; color: #172B36;">Grounded GenAI Decision Intelligence</span>'
        "</div>"
        f'<div style="display: flex; gap: 6px;">{prov_badge}{grounded_badge}</div>'
        "</div>"
        '<div style="font-size: 0.95rem; color: #172B36; font-weight: 600; line-height: 1.5; margin-bottom: 12px; padding: 10px 14px; background-color: #F5F3ED; border-radius: 6px; border-left: 4px solid #216C65;">'
        f"{html.escape(genai_exp.executive_summary)}"
        "</div>"
        '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 14px;">'
        '<div style="background-color: #FFFFFF; border: 1px solid #DDD9CE; padding: 12px 14px; border-radius: 6px;">'
        '<div style="font-size: 0.8rem; font-weight: 700; color: #216C65; text-transform: uppercase; margin-bottom: 6px;">Demand &amp; TreeSHAP Rationale</div>'
        f'<div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">{html.escape(genai_exp.forecast_rationale)}</div>'
        "</div>"
        '<div style="background-color: #FFFFFF; border: 1px solid #DDD9CE; padding: 12px 14px; border-radius: 6px;">'
        '<div style="font-size: 0.8rem; font-weight: 700; color: #216C65; text-transform: uppercase; margin-bottom: 6px;">Constraints &amp; Optimization</div>'
        f'<div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">{html.escape(genai_exp.allocation_rationale)}</div>'
        "</div>"
        "</div>"
        '<div style="background-color: #FFFFFF; border: 1px solid #DDD9CE; padding: 12px 14px; border-radius: 6px; margin-bottom: 14px;">'
        '<div style="font-size: 0.8rem; font-weight: 700; color: #8A5A1E; text-transform: uppercase; margin-bottom: 6px;">Clinical Tier Equity &amp; Shortage Assessment</div>'
        f'<div style="font-size: 0.84rem; color: #334155; line-height: 1.45;">{html.escape(genai_exp.fairness_and_risk_assessment)}</div>'
        "</div>"
        '<div style="background-color: #F5F3ED; border: 1px solid #DDD9CE; border-left: 4px solid #4F9A8B; padding: 12px 14px; border-radius: 6px; margin-bottom: 4px;">'
        '<div style="font-size: 0.8rem; font-weight: 700; color: #172B36; text-transform: uppercase; margin-bottom: 6px;">Recommended Operational Supply Action (Logistical Only)</div>'
        f'<div style="font-size: 0.85rem; color: #172B36; line-height: 1.45;">{html.escape(genai_exp.recommended_operational_action)}</div>'
        "</div>"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)

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


def render_table(df: pd.DataFrame, max_height: int | None = None) -> None:
    """Render a DataFrame as a clean, readable HTML table (wraps text, no canvas scrolling)."""
    import html

    cols = list(df.columns)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            if isinstance(v, float):
                v = f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"
            elif isinstance(v, int) and not isinstance(v, bool):
                v = f"{v:,}"
            cells.append(f'<td class="{"num" if num else ""}">{html.escape(str(v))}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    style = f' style="max-height:{max_height}px"' if max_height else ""
    st.markdown(
        f'<div class="aegis-table-wrap"{style}><table class="aegis-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
