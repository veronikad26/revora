"""
Abandoned-checkout behavioral scorer (PRD Section 5 — category 5).

Responsibilities:
- Simple rules-based scorer (thresholds + small weighted score) over:
    - time-since-cart-created
    - cart/checkout value
    - repeat-abandonment history
    - funnel stage reached
- Not an ML model or LLM — deliberately low-dimensional and
  inspectable, per PRD design principle.
- Used by the Diagnosis node in place of a decline-code lookup for
  CheckoutEvent inputs.

No implementation yet — skeleton only.
"""
