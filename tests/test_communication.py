"""Phase 6 Communication node tests without live provider calls."""
from types import SimpleNamespace

import pytest

from app.graph.nodes.communication import build_message_prompt, communication_node
from app.graph.state import new_case_state
from app.integrations.gemini_client import CustomerIntent


class FakeGemini:
    def __init__(self, messages=None):
        self.messages = list(messages or ["Reminder: Invoice INV-1 for INR 500 is pending. Please open your payment app. Reply STOP anytime."])
        self.prompts = []

    def generate_message(self, prompt):
        self.prompts.append(prompt)
        return self.messages.pop(0)

    def parse_customer_reply(self, reply):
        return CustomerIntent(promise_date="2026-08-30", amount_acknowledged=True, raw_text=reply)


def base_state():
    state = new_case_state(case_id="case-comm-1", entry_point="receivable", customer_id="customer-1", amount=500, invoice_payment_ref="INV-1")
    state["proposed_action"] = "nudge"
    return state


def test_outbound_generation_passes_firewall_and_returns_draft():
    client = FakeGemini()
    result = communication_node(base_state(), gemini_client=client)
    assert result["draft_message"].startswith("Reminder")
    assert result["trust_firewall_result"] == "pass"
    assert len(result["conversation_history"]) == 1
    assert "INV-1" in client.prompts[0]
    assert "OTP/CVV" in client.prompts[0]


def test_outbound_blocked_draft_is_regenerated_then_escalated_if_still_unsafe():
    client = FakeGemini(["Pay now at https://bad.example", "Pay immediately at https://bad.example"])
    result = communication_node(base_state(), gemini_client=client)
    assert result["trust_firewall_result"] == "blocked"
    assert result["proposed_action"] == "escalate"
    assert len(client.prompts) == 2


def test_inbound_reply_is_structured():
    state = base_state()
    state["last_customer_reply"] = "I will pay on 30 August"
    result = communication_node(state, mode="inbound", gemini_client=FakeGemini())
    assert result["parsed_intent"]["promise_date"] == "2026-08-30"
    assert result["parsed_intent"]["amount_acknowledged"] is True
    assert result["dispute_flag"] is False
    assert result["conversation_history"][0]["direction"] == "in"


def test_opt_out_is_detected_before_gemini_parser():
    class MustNotParse(FakeGemini):
        def parse_customer_reply(self, reply):
            raise AssertionError("opt-out must short-circuit the LLM parser")

    state = base_state()
    state["last_customer_reply"] = "STOP, do not message me"
    result = communication_node(state, mode="inbound", gemini_client=MustNotParse())
    assert result["opt_out"] is True
    assert result["consent_flag"] is False
    assert result["contact_allowed"] is False


def test_outbound_contact_limit_escalates_without_llm_call():
    state = base_state()
    state["contact_count"] = 3
    client = FakeGemini()
    result = communication_node(state, gemini_client=client)
    assert result["proposed_action"] == "escalate"
    assert client.prompts == []


def test_invalid_communication_mode_is_rejected():
    with pytest.raises(ValueError):
        communication_node(base_state(), mode="unknown", gemini_client=FakeGemini())


def test_prompt_contains_no_execution_authority():
    prompt = build_message_prompt(base_state())
    assert "Do not claim payment was made" in prompt
    assert "Do not include URLs" in prompt
    assert "discounts" in prompt
