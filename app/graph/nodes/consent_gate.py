"""
Consent Gate node — deterministic (PRD Section 6.1, simplified).

Responsibilities:
- Check the boolean consent_flag for the customer/channel
  (app/models/consent_flag.py) before any outreach.
- If consent is missing: route the case to DO NOTHING with reason
  "no consent on file" — do not fall through to Execution or
  Communication nodes.
- This node is placed so that no graph path can reach outreach
  without passing through it (see app/graph/edges/routing.py).

No implementation yet — skeleton only.
"""
"""Deterministic consent and opt-out gate."""
from __future__ import annotations
from typing import Any
from app.config import OPT_OUT_KEYWORDS
from app.graph.state import RecoveryState
from app.models.consent_flag import ConsentFlag

def _opted_out(text: str | None) -> bool:
    raw=(text or "").casefold()
    return any(keyword.casefold() in raw for keyword in OPT_OUT_KEYWORDS)

def consent_gate_node(state: RecoveryState, session: Any | None = None) -> dict[str, Any]:
    """Check channel consent before any customer outreach."""
    customer_id=state.get("customer_id", "")
    channel=state.get("channel", "whatsapp")
    consent=bool(state.get("consent_flag", False))
    if session is not None and customer_id:
        record=session.query(ConsentFlag).filter_by(customer_id=customer_id, channel=channel).one_or_none()
        if record is not None:
            consent=bool(record.consent)
    reply=state.get("last_customer_reply")
    opted_out=bool(state.get("opt_out", False) or _opted_out(reply))
    if opted_out:
        consent=False
        reason="customer opt-out received; future automated contact disabled"
    elif consent:
        reason="consent on file"
    else:
        reason="no consent on file"
    return {
        "consent_flag": consent,
        "opt_out": opted_out,
        "consent_checked": True,
        "contact_allowed": consent,
        "consent_reason": reason,
        "action_reason": reason if not consent else state.get("action_reason"),
        "outcome": "do_nothing" if not consent else state.get("outcome"),
        "outcome_reason": reason if not consent else state.get("outcome_reason"),
    }

check_consent=consent_gate_node
