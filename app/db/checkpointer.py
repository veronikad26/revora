"""Checkpoint factories for assembled RecoverAI graphs."""
from __future__ import annotations
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any


def create_checkpointer(db_path: str | Path | None = None) -> Any:
    """Create a LangGraph checkpointer.

    ``None`` returns ``MemorySaver`` for tests and local ephemeral runs. A
    filesystem path uses LangGraph's SQLite saver and persists state by
    thread/case ID across process restarts.
    """
    if db_path is None:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        raise RuntimeError("Install langgraph-checkpoint-sqlite for SQLite graph persistence") from exc
    path = str(Path(db_path))
    connection = __import__("sqlite3").connect(path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return saver


def get_checkpointer(db_path: str | Path | None = None) -> Any:
    """Compatibility alias used by ``build_graph.py``."""
    return create_checkpointer(db_path)
