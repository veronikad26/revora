from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests


DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_TIMEOUT_SECONDS = 60.0


class RevoraAPIError(RuntimeError):
    """Raised when the Revora API cannot return a usable response."""


class RevoraAPIClient:
    """Small requests-based client for the local Revora API."""

    def __init__(self, base_url: str | None = None, *, timeout: float | None = None) -> None:
        self.base_url = (base_url or os.getenv("REVORA_API_URL", DEFAULT_API_URL)).rstrip("/")
        configured_timeout = os.getenv("REVORA_API_CLIENT_TIMEOUT_SECONDS")
        if timeout is not None:
            self.timeout = float(timeout)
        elif configured_timeout:
            try:
                self.timeout = float(configured_timeout)
            except ValueError as exc:
                raise ValueError("REVORA_API_CLIENT_TIMEOUT_SECONDS must be a number") from exc
        else:
            self.timeout = DEFAULT_API_TIMEOUT_SECONDS
        if self.timeout <= 0:
            raise ValueError("API request timeout must be greater than zero")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RevoraAPIError(
                f"{method} {path} timed out after {self.timeout:g}s; "
                "the API may still be processing the case. Check the API log or refresh the case."
            ) from exc
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

    def grant_consent(self, case_id: str, *, channel: str = "whatsapp", consent: bool = True) -> dict[str, Any]:
        """Grant (or revoke) outreach consent for a case's customer/channel.

        For entry points whose playbook proposes notify/nudge/negotiate
        (overdue_invoice, abandoned_checkout), granting consent here is what
        re-invokes the graph server-side and drives it through Communication
        -> Trust Firewall -> Policy Engine -> Execution -- i.e. what actually
        drafts and "sends" (dry-run, no real provider) the first PTP/nudge
        message shown in the negotiation chat.
        """
        return self._request("POST", f"/cases/{case_id}/consent", json={"consent": consent, "channel": channel})

    def simulate_reply(self, case_id: str, reply_text: str) -> dict[str, Any]:
        """Feed a typed customer reply into the graph's inbound path.

        No messaging provider involved — this hits our own FastAPI route,
        which runs the exact same communication_node(mode="inbound") ->
        PTP state machine path a real inbound message would.
        """
        return self._request("POST", f"/cases/{case_id}/simulate-reply", json={"reply": reply_text})


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


def _new_demo_payment_id() -> str:
    """A fresh, collision-free default for the Failure tab's Payment ID field.

    create_failure() deliberately deduplicates on payment_id (so the same
    real-world gateway failure event is never processed twice). That's
    correct behavior, but it means a static default value like
    "payment-demo" causes every *subsequent* submission where the user
    didn't edit the field to hit the duplicate branch instead of creating
    a fresh, freshly-checkpointed case. Randomizing the default after each
    submission keeps casual repeat testing collision-free while still
    letting a user intentionally re-use a Payment ID to exercise the
    dedup path if they want to.
    """
    return f"payment-demo-{uuid.uuid4().hex[:8]}"


def _reset_failure_payment_id(*, st: Any) -> None:
    """Callback for the 'New demo Payment ID' button (see render_case_submission_forms).

    Must run as a widget on_click callback, NOT after the payment_id
    text_input has already rendered in the current script run --
    Streamlit raises StreamlitAPIException if you assign to
    st.session_state["failure_payment_id"] once that run's text_input
    with the same key has already been instantiated. Callbacks execute
    before the *next* rerun begins, so the text_input for that upcoming
    run hasn't been created yet and the assignment is safe there.
    """
    st.session_state["failure_payment_id"] = _new_demo_payment_id()


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
        "customer_phone": state.get("customer_phone"),
        "entry_point": state.get("entry_point"),
        "amount": state.get("amount"),
        "currency": state.get("currency"),
        "diagnosis_reason": state.get("diagnosis_reason"),
        "action_reason": state.get("action_reason"),
        "escalation_trigger": state.get("escalation_trigger"),
        "consent_checked": state.get("consent_checked"),
        "contact_allowed": state.get("contact_allowed"),
        "draft_message": state.get("draft_message"),
        "trust_firewall_result": state.get("trust_firewall_result"),
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


