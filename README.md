# Revora — Root-Cause Revenue Recovery Agent

Agentic revenue-recovery system built on LangGraph. Detects revenue at risk
across payment failures, checkout abandonment, and overdue receivables;
diagnoses root cause; determines a bounded intervention; executes it through
a deterministic guardrail/policy layer; and measures recovered revenue
against baselines on a synthetic batch.

See `PRD` (project docs) for full architecture, tech stack, guardrails,
and evaluation methodology.

## Project layout
- `app/graph/` — LangGraph state, nodes, and edge/routing logic
- `app/models/` — data entities (SQLite-backed)
- `app/integrations/` — Razorpay, Twilio WhatsApp, Gemini API clients
- `app/rules/` — deterministic rule tables, confidence heuristic, playbooks
- `app/db/` — SQLite setup, schema, LangGraph checkpointer
- `app/api/` — FastAPI webhook/route entrypoints
- `evaluation/` — synthetic batch generator, customer simulator, baselines, metrics
- `dashboard/` — Streamlit dashboard
- `data/` — synthetic batches and seed data
- `tests/` — unit tests per guardrail/node

This is a skeleton only — no business logic is implemented yet.

## Status
Scaffold — not yet implemented.
