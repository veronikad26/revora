"""Deterministic outcome feedback loop for confidence and retry timing."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from app.graph.state import RecoveryState
from app.models.outcome_event import OutcomeEvent


def closed_loop_update_node(state: RecoveryState, session: Any | None = None) -> dict[str, Any]:
    outcomes: list[str] = []
    if session is not None:
        outcomes.extend(row.outcome_type for row in session.query(OutcomeEvent).filter_by(case_id=state["case_id"]).all())
    if state.get("outcome"):
        outcomes.append(str(state["outcome"]))
    counts = dict(Counter(outcomes))
    category = state.get("root_cause_category") or "unknown"
    previous = dict(state.get("learning_updates") or {})
    confidence_adjustments = dict(previous.get("confidence_adjustments") or {})
    timing = dict(previous.get("retry_delay_multipliers") or {})
    old_delta = float(confidence_adjustments.get(category, 0.0))
    outcome = str(state.get("outcome") or "")
    if outcome == "recovered" or state.get("payment_confirmed"):
        delta = min(0.20, old_delta + 0.02)
        delay = max(0.75, float(timing.get(category, 1.0)) - 0.05)
    elif outcome in {"broken", "escalated"}:
        delta = max(-0.20, old_delta - 0.03)
        delay = min(1.50, float(timing.get(category, 1.0)) + 0.10)
    else:
        delta = old_delta
        delay = float(timing.get(category, 1.0))
    confidence_adjustments[category] = round(delta, 4)
    timing[category] = round(delay, 4)
    updated_at = datetime.now(timezone.utc).isoformat()
    updates = {"observations_seen": len(outcomes), "outcome_counts": counts, "confidence_adjustments": confidence_adjustments, "retry_delay_multipliers": timing, "last_category": category, "last_outcome": outcome or None, "updated_at": updated_at}
    return {"learning_updates": updates, "retry_delay_multiplier": timing[category], "updated_at": updated_at}


update_from_outcomes = closed_loop_update_node