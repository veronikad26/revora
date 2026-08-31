"""FastAPI application entry point for Revora Phase 8."""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from app.api.routes import router as case_router
from app.api.webhooks import router as webhook_router
from app.db.database import init_db
from app.graph.build_graph import build_graph


def create_app(*, graph: Any | None = None, checkpoint_path: str | Path | None = None, initialize_db: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if initialize_db:
            init_db()
        if getattr(application.state, "graph", None) is None:
            application.state.graph = graph or build_graph(checkpoint_path=checkpoint_path)
        yield

    application = FastAPI(title="Revora RecoverAI API", version="0.1.0", lifespan=lifespan)
    application.include_router(case_router)
    application.include_router(webhook_router)
    return application


app = create_app()