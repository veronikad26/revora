"""
Communication node — the ONE LLM-backed node in the graph
(PRD Section 3.1 / Section 8, Gemini API).

Responsibilities:
- Generate the outbound Hinglish/English nudge or PTP negotiation
  message from structured case data (invoice #, amount, days overdue),
  subject to Trust Firewall review before send.
- Parse free-text customer replies into structured intent:
    {promise_date, amount_acknowledged, dispute_flag, refusal}
  using structured output (see app/integrations/gemini_client.py).
- Never given a tool that can execute a payment, retry, or modify
  any invoice/amount/fee/date (PRD Section 6.4 boundary, preserved
  even in this simplified build).

No implementation yet — skeleton only.
"""
