"""Tests for the deterministic Diagnosis node."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.graph.nodes.diagnosis import diagnosis_node, load_root_cause_rules
from app.graph.state import new_case_state
from app.models.root_cause_classification import RootCauseClassification


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_known_gateway_reason_maps_to_insufficient_balance(db_session):
    state = new_case_state(
        case_id="case-failure-1",
        entry_point="failure",
        customer_id="customer-1",
        event_id="failure-1",
        payment_id="pay-1",
        amount=Decimal("500"),
        method="card",
        gateway_reason="insufficient_funds",
        now=NOW,
    )

    update = diagnosis_node(state, session=db_session)
    db_session.commit()

    assert update["root_cause_category"] == "insufficient_balance"
    assert update["confidence"] == 0.95
    assert "insufficient_funds" in update["diagnosis_reason"]
    record = db_session.query(RootCauseClassification).one()
    assert record.event_id == "failure-1"
    assert record.category == "insufficient_balance"


def test_unknown_gateway_reason_defaults_to_low_confidence_technical():
    state = new_case_state(
        case_id="case-failure-2",
        entry_point="failure",
        customer_id="customer-2",
        gateway_reason="new_bank_reason_not_in_table",
        now=NOW,
    )

    update = diagnosis_node(state)

    assert update["root_cause_category"] == "technical_unclassified"
    assert update["confidence"] == 0.35
    assert "unrecognized" in update["diagnosis_reason"]


def test_abandoned_checkout_uses_behavioral_signals_not_gateway_reason():
    state = new_case_state(
        case_id="case-checkout-1",
        entry_point="abandonment",
        customer_id="customer-3",
        cart_id="cart-1",
        cart_value=Decimal("12000"),
        funnel_stage_reached="payment",
        last_activity_at=(NOW - timedelta(hours=26)).isoformat(),
        prior_abandonment_count=2,
        gateway_reason="card_expired",
        now=NOW,
    )

    update = diagnosis_node(state)

    assert update["root_cause_category"] == "abandoned_checkout"
    assert update["confidence"] == 0.95
    assert "behavioral abandonment score=1.0000" in update["diagnosis_reason"]
    assert "card_expired" not in update["diagnosis_reason"]


def test_receivable_is_classified_as_overdue_invoice():
    state = new_case_state(
        case_id="case-invoice-1",
        entry_point="receivable",
        customer_id="customer-4",
        invoice_payment_ref="INV-1",
        amount=1000,
        now=NOW,
    )

    update = diagnosis_node(state)

    assert update["root_cause_category"] == "overdue_invoice"
    assert update["confidence"] == 0.95


def test_rule_table_is_loaded_from_phase_zero_yaml():
    table = load_root_cause_rules()
    reasons = {item["reason"] for item in table["rules"]}
    assert table["default_category"] == "technical_unclassified"
    assert "insufficient_funds" in reasons
    assert "payment_risk_check_failed" in reasons