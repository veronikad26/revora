"""
Tests for the Policy Engine node (app/graph/nodes/policy_engine.py).

To cover: every guardrail (retry limit, contact limit, contact hours,
consent, PTP limits, dispute/confidence status) is independently
re-checked and can reject an action regardless of what upstream nodes
proposed.

No implementation yet — skeleton only.
"""
