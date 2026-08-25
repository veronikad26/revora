"""
Tests for the Diagnosis node (app/graph/nodes/diagnosis.py).

To cover: known decline-code -> correct category mapping,
confidence-below-threshold -> routed to human review, abandoned
checkout -> routed through abandonment_scorer.py instead of a code
lookup.

No implementation yet — skeleton only.
"""
