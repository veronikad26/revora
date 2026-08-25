"""
Consent Gate node — deterministic (PRD Section 6.1, simplified).

Responsibilities:
- Check the boolean consent_flag for the customer/channel
  (app/models/consent_flag.py) before any outreach.
- If consent is missing: route the case to DO NOTHING with reason
  "no consent on file" — do not fall through to Execution or
  Communication nodes.
- This node is placed so that no graph path can reach outreach
  without passing through it (see app/graph/edges/routing.py).

No implementation yet — skeleton only.
"""
