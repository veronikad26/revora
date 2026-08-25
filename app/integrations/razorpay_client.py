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
