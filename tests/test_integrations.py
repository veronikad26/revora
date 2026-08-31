"""Phase 5 integration adapter tests; all provider calls are mocked or dry-run."""
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.graph.nodes.execution import execution_node
from app.graph.state import new_case_state
from app.integrations.gemini_client import CustomerIntent, GeminiClient
from app.integrations.razorpay_client import RazorpayClient
from app.integrations.twilio_whatsapp_client import TwilioWhatsAppClient


def test_razorpay_signature_and_dry_run_retry():
    client = RazorpayClient(dry_run=True)
    signature = __import__("hmac").new(b"secret", b"payload", __import__("hashlib").sha256).hexdigest()
    assert client.verify_webhook_signature(b"payload", signature, "secret") is True
    result = client.retry_payment("pay-1")
    assert result.skipped is False
    assert result.status == "retry_requested"


def test_razorpay_live_status_uses_injected_sdk():
    sdk = SimpleNamespace(payment=SimpleNamespace(fetch=lambda payment_id: {"id": payment_id, "status": "captured"}))
    client = RazorpayClient("key", "secret", dry_run=False, sdk=sdk)
    status = client.get_payment_status("pay-1")
    assert status.paid is True


def test_twilio_dry_run_normalizes_whatsapp_recipient():
    client = TwilioWhatsAppClient(whatsapp_from="+911111111111", dry_run=True)
    result = client.send_message("+912222222222", "Reminder for Invoice INV-1: INR 500 is pending.")
    assert result.status == "dry_run"
    assert result.to == "whatsapp:+912222222222"
    with pytest.raises(ValueError, match="links"):
        client.send_message("+912222222222", "Invoice INV-1: https://example.com")


def test_twilio_inbound_webhook_parser():
    parsed = TwilioWhatsAppClient.parse_inbound_webhook({"MessageSid": "SM1", "From": "whatsapp:+91", "Body": "STOP"})
    assert parsed["message_sid"] == "SM1"
    assert parsed["body"] == "STOP"


def test_gemini_dry_run_reply_parser():
    client = GeminiClient(dry_run=True)
    intent = client.parse_customer_reply("I will pay the invoice tomorrow")
    assert isinstance(intent, CustomerIntent)
    assert intent.amount_acknowledged is True
    assert intent.dispute_flag is False


def test_gemini_live_response_is_structured_with_mock_http():
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"promise_date":"2026-08-30","amount_acknowledged":true,"dispute_flag":false,"refusal":false,"opt_out":false}'}]}}]}

    class Http:
        @staticmethod
        def post(*args, **kwargs):
            return Response()

    intent = GeminiClient(api_key="key", dry_run=False, http=Http).parse_customer_reply("I will pay on 30 August")
    assert intent.promise_date == "2026-08-30"
    assert intent.amount_acknowledged is True


def test_execution_uses_injected_razorpay_client():
    class FakeRazorpay:
        def retry_payment(self, payment_id):
            return SimpleNamespace(status="retry_requested", skipped=False, reason="fake")

    state = new_case_state(case_id="case-1", entry_point="failure", customer_id="customer-1", payment_id="pay-1")
    state["authorized_action"] = "retry"
    result = execution_node(state, razorpay_client=FakeRazorpay())
    assert result["retry_count"] == 1
    assert result["execution_result"] == "retry_requested: fake"
