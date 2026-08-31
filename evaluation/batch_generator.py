"""
Synthetic batch generator (PRD Section 9.1).

Responsibilities:
- Generate 50-100 synthetic cases spanning all three entry points and
  all six root-cause categories.
- Assign each case a hidden recoverability profile (e.g. "recoverable
  with correct timing", "recoverable only via negotiation",
  "unrecoverable regardless of action") based on stated assumptions.
- Use a fixed, published random seed for exact reproducibility.
- The agent must never see the hidden profile directly.
"""
"""Deterministic synthetic cases for offline RecoverAI evaluation."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Any, Iterator


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    entry_point: str
    customer_id: str
    amount: float
    currency: str = "INR"
    payment_id: str = ""
    gateway_reason: str | None = None
    method: str | None = None
    cart_id: str | None = None
    cart_value: float | None = None
    funnel_stage_reached: str | None = None
    last_activity_at: str | None = None
    prior_abandonment_count: int = 0
    invoice_payment_ref: str | None = None
    consent_flag: bool = False
    expected_category: str = "technical_unclassified"
    expected_safe_action: str = "escalate"
    hidden_profile: str = "unrecoverable"

    def as_dict(self, *, include_hidden: bool = False) -> dict[str, Any]:
        value = asdict(self)
        if not include_hidden:
            value.pop("hidden_profile", None)
            value.pop("expected_category", None)
            value.pop("expected_safe_action", None)
        return value


_FAILURES = (
    ("insufficient_funds", "insufficient_balance", "retry", "recoverable_with_retry"),
    ("card_expired", "card_expired_invalid", "notify", "recoverable_with_customer_update"),
    ("payment_risk_check_failed", "risk_fraud_block", "risk_ops_flag", "unrecoverable"),
    ("server_error", "technical_unclassified", "escalate", "recoverable_after_support"),
    ("payment_failed", "technical_unclassified", "escalate", "unrecoverable"),
)


def generate_cases(count: int = 100, *, seed: int = 42) -> list[EvaluationCase]:
    """Generate reproducible cases while keeping labels separate from input."""
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    cases: list[EvaluationCase] = []
    for index in range(count):
        case_id = f"eval-{seed}-{index:05d}"
        customer_id = f"customer-{rng.randint(10000, 99999)}"
        if index % 3 == 0:
            reason, category, action, profile = _FAILURES[rng.randrange(len(_FAILURES))]
            amount = float(rng.choice([250, 500, 1250, 5000]))
            cases.append(EvaluationCase(case_id, "failure", customer_id, amount, payment_id=f"pay-{case_id}", gateway_reason=reason, method=rng.choice(["card", "upi"]), expected_category=category, expected_safe_action=action, hidden_profile=profile))
        elif index % 3 == 1:
            value = float(rng.choice([500, 2500, 12000, 25000]))
            hours = rng.choice([2, 6, 26, 48])
            cases.append(EvaluationCase(case_id, "abandonment", customer_id, value, cart_id=f"cart-{case_id}", cart_value=value, funnel_stage_reached=rng.choice(["cart", "address", "payment"]), last_activity_at=(now - timedelta(hours=hours)).isoformat(), prior_abandonment_count=rng.randint(0, 3), expected_category="abandoned_checkout", expected_safe_action="nudge", hidden_profile="recoverable_with_nudge" if hours >= 6 else "unrecoverable"))
        else:
            amount = float(rng.choice([1000, 5000, 25000]))
            consent = rng.choice([False, True])
            cases.append(EvaluationCase(case_id, "receivable", customer_id, amount, invoice_payment_ref=f"INV-{seed}-{index:05d}", consent_flag=consent, expected_category="overdue_invoice", expected_safe_action="notify" if consent else "escalate", hidden_profile="recoverable_with_customer_update" if consent else "unrecoverable_without_consent"))
    return cases


def iter_cases(count: int = 100, *, seed: int = 42) -> Iterator[EvaluationCase]:
    yield from generate_cases(count, seed=seed)


generate_batch = generate_cases