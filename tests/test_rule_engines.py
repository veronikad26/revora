"""Phase 2 tests for deterministic rule engines."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.config import CONFIDENCE_THRESHOLD
from app.models.checkout_event import CheckoutEvent
from app.rules.abandonment_scorer import calculate_abandonment_score, score_checkout
from app.rules.confidence_heuristic import (
    calculate_confidence,
    is_actionable_confidence,
    score_known_reason,
)


FIXED_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_confidence_scores_are_ordered_and_explainable():
    exact = calculate_confidence(exact_match=True)
    partial = calculate_confidence(partial_match=True)
    unknown = calculate_confidence(first_seen=True)
    missing = calculate_confidence(signal_present=False)

    assert exact.score > partial.score > unknown.score > missing.score
    assert exact.match_type == "exact"
    assert exact.is_above_threshold is True
    assert unknown.is_above_threshold is False


def test_known_reason_matching_is_case_and_whitespace_insensitive():
    result = score_known_reason("  INSUFFICIENT_FUNDS ", ["insufficient_funds"])
    assert result.score == 0.95
    assert result.match_type == "exact"

    partial = score_known_reason("card_expired_extra_context", ["card_expired"])
    assert partial.match_type == "partial"
    assert partial.score < 0.95


def test_actionable_confidence_uses_phase_zero_threshold():
    assert is_actionable_confidence(CONFIDENCE_THRESHOLD) is True
    assert is_actionable_confidence(CONFIDENCE_THRESHOLD - 0.001) is False
    assert is_actionable_confidence(9.0) is True
    assert is_actionable_confidence(-1.0) is False


def test_high_value_recent_payment_stage_checkout_scores_high():
    event = CheckoutEvent(
        id="checkout-1",
        cart_id="cart-1",
        customer_id="customer-1",
        cart_value=Decimal("12000"),
        funnel_stage_reached="payment",
        created_at=FIXED_NOW - timedelta(hours=26),
        last_activity_at=FIXED_NOW - timedelta(hours=26),
        prior_abandonment_count=2,
    )
    result = score_checkout(event, now=FIXED_NOW)
    assert result.score == 1.0
    assert result.band == "high"
    assert result.is_actionable is True
    assert len(result.signals) == 4


def test_low_signal_checkout_is_low_and_deterministic():
    first = calculate_abandonment_score(
        hours_since_last_activity=0.5,
        cart_value=0,
        prior_abandonment_count=0,
        funnel_stage_reached="unknown",
        now=FIXED_NOW,
    )
    second = calculate_abandonment_score(
        hours_since_last_activity=0.5,
        cart_value=0,
        prior_abandonment_count=0,
        funnel_stage_reached="unknown",
        now=FIXED_NOW,
    )
    assert first == second
    assert first.score == 0.0
    assert first.band == "low"
    assert first.is_actionable is False
