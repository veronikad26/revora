"""
Tests for the Trust Firewall node (app/graph/nodes/trust_firewall.py).

To cover: each hard-block condition (link, urgency language, sensitive
data request, missing reference, out-of-limit amount/date change)
independently blocks a message; regeneration is capped at 1 attempt
before escalation.

No implementation yet — skeleton only.
"""
