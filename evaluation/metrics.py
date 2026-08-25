"""
Metrics / breakdown computation (PRD Section 9.4).

Responsibilities:
- Rupees recovered as % of at-risk and as uplift multiple vs. both
  baselines.
- Breakdown by root-cause category and by entry point.
- PTP kept-rate, with average days-late when broken.
- Correctly withheld actions (DO NOTHING) count.
- False-intervention count and rate (target 0).
- Escalation count/rate by trigger.
- Closed-loop effect: confidence/timing table before vs. after the
  batch run (PRD Section 8.1).

No implementation yet — skeleton only.
"""
