"""Streamlit operations dashboard for Revora Phase 10."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any


def load_report(path: str | Path = "evaluation/results.json") -> dict[str, Any]:
    """Load a Phase 9 report without mutating or recomputing it."""
    report_path = Path(path)
    if not report_path.exists():
        return {"seed": None, "count": 0, "metrics": {}, "results": {}}
    return json.loads(report_path.read_text(encoding="utf-8"))


def flatten_breakdown(summary: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [{"name": name, **values} for name, values in summary.get(key, {}).items()]


def _metric(value: Any, percent: bool = False) -> str:
    if percent:
        return f"{float(value or 0) * 100:.1f}%"
    return f"₹{float(value or 0):,.2f}"


def render_dashboard(report: dict[str, Any], *, st: Any | None = None) -> None:
    if st is None:
        import streamlit as st
    st.set_page_config(page_title="Revora RecoverAI", page_icon=None, layout="wide")
    st.title("Revora RecoverAI")
    st.caption("Guardrail-first payment recovery operations and evaluation dashboard")
    metrics = report.get("metrics", {})
    conditions = list(metrics)
    if not conditions:
        st.info("No evaluation report found. Run: python -m evaluation.run_batch --output evaluation/results.json")
        return
    selected = st.sidebar.selectbox("Condition", conditions, index=conditions.index("revora") if "revora" in conditions else 0)
    current = metrics[selected]
    columns = st.columns(5)
    columns[0].metric("Cases", current.get("cases", 0))
    columns[1].metric("At risk", _metric(current.get("at_risk_amount")))
    columns[2].metric("Recovered", _metric(current.get("recovered_amount")))
    columns[3].metric("Recovery rate", _metric(current.get("recovery_rate"), percent=True))
    columns[4].metric("Escalation rate", _metric(current.get("escalation_rate"), percent=True))

    st.subheader("Condition comparison")
    comparison_rows = []
    for name, summary in metrics.items():
        comparison_rows.append({"condition": name, "cases": summary.get("cases", 0), "at_risk_amount": summary.get("at_risk_amount", 0), "recovered_amount": summary.get("recovered_amount", 0), "recovery_rate": summary.get("recovery_rate", 0), "false_intervention_rate": summary.get("false_intervention_rate", 0)})
    st.dataframe(comparison_rows, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Root-cause breakdown")
        st.dataframe(flatten_breakdown(current, "by_category"), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Entry-point breakdown")
        st.dataframe(flatten_breakdown(current, "by_entry_point"), use_container_width=True, hide_index=True)

    st.subheader("Safety and guardrails")
    safety = st.columns(4)
    safety[0].metric("Correctly withheld", current.get("correctly_withheld_count", 0))
    safety[1].metric("False interventions", current.get("false_intervention_count", 0))
    safety[2].metric("Escalations", current.get("escalation_count", 0))
    safety[3].metric("Evaluation seed", report.get("seed", "n/a"))
    st.json({"escalation_triggers": current.get("escalation_triggers", {})})

    st.subheader("Fully traced case")
    records = report.get("results", {}).get(selected, [])
    case_ids = [str(row.get("case", {}).get("case_id")) for row in records]
    if case_ids:
        case_id = st.selectbox("Case ID", case_ids)
        record = next(row for row in records if row.get("case", {}).get("case_id") == case_id)
        st.json(record)
    else:
        st.info("No case records available for this condition.")


def main() -> None:
    report_path = os.getenv("REVORA_EVALUATION_REPORT", "evaluation/results.json")
    render_dashboard(load_report(report_path))


if __name__ == "__main__":
    main()
