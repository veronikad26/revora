"""
Trust Firewall node — single deterministic pass (PRD Section 6.3).

Responsibilities:
- Hard-block and flag for regeneration any outbound message that:
    - contains a link other than the whitelisted "open your app" instruction
    - contains urgency/threat language from a fixed blocklist
    - requests OTP / card number / CVV / bank credentials
    - lacks a specific, verifiable reference (order ID / invoice / amount)
    - proposes a change to amount, discount, fee, or a date beyond the
      merchant-configured PTP window
- Allow at most one regeneration attempt before escalating the case.
- Log every pass/fail decision (see app/models/message.py).

Not LLM-backed. No implementation yet — skeleton only.
"""
