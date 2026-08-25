"""Phase 1 persistence contract tests."""
from datetime import date, datetime, timezone
from decimal import Decimal
from app.models import AuditLogEntry, CheckoutEvent, ConsentFlag, FailureEvent, Message, OutcomeEvent, PolicyDecision, PTPRecord, RetryAttempt, RootCauseClassification

def test_all_prd_entities_persist(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all([
        FailureEvent(id="f1", payment_id="pay1", gateway_code="GATEWAY_ERROR", gateway_reason="insufficient_funds", amount=Decimal("100.00"), method="card", timestamp=now, customer_id="c1"),
        CheckoutEvent(id="ch1", cart_id="cart1", customer_id="c1", cart_value=Decimal("250.00"), funnel_stage_reached="payment", created_at=now, last_activity_at=now),
        RootCauseClassification(id="rc1", event_id="f1", event_type="failure", category="insufficient_balance", confidence=0.95, reason="exact gateway reason"),
        ConsentFlag(id="co1", customer_id="c1", channel="whatsapp", consent=True),
        RetryAttempt(id="r1", failure_event_id="f1", attempt_number=1),
        PTPRecord(id="p1", case_id="case1", customer_id="c1", invoice_payment_ref="inv1", amount=Decimal("100.00"), promised_date=date.today(), state="PROMISED"),
        Message(id="m1", case_id="case1", ptp_id="p1", direction="out", content="Invoice INV1 reference"),
        PolicyDecision(id="pd1", case_id="case1", action_proposed="message", proposing_node="router", authorized=True, reason="consent present"),
        OutcomeEvent(id="o1", case_id="case1", outcome_type="nudge_converted", observed_value="true", recovered_amount=Decimal("250.00")),
        AuditLogEntry(id="a1", case_id="case1", entity_type="case", entity_id="case1", action="message", actor="policy_engine", reason="authorized", customer_visible_reason="Invoice INV1 is due."),
    ])
    db_session.commit()
    assert db_session.query(AuditLogEntry).count() == 1
    assert db_session.query(FailureEvent).one().amount == Decimal("100.00")
    assert db_session.query(ConsentFlag).one().consent is True

def test_retry_slot_and_consent_are_unique(db_session):
    db_session.add(FailureEvent(id="f1", payment_id="pay1", amount=Decimal("1"), method="upi", timestamp=datetime.now(timezone.utc), customer_id="c1"))
    db_session.add(RetryAttempt(id="r1", failure_event_id="f1", attempt_number=1))
    db_session.commit()
    db_session.add(RetryAttempt(id="r2", failure_event_id="f1", attempt_number=1))
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
    else:
        raise AssertionError("duplicate retry slot should be rejected")
