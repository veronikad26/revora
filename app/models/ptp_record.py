"""
PTPRecord entity (PRD Section 7 / 11).

Fields: id, customer_id, invoice/payment_ref, amount, promised_date,
state, conversation_id, negotiation_limit_max_date, dispute_flag.

Tracks a case through the full PTP state machine:
DETECTED -> CONTACTED -> NEGOTIATING -> PROMISED -> KEPT/BROKEN,
with DISPUTED -> ESCALATED and BROKEN -> RENEGOTIATE (max 1x) -> ESCALATED.

No implementation yet — skeleton only.
"""
