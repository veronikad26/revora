"""
Observation / Audit node — deterministic (PRD Section 3.1 / Section 8.1).

Responsibilities:
- Write every decision (action, reason, actor, timestamp) to the
  append-only audit ledger BEFORE execution (app/models/audit_log_entry.py).
- After execution, capture the outcome (payment succeeded? PTP kept or
  broken? nudge converted?) as an OutcomeEvent
  (app/models/outcome_event.py).
- Surface a simplified, customer-facing version of the audit reason
  as a transparency footer alongside outbound messages
  (PRD Section 8.2).

No implementation yet — skeleton only.
"""
