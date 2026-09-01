"""Standalone PTP walkthrough for demo purposes — calls nodes directly,
bypassing the graph's current outbound-only invocation limitation."""
from __future__ import annotations
from datetime import datetime, timezone
from app.graph.state import new_case_state
from app.graph.nodes.diagnosis import diagnosis_node
from app.graph.nodes.recovery_router import recovery_router_node
from app.graph.nodes.consent_gate import consent_gate_node
from app.graph.nodes.communication import communication_node
from app.graph.nodes.policy_engine import policy_engine_node
from app.graph.nodes.execution import execution_node
from app.graph.nodes.observation import observation_node
from app.integrations.gemini_client import GeminiClient, CustomerIntent

NOON = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)

def show(label, state):
    print(f"\n--- {label} ---")
    for key in ("ptp_state", "proposed_action", "authorized_action", "action_reason",
                "promised_date", "draft_message", "execution_result"):
        if state.get(key) is not None:
            print(f"  {key}: {state[key]}")

class DateAwareDemoClient(GeminiClient):
    """Dry-run client that also extracts a promise date for demo clarity."""
    def parse_customer_reply(self, reply):
        base = super().parse_customer_reply(reply)
        if "10" in reply and "pay" in reply.lower():
            return CustomerIntent(promise_date="2026-09-10", amount_acknowledged=True, raw_text=reply)
        return base

def main():
    state = new_case_state(case_id="demo-ptp-1", entry_point="receivable",
                            customer_id="cust-demo", invoice_payment_ref="INV-DEMO-1",
                            amount=1000, now=NOON)
    state["consent_flag"] = True
    state["customer_phone"] = "+919999999999"
    client = DateAwareDemoClient(dry_run=True)

    state.update(diagnosis_node(state)); show("1. Diagnosis", state)
    state.update(recovery_router_node(state)); show("2. Recovery Router", state)
    state.update(consent_gate_node(state)); show("3. Consent Gate", state)
    state.update(communication_node(state, gemini_client=client)); show("4. Communication (outbound, LLM-drafted)", state)
    state.update(policy_engine_node(state, now=NOON)); show("5. Policy Engine", state)
    state.update(execution_node(state)); show("6. Execution", state)
    state.update(observation_node(state)); show("7. Observation")

    print("\n>>> Simulating inbound WhatsApp reply: 'I will pay by the 10th' <<<")
    state["last_customer_reply"] = "I will pay by the 10th"
    state.update(communication_node(state, mode="inbound", gemini_client=client))
    show("8. Communication (inbound reply parsed)", state)

    print("\n>>> Recovery Router runs again — should now wait, not re-contact <<<")
    state.update(recovery_router_node(state))
    show("9. Recovery Router (post-promise)", state)

if __name__ == "__main__":
    main()