"""
Assembles the Revora LangGraph StateGraph (PRD Section 4.2 — Graph Flow).

Responsibilities:
- Instantiate a StateGraph using the schema from state.py.
- Register each node from app/graph/nodes/:
    diagnosis -> recovery_router -> consent_gate ->
    (execution | communication -> trust_firewall) -> policy_engine ->
    observation -> closed_loop_update
- Wire conditional edges per app/graph/edges/routing.py so that
  guardrail checkpoints (Consent Gate, Policy Engine) cannot be
  bypassed by any path through the graph.
- Attach the SQLite checkpointer (app/db/checkpointer.py) for
  persistent, resumable case state.
- Compile and return the runnable graph for app/main.py to invoke.

No implementation yet — skeleton only.
"""
