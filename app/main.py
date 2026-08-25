"""
FastAPI application entrypoint.

Responsibilities (per PRD):
- Boot the FastAPI app and wire up API routers (app/api/).
- Initialize the SQLite database and LangGraph checkpointer on startup.
- Compile and hold a reference to the Revora LangGraph agent
  (see app/graph/build_graph.py) so incoming events can be dispatched
  into it.

No implementation yet — skeleton only.
"""
