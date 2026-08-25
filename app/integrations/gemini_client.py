"""
Gemini API client (PRD Section 10 — Tech Stack).

Responsibilities:
- Wrap calls to the Gemini API (free tier) for the Communication node's
  two jobs only:
    1. Generate the outbound Hinglish/English message text.
    2. Parse free-text customer replies into structured intent
       (promise_date, amount_acknowledged, dispute_flag, refusal)
       using structured/JSON output.
- No other node in the graph calls this client — the LLM's usage
  surface is intentionally limited to these two functions.

No implementation yet — skeleton only.
"""
