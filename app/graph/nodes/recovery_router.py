"""
Recovery / Guardrail Router node — deterministic (PRD Section 3.1 / 5.2).

Responsibilities:
- Look up the bounded playbook for the diagnosed root-cause category
  from app/rules/playbook_table.yaml (allowed action, retry limit,
  messaging allowed, escalation trigger).
- Below-confidence-threshold or unclassified cases are routed to
  human review here, not guessed.
- Propose the next action (retry | notify | nudge | negotiate |
  do_nothing) to be authorized later by the Policy Engine.

Not LLM-backed. No implementation yet — skeleton only.
"""
