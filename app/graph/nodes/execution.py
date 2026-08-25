"""
Execution node(s) — deterministic (PRD Section 3.1 / 6.2).

Responsibilities:
- Carry out an action already authorized by the Policy Engine:
    - retry a payment (via app/integrations/razorpay_client.py),
      checking the already_attempted flag first (simplified idempotency)
    - send a WhatsApp message (via app/integrations/twilio_whatsapp_client.py)
    - log a PTP record
    - flag a case to the risk-ops queue (silent, no messaging)
    - do nothing (still logged as a first-class action)
- Never executes anything that was not explicitly authorized by
  policy_engine.py.

No implementation yet — skeleton only.
"""
