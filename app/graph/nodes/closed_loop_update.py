"""Deterministic outcome aggregation for the closed-loop update."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from app.graph.state import RecoveryState
from app.models.outcome_event import OutcomeEvent

def closed_loop_update_node(state: RecoveryState, session: Any | None = None)->dict[str,Any]:
    outcomes=[]
    if session is not None:
        outcomes=[row.outcome_type for row in session.query(OutcomeEvent).filter_by(case_id=state["case_id"]).all()]
    if state.get("outcome"):
        outcomes.append(state["outcome"])
    counts=dict(Counter(outcomes))
    update={"observations_seen":len(outcomes),"outcome_counts":counts,"updated_at":datetime.now(timezone.utc).isoformat()}
    return {"learning_updates":update}

update_from_outcomes=closed_loop_update_node
