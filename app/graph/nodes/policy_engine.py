"""Deterministic sole authorization point before execution."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from app.config import CONTACT_HOURS, CONFIDENCE_THRESHOLD, MAX_CUSTOMER_CONTACTS, effective_retry_limit
from app.graph.state import RecoveryState
from app.models.policy_decision import PolicyDecision
from app.graph.nodes.recovery_router import load_playbooks

MESSAGE_ACTIONS={"notify","nudge","negotiate","ptp_log"}
def policy_engine_node(state: RecoveryState, session: Any | None = None, now: datetime | None = None)->dict[str,Any]:
    action=state.get("proposed_action") or "do_nothing"
    reason="authorized"
    authorized=True
    confidence=state.get("confidence")
    if action in MESSAGE_ACTIONS:
        if not state.get("consent_checked") or not state.get("consent_flag") or not state.get("contact_allowed"):
            authorized=False; reason="outreach rejected: consent gate has not authorized this channel"
        elif state.get("opt_out"):
            authorized=False; reason="outreach rejected: customer opted out"
        elif state.get("contact_count",0)>=MAX_CUSTOMER_CONTACTS:
            authorized=False; reason="outreach rejected: customer contact limit reached"
        else:
            current=now or datetime.now(timezone.utc)
            hour=current.hour
            if not CONTACT_HOURS[0] <= hour < CONTACT_HOURS[1]:
                authorized=False; reason="outreach rejected: outside permitted contact hours"
    if action=="retry":
        category=state.get("root_cause_category") or "technical_unclassified"
        limit=effective_retry_limit(int(load_playbooks().get("playbooks",{}).get(category,{}).get("retry_limit",0)))
        if state.get("retry_count",0)>=limit:
            authorized=False; reason=f"retry rejected: category limit {limit} reached"
        elif state.get("already_attempted_flag"):
            authorized=False; reason="retry rejected: already attempted"
        elif confidence is None or confidence<CONFIDENCE_THRESHOLD:
            authorized=False; reason="retry rejected: confidence below threshold"
    if action=="risk_ops_flag":
        reason="risk-blocked case routed silently to risk operations"
    if state.get("dispute_flag"):
        authorized=False; reason="action rejected: explicit dispute requires human escalation"
    result={"authorized_action":action if authorized else None,"action_reason":reason}
    if not authorized:
        result["proposed_action"]="escalate"
        result["outcome"]="escalated"
    if session is not None:
        session.add(PolicyDecision(id=str(uuid.uuid4()),case_id=state["case_id"],action_proposed=action,proposing_node="recovery_router",authorized=authorized,reason=reason,created_at=datetime.now(timezone.utc)))
    return result

authorize_action=policy_engine_node
