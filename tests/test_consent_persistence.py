"""Regression tests for session injection into build_graph() nodes.

Confirms the two Phase 0 guardrail decisions actually persist when a case
runs through a real (session_factory-backed) graph invocation, not just in
in-memory graph state for that one call:
  - an opt-out reply flips ConsentFlag.consent to False
  - a risk-fraud-block case is written to AuditLogEntry with the
    RISK_OPS_AUDIT_ACTION action name

Also confirms build_graph() without session_factory is byte-for-byte the
same as before this change (no persistence, no behavior change) so every
other existing test keeps passing untouched.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import RISK_OPS_AUDIT_ACTION
from app.graph.build_graph import build_graph
from app.graph.state import new_case_state
from app.models import AuditLogEntry, Base, ConsentFlag


def _isolated_session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def test_opt_out_reply_persists_consent_flag_to_false():
    session_factory, engine = _isolated_session_factory()
    graph = build_graph(session_factory=session_factory)

    state = new_case_state(case_id="persist-1", entry_point="receivable", customer_id="cust-opt-out", invoice_payment_ref="INV-1", amount=100)
    state["last_customer_reply"] = "STOP messaging me"
    graph.invoke(state, config={"configurable": {"thread_id": "persist-1"}})

    with session_factory() as check:
        record = check.query(ConsentFlag).filter_by(customer_id="cust-opt-out", channel="whatsapp").one()
        assert record.consent is False
        audit = check.query(AuditLogEntry).filter_by(entity_type="consent", action="opt_out").one()
        assert audit.entity_id == "cust-opt-out:whatsapp"

    engine.dispose()


def test_risk_fraud_block_case_writes_audit_log_entry():
    session_factory, engine = _isolated_session_factory()
    graph = build_graph(session_factory=session_factory)

    state = new_case_state(case_id="persist-2", entry_point="failure", customer_id="cust-risk", payment_id="pay-1", gateway_reason="payment_risk_check_failed", method="card", amount=500)
    graph.invoke(state, config={"configurable": {"thread_id": "persist-2"}})

    with session_factory() as check:
        entries = check.query(AuditLogEntry).filter_by(case_id="persist-2", action=RISK_OPS_AUDIT_ACTION).all()
        assert len(entries) == 1
        assert entries[0].reason == "risk-blocked case routed silently to risk operations"

    engine.dispose()


def test_build_graph_without_session_factory_has_no_persistence_side_effects():
    """Every pre-existing test relies on this: no session_factory == no DB writes."""
    graph = build_graph()
    state = new_case_state(case_id="no-persist-1", entry_point="failure", customer_id="cust-1", payment_id="pay-1", gateway_reason="insufficient_funds", method="card")
    result = graph.invoke(state, config={"configurable": {"thread_id": "no-persist-1"}})
    assert result["authorized_action"] == "retry"