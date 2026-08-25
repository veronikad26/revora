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
"""Deterministic execution adapter with safe dry-run defaults."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable
from app.graph.state import RecoveryState

def execution_node(state: RecoveryState, retry_callable: Callable[[RecoveryState], Any] | None = None, message_callable: Callable[[RecoveryState], Any] | None = None)->dict[str,Any]:
    action=state.get("authorized_action")
    if action is None:
        return {"execution_result":"not_authorized"}
    if action=="retry":
        if state.get("already_attempted_flag"):
            return {"execution_result":"skipped_already_handled"}
        result=retry_callable(state) if retry_callable else "dry_run_retry"
        return {"already_attempted_flag":True,"retry_count":state.get("retry_count",0)+1,"execution_result":str(result),"updated_at":datetime.now(timezone.utc).isoformat()}
    if action in {"notify","nudge","negotiate"}:
        result=message_callable(state) if message_callable else "dry_run_message"
        return {"contact_count":state.get("contact_count",0)+1,"execution_result":str(result),"updated_at":datetime.now(timezone.utc).isoformat()}
    if action=="risk_ops_flag":
        return {"execution_result":"risk_ops_flagged","outcome":"escalated","outcome_reason":"risk-blocked case routed to risk operations"}
    if action=="escalate":
        return {"execution_result":"escalated","outcome":"escalated"}
    return {"execution_result":"do_nothing","outcome":"do_nothing"}

execute_action=execution_node
