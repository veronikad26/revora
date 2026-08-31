"""Phase 7 tests for the assembled guarded RecoverAI graph."""
from app.graph.build_graph import build_graph
from app.graph.state import new_case_state


def test_assembled_graph_runs_retry_through_policy_and_observation():
    graph = build_graph()
    state = new_case_state(
        case_id="graph-retry-1",
        entry_point="failure",
        customer_id="customer-1",
        payment_id="pay-1",
        gateway_reason="insufficient_funds",
        method="card",
    )
    result = graph.invoke(state, config={"configurable": {"thread_id": "graph-retry-1"}})
    assert result["root_cause_category"] == "insufficient_balance"
    assert result["proposed_action"] == "retry"
    assert result["authorized_action"] == "retry"
    assert result["already_attempted_flag"] is True
    assert result["retry_count"] == 1
    assert result["execution_result"].startswith("retry_requested")
    assert result["learning_updates"]["observations_seen"] == 1


def test_assembled_graph_never_sends_outreach_without_consent():
    graph = build_graph()
    state = new_case_state(
        case_id="graph-contact-1",
        entry_point="receivable",
        customer_id="customer-2",
        invoice_payment_ref="INV-2",
        amount=1000,
    )
    state["proposed_action"] = "nudge"
    result = graph.invoke(state, config={"configurable": {"thread_id": "graph-contact-1"}})
    assert result["consent_checked"] is True
    assert result["contact_allowed"] is False
    assert result["authorized_action"] is None
    assert result["execution_result"] == "not_authorized"


def test_graph_checkpoint_can_resume_same_thread():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-checkpoint-1"}}
    state = new_case_state(case_id="graph-checkpoint-1", entry_point="failure", customer_id="customer-3", payment_id="pay-3", gateway_reason="server_error")
    first = graph.invoke(state, config=config)
    resumed = graph.get_state(config).values
    assert resumed["case_id"] == first["case_id"]
    assert resumed["execution_result"] == first["execution_result"]
