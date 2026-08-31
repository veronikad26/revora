"""
Execution node(s) — deterministic (PRD Section 3.1 / 6.2).

Responsibilities:
- Carry out an action already authorized by the Policy Engine:
    - retry a payment (via app/integrations/razorpay_client.py),
      checking the already_attempted flag first (simplified idempotency)
    - send a WhatsApp message (via app/integrations/twilio_whatsapp_client.py)
    - log a PTP record
    - flag a case to the risk-ops queue (silent, no messaging)
    - do nothing (still logged as a first-class action)
- Never executes anything that was not explicitly authorized by
  policy_engine.py.

No implementation yet — skeleton only.
"""
"""Deterministic execution adapter for authorized provider actions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.graph.state import RecoveryState
from app.integrations.razorpay_client import RazorpayClient
from app.integrations.twilio_whatsapp_client import TwilioWhatsAppClient


def _result_text(result: Any) -> str:
    if hasattr(result, "reason"):
        return f"{getattr(result, 'status', 'unknown')}: {result.reason}"
    if hasattr(result, "status"):
        return str(result.status)
    return str(result)


def execution_node(
    state: RecoveryState,
    retry_callable: Callable[[RecoveryState], Any] | None = None,
    message_callable: Callable[[RecoveryState], Any] | None = None,
    *,
    razorpay_client: RazorpayClient | None = None,
    whatsapp_client: TwilioWhatsAppClient | None = None,
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
        return {
            "already_attempted_flag": True,
            "retry_count": state.get("retry_count", 0) + (0 if skipped else 1),
            "execution_result": _result_text(result),
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