"""Deterministic execution adapter for authorized provider actions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.graph.state import RecoveryState
from app.integrations.razorpay_client import RazorpayClient
from app.integrations.twilio_whatsapp_client import TwilioWhatsAppClient
from app.models.retry_attempt import RetryAttempt


def _result_text(result: Any) -> str:
    if hasattr(result, "reason"):
        return f"{getattr(result, 'status', 'unknown')}: {result.reason}"
    if hasattr(result, "status"):
        return str(result.status)
    return str(result)


def _record_retry_attempt(session: Any, *, failure_event_id: str, attempt_number: int, result_text: str) -> None:
    """Persist an idempotent retry slot (PRD Section 11 — retry_attempt).

    No-op when ``session`` is ``None`` so direct unit tests and any
    ``build_graph()`` call without ``session_factory`` keep their existing
    in-memory-only behavior. Upserts on the (failure_event_id,
    attempt_number) unique slot rather than assuming it's always new, so a
    re-run against an already-logged attempt updates it instead of raising
    an IntegrityError.
    """
    if session is None or not failure_event_id:
        return
    existing = session.query(RetryAttempt).filter_by(failure_event_id=failure_event_id, attempt_number=attempt_number).one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        session.add(
            RetryAttempt(
                id=str(uuid.uuid4()),
                failure_event_id=failure_event_id,
                attempt_number=attempt_number,
                already_attempted=True,
                executed_time=now,
                result=result_text,
            )
        )
    else:
        existing.already_attempted = True
        existing.executed_time = now
        existing.result = result_text


def execution_node(
    state: RecoveryState,
    retry_callable: Callable[[RecoveryState], Any] | None = None,
    message_callable: Callable[[RecoveryState], Any] | None = None,
    *,
    razorpay_client: RazorpayClient | None = None,
    whatsapp_client: TwilioWhatsAppClient | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Execute only the action independently authorized by Policy Engine.

    Provider clients default to dry-run instances through Phase 0 config. Tests
    can inject clients or callbacks without network access.
    """

    action = state.get("authorized_action")
    now = datetime.now(timezone.utc).isoformat()
    if action is None:
        return {"execution_result": "not_authorized", "updated_at": now}

    if action == "retry":
        if state.get("already_attempted_flag"):
            return {"execution_result": "skipped_already_handled", "updated_at": now}
        if retry_callable:
            result = retry_callable(state)
        else:
            client = razorpay_client or RazorpayClient()
            payment_id = state.get("payment_id")
            if not payment_id:
                return {"execution_result": "retry_rejected_missing_payment_id", "updated_at": now}
            result = client.retry_payment(payment_id)
        skipped = bool(getattr(result, "skipped", False))
        result_text = _result_text(result)
        _record_retry_attempt(
            session,
            failure_event_id=state.get("event_id") or state.get("case_id", ""),
            attempt_number=state.get("retry_count", 0) + 1,
            result_text=result_text,
        )
        return {
            "already_attempted_flag": True,
            "retry_count": state.get("retry_count", 0) + (0 if skipped else 1),
            "execution_result": result_text,
            "outcome": "pending" if not skipped else "do_nothing",
            "updated_at": now,
        }

    if action in {"notify", "nudge", "negotiate"}:
        if message_callable:
            result = message_callable(state)
        else:
            client = whatsapp_client or TwilioWhatsAppClient()
            recipient = state.get("customer_phone", "")
            body = state.get("draft_message", "")
            if not recipient or not body:
                return {"execution_result": "message_rejected_missing_recipient_or_body", "updated_at": now}
            result = client.send_message(recipient, body)
        return {"contact_count": state.get("contact_count", 0) + 1, "execution_result": _result_text(result), "updated_at": now}

    if action == "risk_ops_flag":
        return {"execution_result": "risk_ops_flagged", "outcome": "escalated", "outcome_reason": "risk-blocked case routed to risk operations", "updated_at": now}
    if action == "escalate":
        return {"execution_result": "escalated", "outcome": "escalated", "updated_at": now}
    return {"execution_result": "do_nothing", "outcome": "do_nothing", "updated_at": now}


execute_action = execution_node