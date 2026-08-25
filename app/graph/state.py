"""
LangGraph state schema — the persisted object that represents one
recovery case as it moves through the graph (PRD Section 4.3).

Fields to define here (per PRD):
- case_id, entry_point (failure | abandonment | receivable)
- root_cause_category, confidence
- retry_count, contact_count, consent_flag, already_attempted_flag
- ptp_state (DETECTED...ESCALATED), promised_date, dispute_flag
- conversation_history (for the Communication node)
- outcome (recovered | broken | escalated | do_nothing), timestamps

This state object is what SQLite-backed checkpointing persists between
graph runs (see app/db/checkpointer.py).

No implementation yet — skeleton only.
"""
