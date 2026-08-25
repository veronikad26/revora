"""
Tests for the Policy Engine node (app/graph/nodes/policy_engine.py).

To cover: every guardrail (retry limit, contact limit, contact hours,
consent, PTP limits, dispute/confidence status) is independently
re-checked and can reject an action regardless of what upstream nodes
proposed.

No implementation yet — skeleton only.
"""
from datetime import datetime, timezone
from app.graph.nodes.policy_engine import policy_engine_node
from app.graph.state import new_case_state

def test_policy_rejects_message_without_consent():
    state=new_case_state(case_id="c1",entry_point="receivable",customer_id="u1")
    state.update({"proposed_action":"negotiate","confidence":0.95})
    result=policy_engine_node(state,now=datetime(2026,8,26,12,tzinfo=timezone.utc))
    assert result["authorized_action"] is None
    assert "consent" in result["action_reason"]

def test_policy_authorizes_retry_with_valid_state():
    state=new_case_state(case_id="c2",entry_point="failure",customer_id="u1",gateway_reason="insufficient_funds")
    state.update({"root_cause_category":"insufficient_balance","confidence":0.95,"proposed_action":"retry"})
    result=policy_engine_node(state)
    assert result["authorized_action"]=="retry"

def test_policy_rejects_retry_after_idempotency_flag():
    state=new_case_state(case_id="c3",entry_point="failure",customer_id="u1")
    state.update({"root_cause_category":"technical_unclassified","confidence":0.95,"proposed_action":"retry","already_attempted_flag":True})
    result=policy_engine_node(state)
    assert result["authorized_action"] is None
    assert "already attempted" in result["action_reason"]
