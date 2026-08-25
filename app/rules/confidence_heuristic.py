"""
Deterministic confidence heuristic (PRD Section 5.1).

Responsibilities:
- Given a diagnosed case, compute a confidence score without a
  trained ML model:
    - exact known decline-code match -> high confidence
    - partial/ambiguous match or first-seen pattern -> lower confidence
- Below CONFIDENCE_THRESHOLD (app/config.py), the Recovery Router
  routes the case to human review instead of guessing.
- Weights/table here are the target of the closed-loop update node
  (app/graph/nodes/closed_loop_update.py), which adjusts them based
  on observed outcomes.

No implementation yet — skeleton only.
"""
