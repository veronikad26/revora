"""
Webhook receivers (PRD Section 10 — Tech Stack).

Responsibilities:
- Razorpay payment/webhook endpoint -> creates a FailureEvent and
  dispatches it into the graph as an entry point.
- Twilio inbound-message webhook endpoint -> routes a customer reply
  into the Communication node of the relevant in-flight case.

No implementation yet — skeleton only.
"""
