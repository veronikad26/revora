"""
General API routes (FastAPI).

Responsibilities:
- Endpoints to trigger checkout-abandonment detection and overdue-
  receivable checks (the two entry points without an inbound webhook).
- Endpoints to inspect case state / audit trail for a given case_id,
  used by the Streamlit dashboard and the "one fully-traced case" demo.

No implementation yet — skeleton only.
"""
