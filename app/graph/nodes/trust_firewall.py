"""Single-pass deterministic outbound-message safety filter."""
from __future__ import annotations
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from app.config import TRUST_FIREWALL_MAX_REGENERATIONS
from app.graph.state import RecoveryState
from app.models.message import Message

@dataclass(frozen=True)
class FirewallResult:
    allowed: bool
    reason: str | None = None
    checks: tuple[str,...] = ()

def evaluate_message(content: str, state: RecoveryState | None = None)->FirewallResult:
    text=content or ""
    lowered=text.casefold()
    checks=[]
    if re.search(r"https?://|www\\.", text, re.I):
        return FirewallResult(False,"contains non-whitelisted link",("link",))
    if any(term in lowered for term in ("immediately","last chance","account will be suspended")):
        return FirewallResult(False,"contains urgency or threat language",("urgency",))
    if re.search(r"\b(otp|cvv|card number|bank login|bank credentials)\b", lowered):
        return FirewallResult(False,"requests sensitive authentication data",("sensitive_data",))
    # A customer-facing message must reference an invoice, order, cart, or amount.
    if not re.search(r"\b(invoice|inv[- ]?\w+|order|cart)\b|₹|\binr\b|\b\d{2,}\b", lowered, re.I):
        return FirewallResult(False,"lacks a specific verifiable reference",("reference",))
    if state:
        amount=str(state.get("amount") or state.get("cart_value") or "")
        if amount and re.search(r"(discount|fee|amount|pay)\s*(change|reduc|increase|waiv)|\bdiscount\b|\bfee\b", lowered):
            return FirewallResult(False,"proposes a change to money terms",("money_terms",))
    return FirewallResult(True,None,("link","urgency","sensitive_data","reference","money_terms"))

def trust_firewall_node(state: RecoveryState, message: str | None = None, session: Any | None = None)->dict[str,Any]:
    content=message if message is not None else state.get("draft_message","")
    result=evaluate_message(content,state)
    update={"trust_firewall_result":"pass" if result.allowed else "blocked","trust_firewall_blocked_reason":result.reason}
    if not result.allowed:
        update["trust_firewall_regenerations"]=state.get("trust_firewall_regenerations",0)+1
        if update["trust_firewall_regenerations"]>TRUST_FIREWALL_MAX_REGENERATIONS:
            update["proposed_action"]="escalate"
    if session is not None:
        session.add(Message(id=str(uuid.uuid4()),case_id=state["case_id"],direction="out",content=content,trust_firewall_result=update["trust_firewall_result"],blocked_reason=result.reason,created_at=datetime.now(timezone.utc)))
    return update

check_message=trust_firewall_node
