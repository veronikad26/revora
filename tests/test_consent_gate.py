"""
Tests for the Consent Gate node (app/graph/nodes/consent_gate.py).

To cover: consent=false or missing -> DO NOTHING with correct reason,
no downstream Execution/Communication node is reached.

No implementation yet — skeleton only.
"""
from app.graph.nodes.consent_gate import consent_gate_node
from app.graph.state import new_case_state

def test_no_consent_blocks_outreach():
    state=new_case_state(case_id="c1",entry_point="receivable",customer_id="u1")
    result=consent_gate_node(state)
    assert result["consent_checked"] is True
    assert result["contact_allowed"] is False
    assert result["outcome"]=="do_nothing"
    assert result["consent_reason"]=="no consent on file"

def test_opt_out_is_permanent_block():
    state=new_case_state(case_id="c2",entry_point="receivable",customer_id="u1")
    state["consent_flag"]=True
    state["last_customer_reply"]="Please STOP messaging me"
    result=consent_gate_node(state)
    assert result["opt_out"] is True
    assert result["contact_allowed"] is False
