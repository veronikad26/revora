"""
Deterministic Promise-to-Pay (PTP) state machine (PRD Section 7).

Transitions:
  DETECTED -> CONTACTED     (first outbound negotiate/notify message sent)
  CONTACTED -> NEGOTIATING  (customer replies without a firm promise)
  CONTACTED/NEGOTIATING -> PROMISED  (customer gives a promise_date)
  PROMISED -> BROKEN -> RENEGOTIATE  (once only, per PTP_MAX_RENEGOTIATIONS) -> ESCALATED
  PROMISED/RENEGOTIATE -> KEPT       (payment confirmed — not yet wired to a real
                                       payment-confirmation signal; see mark_kept)
  * -> DISPUTED -> ESCALATED (immediate, no further negotiation)

Pure functions only: nodes call these and merge the returned partial update
into graph state, so this stays independently testable and auditable.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.config import PTP_MAX_RENEGOTIATIONS


def _today(now: datetime | None) -> date:
    current = now or datetime.now(timezone.utc)
    return current.date()


def on_outbound_sent(state: dict[str, Any]) -> dict[str, Any]:
    """Advance DETECTED -> CONTACTED after a message has passed the firewall and sent."""
    if state.get("ptp_state", "DETECTED") == "DETECTED":
        return {"ptp_state": "CONTACTED"}
    return {}


def on_inbound_reply(state: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    """Advance state after a parsed customer reply."""
    current = state.get("ptp_state", "DETECTED")

    if intent.get("dispute_flag"):
        return {"ptp_state": "DISPUTED"}

    promise_date = intent.get("promise_date")
    if promise_date:
        return {"ptp_state": "PROMISED", "promised_date": promise_date}

    if current == "CONTACTED":
        return {"ptp_state": "NEGOTIATING"}
    return {}


def check_promise_status(state: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Detect a broken promise and apply the bounded renegotiation rule.

    Call this from the Recovery Router before proposing a new action, so a
    stale PROMISED case is reclassified before another action is chosen.
    """
    if state.get("ptp_state") != "PROMISED":
        return {}
    promised_date = state.get("promised_date")
    if not promised_date:
        return {}
    try:
        due = date.fromisoformat(str(promised_date)[:10])
    except ValueError:
        return {}
    if due >= _today(now):
        return {}  # not yet due

    renegotiation_count = state.get("renegotiation_count", 0)
    if renegotiation_count < PTP_MAX_RENEGOTIATIONS:
        return {
            "ptp_state": "RENEGOTIATE",
            "renegotiation_count": renegotiation_count + 1,
            "outcome_reason": "promised date passed without payment; one renegotiation permitted",
        }
    return {
        "ptp_state": "ESCALATED",
        "outcome": "broken",
        "outcome_reason": "promise broken and renegotiation limit reached",
    }


def mark_kept(state: dict[str, Any]) -> dict[str, Any]:
    """Call this once you have a real payment-confirmation signal for this case.

    Not wired to anything yet — there is no live payment-status check in the
    graph today. This exists so that step can be dropped in later without
    redesigning the state machine.
    """
    if state.get("ptp_state") in {"PROMISED", "RENEGOTIATE"}:
        return {"ptp_state": "KEPT", "outcome": "recovered"}
    return {}