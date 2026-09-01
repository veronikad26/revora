from datetime import datetime, timedelta, timezone

from app.graph.build_graph import build_graph
from app.graph.nodes.communication import communication_node
from app.graph.nodes.closed_loop_update import closed_loop_update_node
from app.graph.state import new_case_state
from app.integrations.gemini_client import GeminiClient
from evaluation.metrics import summarize_results


class BadThenGoodGemini:
    def __init__(self):
        self.calls = 0

    def generate_message(self, prompt):
        self.calls += 1
        return "Pay immediately at https://bad.example" if self.calls == 1 else "Please open your payment app for invoice INV-1. Reply STOP anytime."

    def parse_customer_reply(self, reply):
        raise AssertionError("not used")


def test_compiled_graph_routes_inbound_reply_to_promised():
    graph = build_graph()
    state = new_case_state(case_id="inbound-1", entry_point="receivable", customer_id="c1", amount=100, invoice_payment_ref="INV-1")
    state.update({"ptp_state": "CONTACTED", "last_customer_reply": "I will pay on 2099-01-15", "pending_event": "inbound_reply"})
    result = graph.invoke(state, config={"configurable": {"thread_id": "inbound-1"}})
    assert result["ptp_state"] == "PROMISED"
    assert result["pending_event"] is None
    assert result["parsed_intent"]["promise_date"] == "2099-01-15"


def test_compiled_graph_routes_payment_reply_to_kept():
    graph = build_graph()
    state = new_case_state(case_id="kept-1", entry_point="receivable", customer_id="c1", amount=100, invoice_payment_ref="INV-1")
    state.update({"ptp_state": "PROMISED", "promised_date": "2099-01-15", "last_customer_reply": "Payment done", "pending_event": "inbound_reply"})
    result = graph.invoke(state, config={"configurable": {"thread_id": "kept-1"}})
    assert result["ptp_state"] == "KEPT"


def test_router_handles_renegotiation_and_dispute():
    from app.graph.nodes.recovery_router import recovery_router_node
    old = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    renegotiate = recovery_router_node({"ptp_state": "PROMISED", "promised_date": old, "renegotiation_count": 0})
    assert renegotiate["ptp_state"] == "RENEGOTIATE"
    dispute = recovery_router_node({"ptp_state": "DISPUTED"})
    assert dispute["proposed_action"] == "escalate"


def test_firewall_blocks_then_regenerates():
    result = communication_node(
        {"case_id": "fw", "proposed_action": "notify", "amount": 100, "invoice_payment_ref": "INV-1", "contact_count": 0},
        gemini_client=BadThenGoodGemini(),
    )
    assert result["trust_firewall_result"] == "pass"
    assert "https://" not in result["draft_message"]


def test_closed_loop_changes_confidence_and_timing():
    state = {"case_id": "learn", "root_cause_category": "insufficient_balance", "outcome": "escalated", "learning_updates": {}}
    result = closed_loop_update_node(state)
    assert result["learning_updates"]["confidence_adjustments"]["insufficient_balance"] < 0
    assert result["retry_delay_multiplier"] > 1.0


def test_false_interventions_include_consent_confidence_and_risk():
    rows = [
        {"strategy": "naive", "action": "notify", "case": {"amount": 10, "consent_flag": False, "expected_category": "overdue_invoice"}},
        {"strategy": "naive", "action": "retry", "case": {"amount": 10, "confidence": 0.4, "expected_category": "technical_unclassified"}},
        {"strategy": "naive", "action": "retry", "case": {"amount": 10, "consent_flag": True, "expected_category": "risk_fraud_block", "expected_safe_action": "risk_ops_flag"}},
    ]
    summary = summarize_results(rows)
    assert summary["false_intervention_count"] == 3
    assert set(summary["false_intervention_reasons"]) == {"consent_violation", "confidence_threshold_violation", "risk_fraud_block_violation"}