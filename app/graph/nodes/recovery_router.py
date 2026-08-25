"""
Recovery / Guardrail Router node — deterministic (PRD Section 3.1 / 5.2).

Responsibilities:
- Look up the bounded playbook for the diagnosed root-cause category
  from app/rules/playbook_table.yaml (allowed action, retry limit,
  messaging allowed, escalation trigger).
- Below-confidence-threshold or unclassified cases are routed to
  human review here, not guessed.
- Propose the next action (retry | notify | nudge | negotiate |
  do_nothing) to be authorized later by the Policy Engine.

Not LLM-backed. No implementation yet — skeleton only.
"""
"""Deterministic root-cause playbook router."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml
from app.config import CONFIDENCE_THRESHOLD, effective_retry_limit
from app.graph.state import RecoveryState

PLAYBOOK_PATH=Path(__file__).resolve().parents[2]/"rules"/"playbook_table.yaml"
@lru_cache(maxsize=1)
def load_playbooks()->dict[str,Any]:
    with PLAYBOOK_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

def recovery_router_node(state: RecoveryState)->dict[str,Any]:
    category=state.get("root_cause_category") or "technical_unclassified"
    confidence=state.get("confidence")
    playbook=load_playbooks().get("playbooks",{}).get(category)
    if not playbook:
        return {"proposed_action":"escalate","escalation_trigger":"missing playbook","action_reason":f"no playbook configured for {category}"}
    if confidence is None or confidence < CONFIDENCE_THRESHOLD:
        return {"proposed_action":"escalate","escalation_trigger":"below confidence threshold","action_reason":f"confidence {confidence!r} is below {CONFIDENCE_THRESHOLD:.2f}"}
    proposed=playbook.get("allowed_action")
    limit=effective_retry_limit(int(playbook.get("retry_limit",0)))
    mapping={
        "retry_at_predicted_time":"retry",
        "notify_only":"notify",
        "negotiate":"negotiate",
        "single_nudge":"nudge",
        "single_safe_retry_or_refresh":"retry",
        "none":"risk_ops_flag" if category=="risk_fraud_block" else "do_nothing",
    }
    action=mapping.get(proposed,"escalate")
    if action=="retry" and state.get("retry_count",0)>=limit:
        action="escalate"
        trigger=f"retry limit reached ({limit})"
    else:
        trigger=playbook.get("escalation_trigger")
    if category=="risk_fraud_block":
        action="risk_ops_flag"
    return {"proposed_action":action,"escalation_trigger":trigger,"action_reason":f"{category} playbook proposes {action} (limit={limit})"}

route_recovery=recovery_router_node