def _checkout_payload_transform(values: dict[str, Any]) -> dict[str, Any]:
    """Convert the dashboard's 'hours since last activity' input into the
    ISO timestamp the API expects.

    Without this, the checkout form silently omitted ``last_activity_at``
    entirely, so ``CheckoutRequest`` fell back to ``now`` for every
    submitted case (see ``app/api/routes.py::create_checkout``). That made
    the abandonment-scorer's largest single signal -- "inactive for at
    least 24 hours" (+0.30 of the 1.0 max score, see
    ``app/rules/abandonment_scorer.py``) -- impossible to trigger from the
    dashboard, so every demo checkout case scored below
    ``CONFIDENCE_THRESHOLD`` and was auto-escalated instead of exercising
    the actual abandoned-checkout playbook.
    """
    hours_ago = values.pop("hours_since_last_activity", 0)
    values["last_activity_at"] = (datetime.now(timezone.utc) - timedelta(hours=float(hours_ago))).isoformat()
    return values


def _submit_form(
    entry_point: str,
    label: str,
    fields: list[tuple[str, str, Any]],
    *,
    st: Any,
    client: RevoraAPIClient,
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    show_consent_toggle: bool = False,
) -> None:
    with st.form(f"submit_{entry_point}_form", clear_on_submit=False):
        values: dict[str, Any] = {}
        for name, field_label, default in fields:
            widget_key = f"{entry_point}_{name}"
            # Streamlit rejects a widget configuration that supplies both a
            # `value=` default and an already-populated session-state value.
            # This occurs for failure_payment_id because it is initialized
            # before the text input is rendered and then reused on reruns.
            # Let session state own the value after first creation.
            has_session_value = widget_key in st.session_state
            if isinstance(default, int):
                kwargs = {"min_value": 0, "step": 1, "key": widget_key}
                if not has_session_value:
                    kwargs["value"] = default
                values[name] = st.number_input(field_label, **kwargs)
            elif isinstance(default, float):
                kwargs = {
                    "min_value": 0.0,
                    "step": 0.01,
                    "format": "%.2f",
                    "key": widget_key,
                }
                if not has_session_value:
                    kwargs["value"] = default
                values[name] = st.number_input(field_label, **kwargs)
            else:
                kwargs = {"key": widget_key}
                if not has_session_value:
                    kwargs["value"] = default
                values[name] = st.text_input(field_label, **kwargs)

        grant_consent = False
        if show_consent_toggle:
            grant_consent = st.checkbox(
                "Customer has given WhatsApp consent (draft & simulate-send the first message immediately)",
                value=True,
                key=f"{entry_point}_grant_consent",
            )

        submitted = st.form_submit_button(label)

    if submitted:
        try:
            # Build a fresh payload so that Streamlit's form values are not
            # mutated accidentally.
            payload = dict(values)

            # Checkout and receivable have a consent checkbox.
            # The checkbox value must be sent to FastAPI as part of the
            # initial case request. Previously, grant_consent was collected
            # by the UI but never added to the API payload.
            if show_consent_toggle:
                payload["consent"] = grant_consent

            # Apply any case-specific payload transformation after adding
            # the consent value.
            if transform:
                payload = transform(payload)

            # Do not issue a follow-up consent graph request from inside the
            # same form submission. The initial case POST must return first;
            # immediately starting a second LangGraph run can block on the
            # previous checkpoint flush and freeze Streamlit.
            response = client.submit_case(
                entry_point,
                payload,
            )

            case_id = _case_id_from_response(response)

            if case_id:
                st.session_state["last_case_id"] = case_id

                # Force the live-case-id widget to pick up the new ID on
                # the next render instead of keeping whatever the user last
                # typed. Streamlit widget state otherwise "owns" the value
                # once the widget has rendered once with a key.
                st.session_state["live_case_id"] = case_id

            status = response.get("status")

            if status == "duplicate":
                note = response.get("note")

                message = (
                    f"{entry_point.title()} case with this identifier "
                    f"already exists: {case_id}."
                )

                if note:
                    message += f" {note}"

                st.warning(message)

            else:
                st.success(
                    f"{entry_point.title()} case processed: "
                    f"{case_id or 'response received'}"
                )

            state = response.get("state")

            # Consent is now submitted together with the initial case POST,
            # so do not trigger another graph invocation here.
            if show_consent_toggle and grant_consent and case_id:
                st.info(
                    "Customer consent was included with the case. "
                    "The case is ready for the communication/negotiation flow."
                )

            if isinstance(state, dict):
                _render_case_state(
                    {
                        "case_id": case_id,
                        **state,
                    },
                    st=st,
                )
            else:
                st.json(response)

        except RevoraAPIError as exc:
            st.error(str(exc))


