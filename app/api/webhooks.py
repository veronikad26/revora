"""Razorpay and Twilio webhook receivers for Phase 8."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import RAZORPAY_WEBHOOK_SECRET, TWILIO_WEBHOOK_URL
from app.db.database import SessionLocal
from app.graph.state import new_case_state
from app.integrations.razorpay_client import RazorpayClient
from app.integrations.twilio_whatsapp_client import TwilioWhatsAppClient
from app.models.failure_event import FailureEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _graph(request: Request) -> Any:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="graph is not initialized")
    return graph


def _payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("payload", {}).get("payment", {}).get("entity", payload.get("payment", payload))


def normalize_razorpay_failure(payload: dict[str, Any]) -> dict[str, Any]:
    entity = _payment_entity(payload)
    payment_id = str(entity.get("id") or entity.get("payment_id") or "")
    if not payment_id:
        raise ValueError("Razorpay payload has no payment id")
    raw_amount = Decimal(str(entity.get("amount", 0)))
    # Razorpay amounts are integer subunits (paise for INR).
    amount = raw_amount / Decimal("100")
    return {
        "event_id": str(payload.get("id") or uuid.uuid4()),
        "payment_id": payment_id,
        "gateway_code": entity.get("error_code"),
        "gateway_reason": entity.get("error_reason") or entity.get("error_description"),
        "amount": amount,
        "currency": entity.get("currency", "INR"),
        "method": entity.get("method", "unknown"),
        "customer_id": str(entity.get("email") or entity.get("contact") or "unknown"),
        "timestamp": datetime.now(timezone.utc),
        "raw_payload": json.dumps(payload, sort_keys=True),
    }


def dispatch_failure(data: dict[str, Any], graph: Any, session: Any) -> dict[str, Any]:
    existing = session.query(FailureEvent).filter_by(payment_id=data["payment_id"]).one_or_none()
    if existing:
        return {"status": "duplicate", "event_id": existing.id, "case_id": existing.id}
    event = FailureEvent(id=str(uuid.uuid4()), **data)
    session.add(event)
    session.flush()
    state = new_case_state(
        case_id=event.id,
        entry_point="failure",
        event_id=event.id,
        customer_id=data["customer_id"],
        amount=data["amount"],
        currency=data["currency"],
        payment_id=data["payment_id"],
        gateway_code=data["gateway_code"],
        gateway_reason=data["gateway_reason"],
        method=data["method"],
        now=data["timestamp"],
    )
    result = graph.invoke(state, config={"configurable": {"thread_id": event.id}})
    return {"status": "processed", "event_id": event.id, "case_id": event.id, "state": result}


@router.post("/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None)):
    raw = await request.body()
    client = RazorpayClient()
    if RAZORPAY_WEBHOOK_SECRET:
        if not client.verify_webhook_signature(raw, x_razorpay_signature or "", RAZORPAY_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="invalid Razorpay signature")
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc
    event_name = payload.get("event", "")
    if event_name not in {"payment.failed", "payment.authorized"}:
        return JSONResponse({"status": "ignored", "event": event_name})
    try:
        session = SessionLocal()
        try:
            result = dispatch_failure(normalize_razorpay_failure(payload), _graph(request), session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request, x_twilio_signature: str | None = Header(default=None)):
    raw = await request.body()
    form = {key: values[-1] for key, values in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
    values = TwilioWhatsAppClient.parse_inbound_webhook(form)
    if TWILIO_WEBHOOK_URL:
        if not x_twilio_signature or not TwilioWhatsAppClient().validate_webhook_signature(TWILIO_WEBHOOK_URL, form, x_twilio_signature):
            raise HTTPException(status_code=401, detail="invalid Twilio signature")
    case_id = str(form.get("CaseId") or form.get("case_id") or "")
    if not case_id:
        raise HTTPException(status_code=400, detail="CaseId is required for inbound routing")
    graph = _graph(request)
    config = {"configurable": {"thread_id": case_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="case checkpoint not found")
    graph.update_state(config, {"last_customer_reply": values["body"], "pending_event": "inbound_reply", "event_id": values["message_sid"]})
    result = graph.invoke({}, config=config)
    return {"status": "processed", "case_id": case_id, "message_sid": values["message_sid"], "state": result}