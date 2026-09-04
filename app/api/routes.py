"""General case and state-inspection routes for Phase 8."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db.database import SessionLocal
from app.graph.state import new_case_state
from app.models.checkout_event import CheckoutEvent
from app.models.consent_flag import ConsentFlag
from app.models.failure_event import FailureEvent

router = APIRouter(tags=["cases"])
logger = logging.getLogger("revora.api")

# Serializes every graph.invoke()/update_state() call process-wide.
#
# Why this exists: a checkout/receivable case is the ONLY kind of case that
# runs the Consent Gate -> Communication -> Trust Firewall chain (failure/
# retry cases skip straight to Policy Engine), so it drives roughly twice as
# many LangGraph checkpoint writes per request as a failure case. Those
# checkpoint writes go to revora_checkpoints.db via LangGraph's SqliteSaver,
# while ordinary case rows (FailureEvent/CheckoutEvent/ConsentFlag/...) go
# to a SEPARATE connection on revora.db via SQLAlchemy's SessionLocal --
# two independent sqlite3 connections with `check_same_thread=False` and no
# coordination between them. Under FastAPI's threadpool (every sync route
# handler runs on its own worker thread) this is a textbook recipe for
# `sqlite3.OperationalError: database is locked` on Windows, and it shows
# up almost exclusively on checkout/receivable because of the extra node
# traffic. A single process-wide lock around every graph run removes the
# contention entirely; for a single-operator dashboard/demo app this has no
# meaningful throughput cost.
_GRAPH_LOCK = threading.Lock()


class FailureRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
    method: str = "unknown"
    gateway_code: str | None = None
    gateway_reason: str | None = None


class CheckoutRequest(BaseModel):
    customer_id: str
    customer_phone: str | None = None
    cart_id: str
    consent: bool = False
    cart_value: Decimal = Field(ge=0)
    currency: str = "INR"
    funnel_stage_reached: str = "payment"
    prior_abandonment_count: int = Field(default=0, ge=0)
    last_activity_at: datetime | None = None


class ReceivableRequest(BaseModel):
    customer_id: str
    customer_phone: str | None = None
    invoice_payment_ref: str
    consent: bool = False
    amount: Decimal = Field(ge=0)
    currency: str = "INR"


class ConsentRequest(BaseModel):
    consent: bool
    channel: str = "whatsapp"


class SimulateReplyRequest(BaseModel):
    reply: str = Field(min_length=1)


def _graph(request: Request) -> Any:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="graph is not initialized")
    return graph


def _invoke(request: Request, state: dict[str, Any]) -> dict[str, Any]:
    """Run one case through the compiled graph."""

    case_id = state["case_id"]

    try:
        with _GRAPH_LOCK:
            result = _graph(request).invoke(
                state,
                config={
                    "configurable": {
                        "thread_id": case_id,
                    },
                    "recursion_limit": 100,
                },
            )

    except Exception as exc:
        logger.exception(
            "graph.invoke failed for case_id=%s",
            case_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"case processing failed: {exc!r}",
        ) from exc

    return {
        "case_id": case_id,
        "state": result,
    }


def _persist_consent(customer_id: str, channel: str, consent: bool) -> None:
    session = SessionLocal()
    try:
        record = session.query(ConsentFlag).filter_by(customer_id=customer_id, channel=channel).one_or_none()
        if record is None:
            session.add(ConsentFlag(id=str(uuid.uuid4()), customer_id=customer_id, channel=channel, consent=consent))
        else:
            record.consent = consent
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=500, detail=f"could not save consent: {exc!r}") from exc
    finally:
        session.close()


def _existing_case_state(request: Request, case_id: str) -> dict[str, Any] | None:
    """Look up a case's live checkpointed state, or None if it has no checkpoint.

    A row existing in the SQL database (FailureEvent, CheckoutEvent, ...) does
    NOT imply a LangGraph checkpoint exists for that case_id -- those are two
    independent persistence layers (see app/config.py::LANGGRAPH_CHECKPOINT_PATH).
    A case can end up with a DB row but no reachable checkpoint if, for
    example, it was originally created while the API was running with the
    in-memory MemorySaver and the process has since restarted.
    """
    config = {"configurable": {"thread_id": case_id}}
    with _GRAPH_LOCK:
        snapshot = _graph(request).get_state(config)
    return dict(snapshot.values) if snapshot.values else None


@router.get("/health", tags=["system"])
def health(request: Request) -> dict[str, Any]:
    return {"status": "ok", "graph_ready": getattr(request.app.state, "graph", None) is not None}


@router.post("/cases/failure", status_code=201)
def create_failure(payload: FailureRequest, request: Request) -> dict[str, Any]:
    session = SessionLocal()
    try:
        existing = session.query(FailureEvent).filter_by(payment_id=payload.payment_id).one_or_none()
        if existing:
            # payment_id is deliberately deduplicated (PRD idempotency
            # requirement) so the same real-world gateway failure event is
            # never processed twice. That must not leave the caller holding
            # a case_id it can never fetch state for: look up the existing
            # case's live checkpoint (the same mechanism GET /cases/{id}
            # uses) instead of returning no state at all.
            state = _existing_case_state(request, existing.id)
            return {
                "status": "duplicate",
                "case_id": existing.id,
                "event_id": existing.id,
                "state": state,
                "note": None if state is not None else (
                    "payment_id already exists but no live checkpoint was found for "
                    "this case (it may have been created before the current "
                    "checkpoint store, or the checkpoint store was reset). "
                    "Submit with a different Payment ID to create a fresh, "
                    "checkpointed case."
                ),
            }
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        event = FailureEvent(id=case_id, payment_id=payload.payment_id, gateway_code=payload.gateway_code, gateway_reason=payload.gateway_reason, amount=payload.amount, currency=payload.currency, method=payload.method, timestamp=now, customer_id=payload.customer_id, raw_payload=payload.model_dump_json())
        session.add(event)
        session.commit()
        state = new_case_state(case_id=case_id, entry_point="failure", event_id=case_id, customer_id=payload.customer_id, amount=payload.amount, currency=payload.currency, payment_id=payload.payment_id, gateway_code=payload.gateway_code, gateway_reason=payload.gateway_reason, method=payload.method, now=now)
        return {"status": "processed", **_invoke(request, state)}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/cases/checkout", status_code=201)
def create_checkout(payload: CheckoutRequest, request: Request) -> dict[str, Any]:
    logger.info("received checkout case: customer_id=%s cart_id=%s", payload.customer_id, payload.cart_id)
    case_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    last_activity = payload.last_activity_at or now
    session = SessionLocal()
    try:
        session.add(CheckoutEvent(id=case_id, cart_id=payload.cart_id, customer_id=payload.customer_id, cart_value=payload.cart_value, currency=payload.currency, funnel_stage_reached=payload.funnel_stage_reached, created_at=now, last_activity_at=last_activity, prior_abandonment_count=payload.prior_abandonment_count, updated_at=now))
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("failed to persist CheckoutEvent for case_id=%s", case_id)
        raise HTTPException(status_code=500, detail=f"could not save checkout event: {exc!r}") from exc
    finally:
        session.close()
    if payload.consent:
        _persist_consent(payload.customer_id, "whatsapp", True)
    state = new_case_state(case_id=case_id, entry_point="abandonment", event_id=case_id, customer_id=payload.customer_id, customer_phone=payload.customer_phone, amount=payload.cart_value, currency=payload.currency, cart_id=payload.cart_id, cart_value=payload.cart_value, funnel_stage_reached=payload.funnel_stage_reached, last_activity_at=last_activity.isoformat(), prior_abandonment_count=payload.prior_abandonment_count, now=now)
    if payload.consent:
        state["consent_flag"] = True
    return {"status": "processed", **_invoke(request, state)}


@router.post("/cases/receivable", status_code=201)
def create_receivable(payload: ReceivableRequest, request: Request) -> dict[str, Any]:
    logger.info("received receivable case: customer_id=%s invoice_payment_ref=%s", payload.customer_id, payload.invoice_payment_ref)
    case_id = str(uuid.uuid4())
    if payload.consent:
        _persist_consent(payload.customer_id, "whatsapp", True)
    state = new_case_state(case_id=case_id, entry_point="receivable", event_id=case_id, customer_id=payload.customer_id, customer_phone=payload.customer_phone, amount=payload.amount, currency=payload.currency, invoice_payment_ref=payload.invoice_payment_ref)
    if payload.consent:
        state["consent_flag"] = True
    return {"status": "processed", **_invoke(request, state)}


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request) -> dict[str, Any]:
    config = {"configurable": {"thread_id": case_id}}
    with _GRAPH_LOCK:
        snapshot = _graph(request).get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="case not found")
    return {"case_id": case_id, "state": snapshot.values}


@router.post("/cases/{case_id}/confirm-payment")
def confirm_payment(case_id: str, request: Request) -> dict[str, Any]:
    """Record an external payment confirmation and close the case as recovered.

    This endpoint represents the provider/webhook confirmation step; it does
    not charge the customer. It is also useful for demonstrating the recovered
    path from the dashboard without requiring a live payment provider.
    """
    config = {"configurable": {"thread_id": case_id}}
    graph = _graph(request)
    with _GRAPH_LOCK:
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="case not found")

        state = snapshot.values
        now = datetime.now(timezone.utc).isoformat()
        audit_event = {
            "action": "payment_confirmed",
            "actor": "payment_provider",
            "entity_type": "case",
            "entity_id": case_id,
            "reason": "external payment confirmation received",
            "customer_visible_reason": None,
            "timestamp": now,
        }
        try:
            graph.update_state(
                config,
                {
                    "payment_confirmed": True,
                    "ptp_state": "KEPT",
                    "outcome": "recovered",
                    "outcome_reason": "payment confirmed by provider",
                    "recovered_amount": state.get("amount"),
                    "execution_result": "payment_confirmed",
                    "audit_trail": [audit_event],
                    "updated_at": now,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("confirm-payment failed for case_id=%s", case_id)
            raise HTTPException(status_code=500, detail=f"confirm-payment failed: {exc!r}") from exc
        result = graph.get_state(config).values
    return {"case_id": case_id, "state": result}


@router.post("/cases/{case_id}/consent")
def update_consent(case_id: str, payload: ConsentRequest, request: Request) -> dict[str, Any]:
    config = {"configurable": {"thread_id": case_id}}
    with _GRAPH_LOCK:
        snapshot = _graph(request).get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="case not found")
    customer_id = snapshot.values["customer_id"]
    session = SessionLocal()
    try:
        record = session.query(ConsentFlag).filter_by(customer_id=customer_id, channel=payload.channel).one_or_none()
        if record is None:
            record = ConsentFlag(id=str(uuid.uuid4()), customer_id=customer_id, channel=payload.channel, consent=payload.consent)
            session.add(record)
        else:
            record.consent = payload.consent
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("failed to persist ConsentFlag for case_id=%s", case_id)
        raise HTTPException(status_code=500, detail=f"could not save consent: {exc!r}") from exc
    finally:
        session.close()
    graph = _graph(request)
    try:
        consent_update = {
            "consent_flag": payload.consent,
            "consent_checked": True,
            "contact_allowed": payload.consent,
            "consent_reason": "consent updated through API",
            "pending_event": "consent_granted" if payload.consent else None,
            "outcome": None if payload.consent else "do_nothing",
            "outcome_reason": None if payload.consent else "consent revoked through API",
        }
        with _GRAPH_LOCK:
            if payload.consent:
                # Pass the consent event as the input to the single graph run.
                # Calling update_state() and then invoke() back-to-back causes
                # LangGraph's SQLite checkpointer to wait on its own queued
                # checkpoint write, leaving checkout/receivable requests stuck.
                # The one-shot pending_event is cleared by the graph's terminal
                # state update, so later refreshes cannot resend the message.
                graph.invoke(consent_update, config=config)
            else:
                graph.update_state(config, consent_update)
            result = graph.get_state(config).values
    except Exception as exc:  # noqa: BLE001
        logger.exception("consent-triggered graph run failed for case_id=%s", case_id)
        raise HTTPException(status_code=500, detail=f"consent update failed: {exc!r}") from exc
    return {"case_id": case_id, "consent": payload.consent, "channel": payload.channel, "state": result}


@router.post("/cases/{case_id}/simulate-reply")
def simulate_reply(case_id: str, payload: SimulateReplyRequest, request: Request) -> dict[str, Any]:
    """Dashboard-only helper for the negotiation chat simulator.

    Feeds a typed customer reply into the graph exactly the way a real
    inbound message would (same last_customer_reply / pending_event
    mechanism the Twilio webhook uses in app/api/webhooks.py), but as a
    plain JSON call with no messaging-provider payload shape, signature,
    or account required. This exists purely so the dashboard can simulate
    the full PTP negotiation loop (Gemini draft -> Trust Firewall ->
    execution -> customer reply -> intent parsing -> PTP state machine)
    entirely locally.
    """
    config = {"configurable": {"thread_id": case_id}}
    graph = _graph(request)
    try:
        with _GRAPH_LOCK:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                raise HTTPException(status_code=404, detail="case not found")
            graph.update_state(config, {"last_customer_reply": payload.reply, "pending_event": "inbound_reply", "event_id": f"sim-{uuid.uuid4().hex[:8]}"})
            result = graph.invoke({}, config=config)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("simulate-reply failed for case_id=%s", case_id)
        raise HTTPException(status_code=500, detail=f"simulate-reply failed: {exc!r}") from exc
    return {"case_id": case_id, "state": result}