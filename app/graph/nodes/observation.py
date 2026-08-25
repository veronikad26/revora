"""
Observation / Audit node — deterministic (PRD Section 3.1 / Section 8.1).

Responsibilities:
- Write every decision (action, reason, actor, timestamp) to the
  append-only audit ledger BEFORE execution (app/models/audit_log_entry.py).
- After execution, capture the outcome (payment succeeded? PTP kept or
  broken? nudge converted?) as an OutcomeEvent
  (app/models/outcome_event.py).
- Surface a simplified, customer-facing version of the audit reason
  as a transparency footer alongside outbound messages
  (PRD Section 8.2).

No implementation yet — skeleton only.
"""
"""Audit-before-execution and outcome observation helpers."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from app.graph.state import RecoveryState
from app.models.audit_log_entry import AuditLogEntry
from app.models.outcome_event import OutcomeEvent

def observation_node(state: RecoveryState, session: Any | None = None)->dict[str,Any]:
    now=datetime.now(timezone.utc).isoformat()
    action=state.get("authorized_action") or state.get("proposed_action") or "do_nothing"
    reason=state.get("action_reason") or state.get("outcome_reason") or "observed case state"
    event={"action":action,"actor":"policy_engine","entity_type":"case","entity_id":state["case_id"],"reason":reason,"customer_visible_reason":None,"timestamp":now}
    update={"audit_trail":[event],"updated_at":now}
    if session is not None:
        session.add(AuditLogEntry(id=str(uuid.uuid4()),case_id=state["case_id"],entity_type="case",entity_id=state["case_id"],action=action,actor="policy_engine",reason=reason,customer_visible_reason=None,created_at=datetime.now(timezone.utc)))
        if state.get("outcome"):
            session.add(OutcomeEvent(id=str(uuid.uuid4()),case_id=state["case_id"],outcome_type=state["outcome"],observed_value=state.get("execution_result"),recovered_amount=state.get("recovered_amount"),created_at=datetime.now(timezone.utc)))
    return update

observe=observation_node
