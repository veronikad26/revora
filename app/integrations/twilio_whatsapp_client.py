"""Twilio WhatsApp adapter for bounded outbound and inbound messaging."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.config import DRY_RUN, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM


@dataclass(frozen=True)
class WhatsAppSendResult:
    message_sid: str | None
    status: str
    to: str
    body: str


class TwilioWhatsAppClient:
    def __init__(self, account_sid: str = TWILIO_ACCOUNT_SID, auth_token: str = TWILIO_AUTH_TOKEN, whatsapp_from: str = TWILIO_WHATSAPP_FROM, *, dry_run: bool = DRY_RUN, sdk: Any | None = None) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_from = self._whatsapp_address(whatsapp_from) if whatsapp_from else ""
        self.dry_run = dry_run
        self._sdk = sdk

    @staticmethod
    def _whatsapp_address(value: str) -> str:
        value = value.strip()
        return value if value.startswith("whatsapp:") else f"whatsapp:{value}"

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            try:
                from twilio.rest import Client
            except ImportError as exc:
                raise RuntimeError("Install the twilio package for live WhatsApp operations") from exc
            if not self.account_sid or not self.auth_token:
                raise RuntimeError("Twilio credentials are required for live operations")
            self._sdk = Client(self.account_sid, self.auth_token)
        return self._sdk

    def send_message(self, to: str, body: str, *, status_callback: str | None = None) -> WhatsAppSendResult:
        if not to:
            raise ValueError("recipient phone number is required")
        if not body or not body.strip():
            raise ValueError("message body is required")
        # FIX: was r"https?://|www\\." — two literal backslashes + "." in a
        # raw string, so a bare "www." link would never actually be caught.
        if re.search(r"https?://|www\.", body, re.I):
            raise ValueError("payment or clickable links are not allowed in WhatsApp messages")
        recipient = self._whatsapp_address(to)
        if self.dry_run:
            return WhatsAppSendResult(None, "dry_run", recipient, body)
        kwargs = {"from_": self.whatsapp_from, "body": body}
        if status_callback:
            kwargs["status_callback"] = status_callback
        message = self.sdk.messages.create(to=recipient, **kwargs)
        return WhatsAppSendResult(getattr(message, "sid", None), getattr(message, "status", "queued"), recipient, body)

    @staticmethod
    def parse_inbound_webhook(form: Mapping[str, Any]) -> dict[str, str | None]:
        """Normalize Twilio form fields for the API/webhook layer."""
        return {
            "message_sid": str(form.get("MessageSid") or form.get("SmsMessageSid") or ""),
            "from": str(form.get("From") or ""),
            "to": str(form.get("To") or ""),
            "body": str(form.get("Body") or ""),
            "profile_name": str(form.get("ProfileName") or "") or None,
        }

    def validate_webhook_signature(self, url: str, params: Mapping[str, Any], signature: str) -> bool:
        if not self.auth_token or not signature:
            return False
        try:
            from twilio.request_validator import RequestValidator
        except ImportError as exc:
            raise RuntimeError("Install the twilio package to validate webhook signatures") from exc
        return bool(RequestValidator(self.auth_token).validate(url, dict(params), signature))


_default_client = TwilioWhatsAppClient()
send_message = _default_client.send_message
parse_inbound_webhook = TwilioWhatsAppClient.parse_inbound_webhook