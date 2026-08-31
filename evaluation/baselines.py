"""
Baseline conditions for batch comparison (PRD Section 9.3).

Responsibilities:
- do_nothing: no intervention at all.
- naive_baseline: retry every failure blindly after a fixed delay;
  generic English reminder for receivables/abandonment; no root-cause
  routing, no consent gate, no idempotency check.
- Each baseline runs against the identical synthetic batch as Revora
  for a fair uplift comparison.
"""
"""Baseline strategies used for fair offline comparison."""
from __future__ import annotations
from typing import Any


def case_value(case: Any, key: str, default: Any = None) -> Any:
    return getattr(case, key, default) if not isinstance(case, dict) else case.get(key, default)


def do_nothing(case: Any) -> dict[str, Any]:
    return {"action": "do_nothing", "contact_count": 0, "retry_count": 0, "authorized": False, "reason": "no intervention"}


def naive_baseline(case: Any) -> dict[str, Any]:
    """Intentionally unsafe comparator: ignores diagnosis and consent."""
    entry = case_value(case, "entry_point")
    action = "retry" if entry == "failure" else "notify"
    return {"action": action, "contact_count": 1 if action == "notify" else 0, "retry_count": 1 if action == "retry" else 0, "authorized": True, "reason": "naive fixed policy"}


def guarded_baseline(case: Any) -> dict[str, Any]:
    """Simple non-LLM comparator with consent and risk safeguards."""
    entry = case_value(case, "entry_point")
    category = case_value(case, "expected_category", "technical_unclassified")
    consent = bool(case_value(case, "consent_flag", False))
    if category == "risk_fraud_block":
        action = "risk_ops_flag"
    elif entry == "failure" and category == "insufficient_balance":
        action = "retry"
    elif consent and entry in {"abandonment", "receivable"}:
        action = "nudge" if entry == "abandonment" else "notify"
    else:
        action = "escalate"
    return {"action": action, "contact_count": int(action in {"notify", "nudge"}), "retry_count": int(action == "retry"), "authorized": action not in {"escalate", "do_nothing"}, "reason": "guarded deterministic baseline"}


BASELINES = {"do_nothing": do_nothing, "naive": naive_baseline, "guarded": guarded_baseline}
