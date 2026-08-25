"""Phase 3 graph-state contract tests."""
import json
from datetime import datetime, timezone

import pytest

from app.graph.state import (
    ENTRY_POINTS,
    PTP_STATES,
    ROOT_CAUSE_CATEGORIES,
    new_case_state,
    validate_state,
)


def test_new_case_state_contains_all_checkpoint_fields():
    state = new_case_state(
        case_id="case-1",
        entry_point="failure",
        customer_id="customer-1",
        event_id="failure-1",
        payment_id="pay-1",
        amount=1250,
        gateway_reason="insufficient_funds",
        now=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
    )

    validate_state(state)
    assert state["case_id"] == "case-1"
    assert state["entry_point"] == "failure"
    assert state["ptp_state"] == "DETECTED"
    assert state["retry_count"] == 0
    assert state["contact_count"] == 0
    assert state["consent_flag"] is False
    assert state["conversation_history"] == []
    assert state["audit_trail"] == []
    json.dumps(state)


def test_state_constants_match_prd_taxonomy():
    assert set(ENTRY_POINTS) == {"failure", "abandonment", "receivable"}
    assert len(ROOT_CAUSE_CATEGORIES) == 6
    assert "RENEGOTIATE" in PTP_STATES
    assert "DISPUTED" in PTP_STATES
    assert "ESCALATED" in PTP_STATES


def test_validation_rejects_invalid_lifecycle_and_confidence():
    state = new_case_state(case_id="case-1", entry_point="abandonment", customer_id="customer-1")
    state["ptp_state"] = "INVALID"  # type: ignore[typeddict-item]
    with pytest.raises(ValueError, match="invalid ptp_state"):
        validate_state(state)

    state = new_case_state(case_id="case-2", entry_point="receivable", customer_id="customer-1")
    state["confidence"] = 1.1
    with pytest.raises(ValueError, match="confidence"):
        validate_state(state)


def test_validation_rejects_negative_guardrail_counters():
    state = new_case_state(case_id="case-1", entry_point="failure", customer_id="customer-1")
    state["retry_count"] = -1
    with pytest.raises(ValueError, match="retry_count"):
        validate_state(state)
