"""Typed, checkpoint-friendly state for one RecoverAI case.

The graph state is intentionally composed of JSON-compatible primitives so
LangGraph can persist it through SQLite checkpointing and resume a case after
an inbound message or a promised-date event. Nodes should return partial
updates to this TypedDict rather than mutating state in place.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from operator import add
from typing import Annotated, Any, Literal, NotRequired, TypedDict


EntryPoint = Literal["failure", "abandonment", "receivable"]
RootCauseCategory = Literal[
    "insufficient_balance",
    "card_expired_invalid",
    "risk_fraud_block",
    "overdue_invoice",
    "abandoned_checkout",
    "technical_unclassified",
]
PTPState = Literal[
    "DETECTED",
    "CONTACTED",
    "NEGOTIATING",
    "PROMISED",
    "KEPT",
    "BROKEN",
    "RENEGOTIATE",
    "DISPUTED",
    "ESCALATED",
]
CaseOutcome = Literal["recovered", "broken", "escalated", "do_nothing"]
Action = Literal[
    "retry",
    "notify",
    "nudge",
    "negotiate",
    "ptp_log",
    "risk_ops_flag",
    "escalate",
    "do_nothing",
]

ENTRY_POINTS: tuple[str, ...] = ("failure", "abandonment", "receivable")
ROOT_CAUSE_CATEGORIES: tuple[str, ...] = (
    "insufficient_balance",
    "card_expired_invalid",
    "risk_fraud_block",
    "overdue_invoice",
    "abandoned_checkout",
    "technical_unclassified",
)
PTP_STATES: tuple[str, ...] = (
    "DETECTED", "CONTACTED", "NEGOTIATING", "PROMISED", "KEPT",
    "BROKEN", "RENEGOTIATE", "DISPUTED", "ESCALATED",
)
OUTCOMES: tuple[str, ...] = ("recovered", "broken", "escalated", "do_nothing")


class ConversationMessage(TypedDict, total=False):
    """A JSON-safe inbound or outbound message in conversation history."""

    direction: Literal["in", "out"]
    content: str
    channel: str
    timestamp: str
    message_id: str


class ParsedIntent(TypedDict, total=False):
    """Structured result returned by the Communication node."""

    promise_date: str | None
    amount_acknowledged: bool
    dispute_flag: bool
    refusal: bool
    opt_out: bool
    raw_text: str
    payment_confirmed: bool


class AuditEvent(TypedDict, total=False):
    """Audit event carried in state before it is persisted to the ledger."""

    action: str
    actor: Literal["rule", "llm", "policy_engine", "human"]
    entity_type: str
    entity_id: str
    reason: str
    customer_visible_reason: str | None
    timestamp: str


class RecoveryState(TypedDict, total=False):
    """Persisted state contract shared by all graph nodes.

    ``total=False`` is deliberate: LangGraph nodes commonly return partial
    state updates. ``new_case_state`` provides a complete valid initial value.
    """

    # Identity and source event.
    case_id: str
    entry_point: EntryPoint
    event_id: str
    event_type: str
    customer_id: str
    customer_phone: str | None
    channel: str
    amount: float
    currency: str
    payment_id: str
    gateway_code: str | None
    gateway_reason: str | None
    method: str | None
    cart_id: str | None
    cart_value: float | None
    funnel_stage_reached: str | None
    last_activity_at: str | None
    prior_abandonment_count: int
    invoice_payment_ref: str | None

    # Diagnosis and bounded routing.
    root_cause_category: RootCauseCategory | None
    confidence: float | None
    diagnosis_reason: str | None
    proposed_action: Action | None
    authorized_action: Action | None
    action_reason: str | None
    escalation_trigger: str | None
    consent_checked: bool
    consent_reason: str | None
    contact_allowed: bool

    # Guardrail counters and flags.
    retry_count: int
    contact_count: int
    consent_flag: bool
    already_attempted_flag: bool
    trust_firewall_regenerations: int
    opt_out: bool

    # Promise-to-Pay lifecycle.
    ptp_state: PTPState
    promised_date: str | None
    negotiation_limit_max_date: str | None
    dispute_flag: bool
    renegotiation_count: int

    # Communication and observability.
    conversation_history: Annotated[list[ConversationMessage], add]
    last_customer_reply: str | None
    parsed_intent: ParsedIntent | None
    draft_message: str | None
    pending_event: Literal["inbound_reply", "consent_granted"] | None
    payment_confirmed: bool
    retry_delay_multiplier: float
    audit_trail: Annotated[list[AuditEvent], add]
    outcome: CaseOutcome | None
    outcome_reason: str | None
    recovered_amount: float | None
    execution_result: str | None
    learning_updates: dict[str, Any]
    created_at: str
    updated_at: str


# Alias with the name commonly used by LangGraph integrations.
GraphState = RecoveryState


def utc_isoformat(value: datetime | None = None) -> str:
    """Return a canonical UTC timestamp suitable for checkpoint serialization."""

    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def date_isoformat(value: date | None) -> str | None:
    """Serialize a date while preserving ``None`` for an unset promise."""

    return value.isoformat() if value else None


def new_case_state(
    *,
    case_id: str,
    entry_point: EntryPoint,
    customer_id: str,
    event_id: str | None = None,
    event_type: str | None = None,
    amount: float = 0.0,
    currency: str = "INR",
    channel: str = "whatsapp",
    payment_id: str | None = None,
    gateway_code: str | None = None,
    gateway_reason: str | None = None,
    method: str | None = None,
    cart_id: str | None = None,
    cart_value: float | None = None,
    funnel_stage_reached: str | None = None,
    last_activity_at: str | None = None,
    prior_abandonment_count: int = 0,
    invoice_payment_ref: str | None = None,
    now: datetime | None = None,
) -> RecoveryState:
    """Create a complete initial state for any of the three entry points."""

    timestamp = utc_isoformat(now)
    return RecoveryState(
        case_id=case_id,
        entry_point=entry_point,
        event_id=event_id or case_id,
        event_type=event_type or entry_point,
        customer_id=customer_id,
        customer_phone=None,
        channel=channel,
        amount=float(amount),
        currency=currency,
        payment_id=payment_id or "",
        gateway_code=gateway_code,
        gateway_reason=gateway_reason,
        method=method,
        cart_id=cart_id,
        cart_value=float(cart_value) if cart_value is not None else None,
        funnel_stage_reached=funnel_stage_reached,
        last_activity_at=last_activity_at,
        prior_abandonment_count=max(0, int(prior_abandonment_count)),
        invoice_payment_ref=invoice_payment_ref,
        root_cause_category=None,
        confidence=None,
        diagnosis_reason=None,
        proposed_action=None,
        authorized_action=None,
        action_reason=None,
        escalation_trigger=None,
        consent_checked=False,
        consent_reason=None,
        contact_allowed=False,
        retry_count=0,
        contact_count=0,
        consent_flag=False,
        already_attempted_flag=False,
        trust_firewall_regenerations=0,
        opt_out=False,
        ptp_state="DETECTED",
        promised_date=None,
        negotiation_limit_max_date=None,
        dispute_flag=False,
        renegotiation_count=0,
        conversation_history=[],
        last_customer_reply=None,
        parsed_intent=None,
        draft_message=None,
        pending_event=None,
        payment_confirmed=False,
        retry_delay_multiplier=1.0,
        audit_trail=[],
        outcome=None,
        outcome_reason=None,
        recovered_amount=None,
        execution_result=None,
        learning_updates={},
        created_at=timestamp,
        updated_at=timestamp,
    )


def validate_state(state: RecoveryState) -> None:
    """Raise ``ValueError`` for invalid lifecycle or bounded-counter values."""

    required = ("case_id", "entry_point", "customer_id", "ptp_state")
    missing = [field for field in required if not state.get(field)]
    if missing:
        raise ValueError(f"missing required state fields: {', '.join(missing)}")
    if state["entry_point"] not in ENTRY_POINTS:
        raise ValueError(f"invalid entry_point: {state['entry_point']}")
    if state["ptp_state"] not in PTP_STATES:
        raise ValueError(f"invalid ptp_state: {state['ptp_state']}")
    confidence = state.get("confidence")
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    for field in ("retry_count", "contact_count", "trust_firewall_regenerations", "renegotiation_count"):
        if state.get(field, 0) < 0:
            raise ValueError(f"{field} cannot be negative")