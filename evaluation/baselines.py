"""
Baseline conditions for batch comparison (PRD Section 9.3).

Responsibilities:
- do_nothing: no intervention at all.
- naive_baseline: retry every failure blindly after a fixed delay;
  generic English reminder for receivables/abandonment; no root-cause
  routing, no consent gate, no idempotency check.
- Each baseline runs against the identical synthetic batch as Revora
  for a fair uplift comparison.

No implementation yet — skeleton only.
"""
