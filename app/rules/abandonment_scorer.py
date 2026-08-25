"""
Abandoned-checkout behavioral scorer (PRD Section 5 — category 5).

Responsibilities:
- Simple rules-based scorer (thresholds + small weighted score) over:
    - time-since-cart-created
    - cart/checkout value
    - repeat-abandonment history
    - funnel stage reached
- Not an ML model or LLM — deliberately low-dimensional and
  inspectable, per PRD design principle.
- Used by the Diagnosis node in place of a decline-code lookup for
  CheckoutEvent inputs.

No implementation yet — skeleton only.
"""
"""Explainable rules-based scoring for abandoned checkouts.

The scorer is deliberately low-dimensional and deterministic. It is a
behavioral signal for diagnosis, not a prediction model and not an
 authorization to contact a customer; Consent Gate and Policy Engine remain
responsible for that decision in later phases.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class AbandonmentScore:
    """Score plus the individual signal explanations used to derive it."""

    score: float
    band: str
    signals: tuple[str, ...]

    @property
    def is_actionable(self) -> bool:
        return self.score >= 0.50

    def as_dict(self) -> dict[str, object]:
        return {"score": self.score, "band": self.band, "signals": list(self.signals), "is_actionable": self.is_actionable}


def _value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _age_hours(event: Any, now: datetime) -> float:
    last_activity = _value(event, "last_activity_at") or _value(event, "created_at")
    if last_activity is None:
        return 0.0
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return max(0.0, (now - last_activity).total_seconds() / 3600.0)


def score_checkout(event: Any, now: datetime | None = None) -> AbandonmentScore:
    """Score an event using age, cart value, repeat history, and funnel stage.

    Maximum score is 1.0. Thresholds and weights are constants in this
    function so the rule is easy to show to judges and tune in a later phase.
    """

    now = now or datetime.now(timezone.utc)
    score = 0.0
    signals: list[str] = []

    age = _age_hours(event, now)
    if age >= 24:
        score += 0.30
        signals.append("inactive for at least 24 hours (+0.30)")
    elif age >= 4:
        score += 0.20
        signals.append("inactive for at least 4 hours (+0.20)")
    elif age >= 1:
        score += 0.10
        signals.append("inactive for at least 1 hour (+0.10)")

    raw_value = _value(event, "cart_value", 0) or 0
    cart_value = float(Decimal(str(raw_value)))
    if cart_value >= 10000:
        score += 0.25
        signals.append("high-value cart at least INR 10,000 (+0.25)")
    elif cart_value >= 2500:
        score += 0.18
        signals.append("medium-value cart at least INR 2,500 (+0.18)")
    elif cart_value > 0:
        score += 0.10
        signals.append("non-zero cart value (+0.10)")

    repeats = int(_value(event, "prior_abandonment_count", 0) or 0)
    if repeats >= 2:
        score += 0.25
        signals.append("at least two prior abandonments (+0.25)")
    elif repeats == 1:
        score += 0.15
        signals.append("one prior abandonment (+0.15)")

    stage = str(_value(event, "funnel_stage_reached", "") or "").strip().lower().replace("-", "_")
    stage_weights = {
        "payment": (0.20, "reached payment stage"),
        "payment_method": (0.20, "reached payment-method stage"),
        "review": (0.15, "reached review stage"),
        "shipping": (0.10, "reached shipping stage"),
        "cart": (0.05, "reached cart stage"),
    }
    weight, label = stage_weights.get(stage, (0.0, ""))
    if weight:
        score += weight
        signals.append(f"{label} (+{weight:.2f})")

    score = round(min(1.0, score), 4)
    band = "high" if score >= 0.75 else "medium" if score >= 0.50 else "low"
    if not signals:
        signals.append("no positive abandonment signals")
    return AbandonmentScore(score, band, tuple(signals))


def calculate_abandonment_score(
    *,
    time_since_cart_created: timedelta | None = None,
    hours_since_last_activity: float | None = None,
    cart_value: Decimal | float | int = 0,
    prior_abandonment_count: int = 0,
    funnel_stage_reached: str = "",
    now: datetime | None = None,
) -> AbandonmentScore:
    """Convenience API for callers that have scalar signals instead of a model."""

    current = now or datetime.now(timezone.utc)
    if hours_since_last_activity is None:
        hours_since_last_activity = (time_since_cart_created.total_seconds() / 3600) if time_since_cart_created else 0
    event = {
        "last_activity_at": current - timedelta(hours=max(0.0, hours_since_last_activity)),
        "cart_value": cart_value,
        "prior_abandonment_count": prior_abandonment_count,
        "funnel_stage_reached": funnel_stage_reached,
    }
    return score_checkout(event, now=current)


score_abandonment = score_checkout