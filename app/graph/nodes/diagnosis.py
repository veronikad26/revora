"""
Diagnosis node — deterministic (PRD Section 3.1 / Section 5).

Responsibilities:
- Take an incoming FailureEvent or CheckoutEvent and map it to one of
  the six root-cause categories (PRD Section 5):
    1. Insufficient Balance
    2. Card Expired / Invalid
    3. Risk / Fraud Block
    4. Overdue Invoice (B2B)
    5. Abandoned Checkout
    6. Technical / Unclassified
- Use the rule table (app/rules/root_cause_rules.yaml) for known
  gateway/decline codes.
- Use the confidence heuristic (app/rules/confidence_heuristic.py) to
  score how well the case matches a known pattern.
- For abandoned checkouts, delegate to the behavioral scorer
  (app/rules/abandonment_scorer.py) instead of a code lookup.
- Write a RootCauseClassification record.

Not LLM-backed. No implementation yet — skeleton only.
"""
