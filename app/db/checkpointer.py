"""
LangGraph SQLite checkpointer setup (PRD Section 4.1 / 10).

Responsibilities:
- Configure LangGraph's SQLite-backed checkpointer so that case state
  (app/graph/state.py) persists across graph runs — required for
  long-running cases sitting in NEGOTIATING while waiting on a
  promised date.
- Expose the checkpointer instance for app/graph/build_graph.py to
  attach when compiling the graph.

No implementation yet — skeleton only.
"""
