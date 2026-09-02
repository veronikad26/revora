"""FastAPI application entry point for Revora Phase 8."""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from app.api.routes import router as case_router
from app.api.webhooks import router as webhook_router
from app.config import LANGGRAPH_CHECKPOINT_PATH
from app.db.database import SessionLocal, init_db
from app.graph.build_graph import build_graph


def create_app(*, graph: Any | None = None, checkpoint_path: str | Path | None = None, initialize_db: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if initialize_db:
            init_db()
        if getattr(application.state, "graph", None) is None:
            # Resolve the checkpoint path once, at graph-build time. A caller
            # can still explicitly pass checkpoint_path=None (e.g. for a
            # deliberately ephemeral MemorySaver in tests); the default here
            # only kicks in when checkpoint_path wasn't specified at all,
            # which is how every previous call site (including `app = create_app()`
            # below) was implicitly getting MemorySaver and losing all case
            # state on every restart.
            resolved_checkpoint_path = checkpoint_path if checkpoint_path is not None else LANGGRAPH_CHECKPOINT_PATH
            # session_factory=SessionLocal is what makes a real API/webhook run
            # actually persist ConsentFlag opt-outs and the AuditLogEntry trail
            # (including risk_ops_flag routing), instead of those guardrail
            # decisions only living in graph state for the single invocation.
            application.state.graph = graph or build_graph(checkpoint_path=resolved_checkpoint_path, session_factory=SessionLocal)
        yield

    application = FastAPI(title="Revora RecoverAI API", version="0.1.0", lifespan=lifespan)
    application.include_router(case_router)
    application.include_router(webhook_router)
    return application


app = create_app()