"""The only LLM-backed graph node: bounded communication only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.config import MAX_CUSTOMER_CONTACTS, OPT_OUT_KEYWORDS, TRUST_FIREWALL_MAX_REGENERATIONS
from app.graph.state import RecoveryState
from app.integrations.gemini_client import CustomerIntent, GeminiClient
from app.graph.nodes.trust_firewall import trust_firewall_node


OUTBOUND_ACTIONS = {"notify", "nudge", "negotiate"}


def _has_opted_out(text: str | None) -> bool:
    value = (text or "").casefold()
    return any(keyword.casefold() in value for keyword in OPT_OUT_KEYWORDS)


def _reference(state: RecoveryState) -> str:
    return str(state.get("invoice_payment_ref") or state.get("cart_id") or state.get("payment_id") or state["case_id"])


def build_message_prompt(state: RecoveryState, *, corrective: bool = False) -> str:
    """Build a constrained prompt containing only non-sensitive case facts."""

    reference = _reference(state)
    amount = state.get("amount") or state.get("cart_value") or 0
    action = state.get("proposed_action") or "notify"
    language = "friendly Hinglish or clear English"
    correction = " Previous draft failed safety review; obey every constraint exactly." if corrective else ""
    return (
        f"Write one short {language} WhatsApp message for a payment recovery case. "
        f"Reference: {reference}. Amount: INR {amount}. Action: {action}. "
        "Use only the supplied reference and amount. Do not include URLs, payment links, OTP/CVV requests, "
        "threats, urgency, discounts, fee changes, or new dates. Do not claim payment was made. "
        "Tell the customer they can open their payment app and reply STOP to opt out. "
        "Do not mention internal systems, policies, confidence, or automation." + correction
    )


def _intent_dict(intent: CustomerIntent) -> dict[str, Any]:
    return {
        "promise_date": intent.promise_date,
        "amount_acknowledged": intent.amount_acknowledged,
        "dispute_flag": intent.dispute_flag,
        "refusal": intent.refusal,
        "opt_out": intent.opt_out,
        "raw_text": intent.raw_text,
    }


def _inbound_update(state: RecoveryState, client: GeminiClient) -> dict[str, Any]:
    reply = state.get("last_customer_reply") or ""
    timestamp = datetime.now(timezone.utc).isoformat()
    if _has_opted_out(reply):
        intent = CustomerIntent(opt_out=True, raw_text=reply)
        return {
            "parsed_intent": _intent_dict(intent),
            "opt_out": True,
            "consent_flag": False,
            "contact_allowed": False,
            "consent_checked": True,
            "consent_reason": "customer opt-out received before intent parsing",
            "dispute_flag": False,
            "conversation_history": [{"direction": "in", "channel": state.get("channel", "whatsapp"), "content": reply, "timestamp": timestamp}],
        }
    intent = client.parse_customer_reply(reply)
    return {
        "parsed_intent": _intent_dict(intent),
        "opt_out": bool(intent.opt_out),
        "consent_flag": False if intent.opt_out else state.get("consent_flag", False),
        "contact_allowed": False if intent.opt_out else state.get("contact_allowed", False),
        "dispute_flag": bool(intent.dispute_flag),
        "promised_date": intent.promise_date,
        "last_customer_reply": reply,
        "conversation_history": [{"direction": "in", "channel": state.get("channel", "whatsapp"), "content": reply, "timestamp": timestamp}],
    }


def communication_node(
    state: RecoveryState,
    *,
    mode: str = "outbound",
    gemini_client: GeminiClient | None = None,
    firewall: Callable[..., dict[str, Any]] = trust_firewall_node,
) -> dict[str, Any]:
    """Generate or parse communication without granting execution authority."""

    client = gemini_client or GeminiClient()
    if mode == "inbound":
        return _inbound_update(state, client)
    if mode != "outbound":
        raise ValueError("mode must be 'inbound' or 'outbound'")
    if state.get("contact_count", 0) >= MAX_CUSTOMER_CONTACTS:
        return {"proposed_action": "escalate", "execution_result": "communication_blocked_contact_limit"}
    if state.get("opt_out"):
        return {"proposed_action": "do_nothing", "execution_result": "communication_blocked_opt_out"}
    if state.get("proposed_action") not in OUTBOUND_ACTIONS:
        return {"execution_result": "communication_not_required"}

    draft = client.generate_message(build_message_prompt(state))
    firewall_update = firewall(state, message=draft)
    if firewall_update.get("trust_firewall_result") == "blocked":
        state_for_retry = dict(state)
        state_for_retry["trust_firewall_regenerations"] = firewall_update.get("trust_firewall_regenerations", 0)
        if state_for_retry["trust_firewall_regenerations"] <= TRUST_FIREWALL_MAX_REGENERATIONS:
            draft = client.generate_message(build_message_prompt(state, corrective=True))
            firewall_update = firewall(state_for_retry, message=draft)
    if firewall_update.get("trust_firewall_result") != "pass":
        return {
            **firewall_update,
            "proposed_action": "escalate",
            "execution_result": "communication_blocked_by_trust_firewall",
        }
    return {
        "draft_message": draft,
        **firewall_update,
        "conversation_history": [{"direction": "out", "channel": state.get("channel", "whatsapp"), "content": draft, "timestamp": datetime.now(timezone.utc).isoformat()}],
    }


communicate = communication_node
