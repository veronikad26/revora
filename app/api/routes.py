"""General case and state-inspection routes for Phase 8."""
from __future__ import annotations

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
    cart_id: str
    cart_value: Decimal = Field(ge=0)
    currency: str = "INR"
    funnel_stage_reached: str = "payment"
    prior_abandonment_count: int = Field(default=0, ge=0)
    last_activity_at: datetime | None = None


class ReceivableRequest(BaseModel):
    customer_id: str
    invoice_payment_ref: str
    amount: Decimal = Field(ge=0)
    currency: str = "INR"


class ConsentRequest(BaseModel):
    consent: bool
    channel: str = "whatsapp"


def _graph(request: Request) -> Any:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="graph is not initialized")
    return graph


def _invoke(request: Request, state: dict[str, Any]) -> dict[str, Any]:
    case_id = state["case_id"]
    result = _graph(request).invoke(state, config={"configurable": {"thread_id": case_id}})
    return {"case_id": case_id, "state": result}


@router.get("/health", tags=["system"])
def health(request: Request) -> dict[str, Any]:
    return {"status": "ok", "graph_ready": getattr(request.app.state, "graph", None) is not None}


@router.post("/cases/failure", status_code=201)
def create_failure(payload: FailureRequest, request: Request) -> dict[str, Any]:
    session = SessionLocal()
    try:
        existing = session.query(FailureEvent).filter_by(payment_id=payload.payment_id).one_or_none()
        if existing:
            return {"status": "duplicate", "case_id": existing.id, "event_id": existing.id}
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        event = FailureEvent(id=case_id, payment_id=payload.payment_id, gateway_code=payload.gateway_code, gateway_reason=payload.gateway_reason, amount=payload.amount, currency=payload.currency, method=payload.method, timestamp=now, customer_id=payload.customer_id, raw_payload=payload.model_dump_json())
        session.add(event)
        session.commit()
        state = new_case_state(case_id=case_id, entry_point="failure", event_id=case_id, customer_id=payload.customer_id, amount=payload.amount, currency=payload.currency, payment_id=payload.payment_id, gateway_code=payload.gateway_code, gateway_reason=payload.gateway_reason, method=payload.method, now=now)
        return {"status": "processed", **_invoke(request, state)}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/cases/checkout", status_code=201)
def create_checkout(payload: CheckoutRequest, request: Request) -> dict[str, Any]:
    case_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    last_activity = payload.last_activity_at or now
    session = SessionLocal()
    try:
        session.add(CheckoutEvent(id=case_id, cart_id=payload.cart_id, customer_id=payload.customer_id, cart_value=payload.cart_value, currency=payload.currency, funnel_stage_reached=payload.funnel_stage_reached, created_at=now, last_activity_at=last_activity, prior_abandonment_count=payload.prior_abandonment_count, updated_at=now))
        session.commit()
    finally:
        session.close()
    state = new_case_state(case_id=case_id, entry_point="abandonment", event_id=case_id, customer_id=payload.customer_id, amount=payload.cart_value, currency=payload.currency, cart_id=payload.cart_id, cart_value=payload.cart_value, funnel_stage_reached=payload.funnel_stage_reached, last_activity_at=last_activity.isoformat(), prior_abandonment_count=payload.prior_abandonment_count, now=now)
    return {"status": "processed", **_invoke(request, state)}


@router.post("/cases/receivable", status_code=201)
def create_receivable(payload: ReceivableRequest, request: Request) -> dict[str, Any]:
    state = new_case_state(case_id=str(uuid.uuid4()), entry_point="receivable", customer_id=payload.customer_id, amount=payload.amount, currency=payload.currency, invoice_payment_ref=payload.invoice_payment_ref)
    return {"status": "processed", **_invoke(request, state)}


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request) -> dict[str, Any]:
    config = {"configurable": {"thread_id": case_id}}
    snapshot = _graph(request).get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="case not found")
    return {"case_id": case_id, "state": snapshot.values}


@router.post("/cases/{case_id}/consent")
def update_consent(case_id: str, payload: ConsentRequest, request: Request) -> dict[str, Any]:
    config = {"configurable": {"thread_id": case_id}}
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
    finally:
        session.close()
    _graph(request).update_state(config, {"consent_flag": payload.consent, "consent_checked": True, "contact_allowed": payload.consent, "consent_reason": "consent updated through API"})
    return {"case_id": case_id, "consent": payload.consent, "channel": payload.channel}
