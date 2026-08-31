from app.graph.nodes.trust_firewall import evaluate_message
from app.graph.state import new_case_state

def test_firewall_blocks_each_high_risk_pattern():
    state=new_case_state(case_id="c1",entry_point="receivable",customer_id="u1")
    assert evaluate_message("Pay invoice INV-1 immediately",state).allowed is False
    assert evaluate_message("Pay invoice INV-1 at https://evil.example",state).allowed is False
    assert evaluate_message("Share your OTP for invoice INV-1",state).allowed is False
    assert evaluate_message("Please pay today",state).allowed is False

def test_firewall_allows_referenced_non_threat_message():
    state=new_case_state(case_id="c2",entry_point="receivable",customer_id="u1")
    result=evaluate_message("Reminder: Invoice INV-4521 for INR 1000 is pending. Reply STOP anytime.",state)
    assert result.allowed is True
