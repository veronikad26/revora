"""
Synthetic batch generator (PRD Section 9.1).

Responsibilities:
- Generate 50-100 synthetic cases spanning all three entry points and
  all six root-cause categories.
- Assign each case a hidden recoverability profile (e.g. "recoverable
  with correct timing", "recoverable only via negotiation",
  "unrecoverable regardless of action") based on stated assumptions.
- Use a fixed, published random seed for exact reproducibility.
- The agent must never see the hidden profile directly.

No implementation yet — skeleton only.
"""
