from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "http://localhost:8000"


class RevoraAPIError(RuntimeError):
    """Raised when the Revora API cannot return a usable response."""


class RevoraAPIClient:
    """Small requests-based client for the local Revora API."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0) -> None:
        self.base_url = (base_url or os.getenv("REVORA_API_URL", DEFAULT_API_URL)).rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    detail = response.json().get("detail", "")
                except (ValueError, AttributeError):
                    detail = response.text
            suffix = f": {detail}" if detail else ""
            raise RevoraAPIError(f"{method} {path} failed{suffix}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RevoraAPIError(f"{method} {path} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RevoraAPIError(f"{method} {path} returned an unexpected response")
        return payload

    def get_case(self, case_id: str) -> dict[str, Any]:
        return self._request("GET", f"/cases/{case_id}")

    def submit_case(self, entry_point: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/cases/{entry_point}", json=payload)

    def confirm_payment(self, case_id: str) -> dict[str, Any]:
        return self._request("POST", f"/cases/{case_id}/confirm-payment")


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


def _case_id_from_response(response: dict[str, Any]) -> str | None:
    case_id = response.get("case_id")
    return str(case_id) if case_id else None


def _render_case_state(state: dict[str, Any], *, st: Any) -> None:
    """Render the operational fields returned by either POST or GET /cases/{id}."""
    st.subheader(f"Case {state.get('case_id', 'unknown')}")
    summary = st.columns(4)
    summary[0].metric("Root cause", state.get("root_cause_category") or "—")
    summary[1].metric("PTP state", state.get("ptp_state") or "—")
    summary[2].metric("Proposed action", state.get("proposed_action") or "—")
    summary[3].metric("Authorized action", state.get("authorized_action") or "—")

    details = {
        "customer_id": state.get("customer_id"),
        "entry_point": state.get("entry_point"),
        "amount": state.get("amount"),
        "currency": state.get("currency"),
        "diagnosis_reason": state.get("diagnosis_reason"),
        "action_reason": state.get("action_reason"),
        "escalation_trigger": state.get("escalation_trigger"),
        "consent_checked": state.get("consent_checked"),
        "contact_allowed": state.get("contact_allowed"),
        "promised_date": state.get("promised_date"),
        "outcome": state.get("outcome"),
        "outcome_reason": state.get("outcome_reason"),
        "execution_result": state.get("execution_result"),
    }
    st.json(details)

    with st.expander("Audit trail", expanded=True):
        audit_trail = state.get("audit_trail") or []
        if audit_trail:
            st.dataframe(audit_trail, use_container_width=True, hide_index=True)
        else:
            st.info("No audit events recorded for this case.")

    with st.expander("Full live graph state"):
        st.json(state)


def _submit_form(entry_point: str, label: str, fields: list[tuple[str, str, Any]], *, st: Any, client: RevoraAPIClient) -> None:
    with st.form(f"submit_{entry_point}_form", clear_on_submit=False):
        values: dict[str, Any] = {}
        for name, field_label, default in fields:
            if isinstance(default, int):
                values[name] = st.number_input(field_label, min_value=0, value=default, step=1, key=f"{entry_point}_{name}")
            elif isinstance(default, float):
                values[name] = st.number_input(field_label, min_value=0.0, value=default, step=0.01, format="%.2f", key=f"{entry_point}_{name}")
            else:
                values[name] = st.text_input(field_label, value=default, key=f"{entry_point}_{name}")
        submitted = st.form_submit_button(label)

    if submitted:
        try:
            response = client.submit_case(entry_point, values)
            case_id = _case_id_from_response(response)
            if case_id:
                st.session_state["last_case_id"] = case_id
            st.success(f"{entry_point.title()} case processed: {case_id or 'response received'}")
            state = response.get("state")
            if isinstance(state, dict):
                _render_case_state({"case_id": case_id, **state}, st=st)
            else:
                st.json(response)
        except RevoraAPIError as exc:
            st.error(str(exc))


def render_case_submission_forms(*, st: Any, client: RevoraAPIClient) -> None:
    st.subheader("Submit a case")
    st.caption(f"Live API: {client.base_url}")
    failure, checkout, receivable = st.tabs(["Failure", "Checkout abandonment", "Receivable"])

    with failure:
        _submit_form(
            "failure",
            "Process failure case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("payment_id", "Payment ID", "payment-demo"),
                ("amount", "Amount", 1000.0),
                ("currency", "Currency", "INR"),
                ("method", "Payment method", "upi"),
                ("gateway_code", "Gateway code (optional)", ""),
                ("gateway_reason", "Gateway reason (optional)", ""),
            ],
            st=st,
            client=client,
        )

    with checkout:
        _submit_form(
            "checkout",
            "Process checkout case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("cart_id", "Cart ID", "cart-demo"),
                ("cart_value", "Cart value", 1000.0),
                ("currency", "Currency", "INR"),
                ("funnel_stage_reached", "Funnel stage reached", "payment"),
                ("prior_abandonment_count", "Prior abandonment count", 0),
            ],
            st=st,
            client=client,
        )

    with receivable:
        _submit_form(
            "receivable",
            "Process receivable case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("invoice_payment_ref", "Invoice/payment reference", "invoice-demo"),
                ("amount", "Amount", 1000.0),
                ("currency", "Currency", "INR"),
            ],
            st=st,
            client=client,
        )


def render_live_case_viewer(*, st: Any, client: RevoraAPIClient, default_case_ids: list[str]) -> None:
    st.subheader("Fully traced case")
    st.caption("Case state is fetched live from the persisted graph checkpoint.")
    default_case_id = st.session_state.get("last_case_id", default_case_ids[0] if default_case_ids else "")
    case_id = st.text_input("Case ID", value=default_case_id, key="live_case_id")
    if st.button("Refresh case", type="secondary"):
        if not case_id.strip():
            st.warning("Enter a case ID first.")
            return
        try:
            response = client.get_case(case_id.strip())
            state = response.get("state")
            if isinstance(state, dict):
                _render_case_state({"case_id": response.get("case_id", case_id.strip()), **state}, st=st)
            else:
                st.json(response)
        except RevoraAPIError as exc:
            st.error(str(exc))

    st.divider()
    st.caption("Demo recovery: this records a payment-provider confirmation; it does not charge a customer.")
    if st.button("Confirm payment and mark recovered", type="primary"):
        if not case_id.strip():
            st.warning("Enter a case ID first.")
            return
        try:
            response = client.confirm_payment(case_id.strip())
            st.success("Payment confirmed. Case marked as recovered without escalation.")
            state = response.get("state")
            if isinstance(state, dict):
                _render_case_state({"case_id": response.get("case_id", case_id.strip()), **state}, st=st)
            else:
                st.json(response)
        except RevoraAPIError as exc:
            st.error(str(exc))


def render_dashboard(report: dict[str, Any], *, st: Any | None = None, client: RevoraAPIClient | None = None) -> None:
    if st is None:
        import streamlit as st
    if client is None:
        client = RevoraAPIClient()

    st.set_page_config(page_title="Revora RecoverAI", page_icon=None, layout="wide")
    st.title("Revora RecoverAI")
    st.caption("Guardrail-first payment recovery operations and evaluation dashboard")
    render_case_submission_forms(st=st, client=client)

    metrics = report.get("metrics", {})
    conditions = list(metrics)
    if not conditions:
        st.info("No evaluation report found. Run: python -m evaluation.run_batch --output evaluation/results.json")
        render_live_case_viewer(st=st, client=client, default_case_ids=[])
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

    records = report.get("results", {}).get(selected, [])
    case_ids = [str(row.get("case", {}).get("case_id")) for row in records if row.get("case", {}).get("case_id")]
    render_live_case_viewer(st=st, client=client, default_case_ids=case_ids)


def main() -> None:
    report_path = os.getenv("REVORA_EVALUATION_REPORT", "evaluation/results.json")
    render_dashboard(load_report(report_path))


if __name__ == "__main__":
    main()