def render_case_submission_forms(*, st: Any, client: RevoraAPIClient) -> None:
    st.subheader("Submit a case")
    st.caption(f"Live API: {client.base_url}")
    failure, checkout, receivable = st.tabs(["Failure", "Checkout abandonment", "Receivable"])

    with failure:
        # Seed a unique default once per session so the very first
        # submission doesn't collide with anyone else's earlier testing.
        # This assignment happens BEFORE the payment_id text_input renders
        # below, which is the one safe time to set a widget-linked
        # session_state key directly.
        if "failure_payment_id" not in st.session_state:
            st.session_state["failure_payment_id"] = _new_demo_payment_id()
        st.caption(
            "Payment ID is deduplicated server-side — resubmitting the same "
            "value returns the original case instead of creating a new one "
            "(you'll see a yellow notice instead of green). Click below for "
            "a fresh one before your next submission if needed."
        )
        st.caption("Failure cases do not require messaging; Revora handles them through **retry**.")
        st.button(
            "🔁 New demo Payment ID",
            key="regen_failure_payment_id",
            on_click=_reset_failure_payment_id,
            kwargs={"st": st},
        )
        _submit_form(
            "failure",
            "Process failure case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("payment_id", "Payment ID", st.session_state["failure_payment_id"]),
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
        st.caption(
            "\"Hours since last activity\" drives the abandonment score's biggest "
            "signal (24h+ inactivity = +0.30) — set it to 24 or more to see the "
            "case actually clear the confidence threshold instead of auto-escalating."
        )
        _submit_form(
            "checkout",
            "Process checkout case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("customer_phone", "Customer phone (used only for the simulated chat below — no real message is sent)", "+919999999999"),
                ("cart_id", "Cart ID", "cart-demo"),
                ("cart_value", "Cart value", 1000.0),
                ("currency", "Currency", "INR"),
                ("funnel_stage_reached", "Funnel stage reached", "payment"),
                ("prior_abandonment_count", "Prior abandonment count", 0),
                ("hours_since_last_activity", "Hours since last activity", 26),
            ],
            st=st,
            client=client,
            transform=_checkout_payload_transform,
            show_consent_toggle=True,
        )

    with receivable:
        st.caption(
            "Overdue-invoice cases require WhatsApp consent before Revora will "
            "negotiate. Check the box below to grant it immediately and trigger "
            "the first PTP message draft."
        )
        _submit_form(
            "receivable",
            "Process receivable case",
            [
                ("customer_id", "Customer ID", "customer-demo"),
                ("customer_phone", "Customer phone (used only for the simulated chat below — no real message is sent)", "+919999999999"),
                ("invoice_payment_ref", "Invoice/payment reference", "invoice-demo"),
                ("amount", "Amount", 1000.0),
                ("currency", "Currency", "INR"),
            ],
            st=st,
            client=client,
            show_consent_toggle=True,
        )


