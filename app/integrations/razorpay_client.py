"""
Razorpay integration client (PRD Section 10 — Tech Stack).

Responsibilities:
- Wrap Razorpay test-mode APIs: Payments, Payment Links status, Webhooks.
- Provide a status-check function used by Execution before firing a
  scheduled retry (skip if already paid).
- Provide a retry-execution function invoked only after Policy Engine
  authorization.

No implementation yet — skeleton only.
"""
"""Razorpay test-mode adapter used by the deterministic execution layer."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from app.config import DRY_RUN, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET


@dataclass(frozen=True)
class PaymentStatus:
    payment_id: str
    status: str
    paid: bool
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetryResult:
    payment_id: str
    status: str
    skipped: bool
    reason: str
    raw: dict[str, Any] | None = None


class RazorpayClient:
    """Small adapter that keeps provider details out of graph nodes.

    Razorpay does not expose a server-side "charge the same failed payment
    again" operation. A retry therefore means re-checking the payment and
    returning a retry instruction for the merchant's checkout/mandate flow;
    the adapter never double-charges a payment.
    """

    def __init__(self, key_id: str = RAZORPAY_KEY_ID, key_secret: str = RAZORPAY_KEY_SECRET, *, dry_run: bool = DRY_RUN, sdk: Any | None = None) -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.dry_run = dry_run
        self._sdk = sdk

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            try:
                import razorpay
            except ImportError as exc:
                raise RuntimeError("Install the razorpay package for live payment operations") from exc
            if not self.key_id or not self.key_secret:
                raise RuntimeError("Razorpay credentials are required for live operations")
            self._sdk = razorpay.Client(auth=(self.key_id, self.key_secret))
        return self._sdk

    @staticmethod
    def _status_from_payload(payment_id: str, payload: dict[str, Any]) -> PaymentStatus:
        status = str(payload.get("status", "unknown")).lower()
        return PaymentStatus(payment_id, status, status in {"captured", "paid"}, payload)

    def get_payment_status(self, payment_id: str) -> PaymentStatus:
        if not payment_id:
            raise ValueError("payment_id is required")
        if self.dry_run:
            return PaymentStatus(payment_id, "dry_run_unknown", False, None)
        payload = self.sdk.payment.fetch(payment_id)
        return self._status_from_payload(payment_id, payload)

    def verify_webhook_signature(self, payload: bytes | str, signature: str, webhook_secret: str) -> bool:
        if not webhook_secret or not signature:
            return False
        body = payload.encode("utf-8") if isinstance(payload, str) else payload
        expected = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def retry_payment(self, payment_id: str) -> RetryResult:
        status = self.get_payment_status(payment_id)
        if status.paid:
            return RetryResult(payment_id, status.status, True, "skipped — payment already succeeded", status.raw)
        if self.dry_run:
            return RetryResult(payment_id, "retry_requested", False, "dry-run retry request; no provider mutation", status.raw)
        return RetryResult(payment_id, "retry_requested", False, "payment remains failed; merchant checkout/mandate flow must initiate retry", status.raw)

    def fetch_payment_link(self, payment_link_id: str) -> dict[str, Any]:
        if not payment_link_id:
            raise ValueError("payment_link_id is required")
        if self.dry_run:
            return {"id": payment_link_id, "status": "dry_run_unknown"}
        return self.sdk.payment_link.fetch(payment_link_id)


_default_client = RazorpayClient()
get_payment_status = _default_client.get_payment_status
retry_payment = _default_client.retry_payment
verify_webhook_signature = _default_client.verify_webhook_signature