def _render_ptp_chat(case_id: str, *, st: Any, client: RevoraAPIClient) -> None:
    """Simulated WhatsApp negotiation — entirely local, no Twilio account
    or real message involved. The outbound leg still runs the real graph
    pipeline (consent gate -> communication/Gemini draft -> trust firewall
    -> execution) and the inbound leg runs the real
    communication_node(mode="inbound") -> PTP state machine path; only the
    actual network hop to a messaging provider is skipped.
    """
    st.markdown("#### 💬 Negotiation chat (simulated WhatsApp)")
    st.caption(
        "Runs the actual pipeline — Gemini drafts the message, the Trust "
        "Firewall checks it, and your typed reply is parsed the same way a "
        "real inbound message would be. Include an explicit date like "
        "`2026-09-10` in your reply for the PTP date to be detected."
    )

    if not case_id.strip():
        st.info("Enter a case ID above to start a negotiation.")
        return

    try:
        response = client.get_case(case_id.strip())
    except RevoraAPIError as exc:
        st.error(str(exc))
        return

    state = response.get("state", {})
    entry_point = state.get("entry_point")

    if entry_point == "failure":
        st.info("Failure cases do not require messaging; Revora handles them through **retry**. There is no negotiation chat for this case.")
        return

    if st.button("▶️ Start / refresh negotiation", key=f"start_negotiation_{case_id}"):
        if not state.get("contact_allowed"):
            try:
                consent_response = client.grant_consent(case_id.strip())
                state = consent_response.get("state", state)
            except RevoraAPIError as exc:
                st.error(f"Could not start negotiation: {exc}")
                return

    status_cols = st.columns(3)
    status_cols[0].metric("PTP state", state.get("ptp_state") or "—")
    status_cols[1].metric("Promised date", state.get("promised_date") or "—")
    status_cols[2].metric("Outcome", state.get("outcome") or "—")

    history = state.get("conversation_history") or []
    if not history:
        st.caption("No messages yet — click \"Start / refresh negotiation\" to send the first reminder.")
    for message in history:
        role = "assistant" if message.get("direction") == "out" else "user"
        with st.chat_message(role):
            st.write(message.get("content", ""))

    reply = st.chat_input("Type the customer's reply…", key=f"chat_input_{case_id}")
    consumed_reply_key = f"chat_reply_consumed_{case_id.strip()}"
    if reply:
        # Streamlit reruns the script after widget interaction. Depending on
        # the Streamlit/browser version, chat_input can still expose the same
        # submitted value during the rerun. Without a one-shot guard, the
        # code below repeatedly calls simulate_reply() and reruns forever.
        fingerprint = hashlib.sha256(
            f"{case_id.strip()}\\0{reply}".encode("utf-8")
        ).hexdigest()
        if st.session_state.get(consumed_reply_key) == fingerprint:
            # The previous run already submitted this exact reply. Keep the
            # marker while the widget still exposes the same value, so any
            # additional rerun (including a scroll-triggered rerun) remains a
            # no-op. The marker is cleared below once the widget is empty.
            return
        st.session_state[consumed_reply_key] = fingerprint
        try:
            client.simulate_reply(case_id.strip(), reply)
            st.rerun()
        except RevoraAPIError as exc:
            st.session_state.pop(consumed_reply_key, None)
            st.error(str(exc))
    else:
        # Do not keep a stale marker if the widget cleared normally.
        st.session_state.pop(consumed_reply_key, None)


def render_live_case_viewer(*, st: Any, client: RevoraAPIClient, default_case_ids: list[str]) -> None:
    st.subheader("Fully traced case")
    st.caption("Case state is fetched live from the persisted graph checkpoint.")
    default_case_id = st.session_state.get("last_case_id", "")
    if not default_case_id and default_case_ids:
        st.info("Evaluation report IDs are historical only. Submit a new case above to create a live case that can be refreshed or marked recovered.")
    case_id = st.text_input("Live API case ID", value=default_case_id, key="live_case_id")
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
    _render_ptp_chat(case_id, st=st, client=client)

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