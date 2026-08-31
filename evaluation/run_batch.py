"""
Batch runner (PRD Section 9 / 10).

Responsibilities:
- Load a synthetic batch (batch_generator.py).
- Run all three conditions (do_nothing, naive_baseline, Revora graph)
  against the identical batch, using customer_simulator.py to produce
  outcomes.
- Persist results for metrics.py / dashboard/streamlit_app.py to read.
"""
"""Run identical synthetic cases through Revora and comparison baselines."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from app.graph.build_graph import build_graph
from app.graph.state import new_case_state
from evaluation.batch_generator import EvaluationCase, generate_cases
from evaluation.baselines import BASELINES
from evaluation.customer_simulator import simulate_customer
from evaluation.metrics import compare_conditions


def _to_state(case: EvaluationCase) -> dict[str, Any]:
    return new_case_state(**{key: value for key, value in case.as_dict(include_hidden=False).items() if key in {"case_id", "entry_point", "customer_id", "amount", "currency", "payment_id", "gateway_reason", "method", "cart_id", "cart_value", "funnel_stage_reached", "last_activity_at", "prior_abandonment_count", "invoice_payment_ref"}})


def run_condition(cases: list[EvaluationCase], strategy: str, *, graph: Any | None = None, seed: int = 42) -> list[dict[str, Any]]:
    if strategy not in {"revora", *BASELINES}:
        raise ValueError(f"unknown strategy: {strategy}")
    rows = []
    for index, case in enumerate(cases):
        if strategy == "revora":
            state = _to_state(case)
            output = graph.invoke(state, config={"configurable": {"thread_id": case.case_id}})
            action = output.get("authorized_action") or output.get("proposed_action") or "do_nothing"
        else:
            output = BASELINES[strategy](case)
            action = output["action"]
        reply = simulate_customer(case, action, seed=seed + index)
        recovered = float(case.amount) if reply.outcome == "recovered" else 0.0
        rows.append({"case": case.as_dict(include_hidden=True), "strategy": strategy, "action": action, "state": output, "outcome": reply.outcome, "reply": reply.text, "recovered_amount": recovered})
    return rows


def run_batch(count: int = 100, *, seed: int = 42, output_path: str | Path | None = None) -> dict[str, Any]:
    cases = generate_cases(count, seed=seed)
    results: dict[str, list[dict[str, Any]]] = {}
    for strategy in ("do_nothing", "naive", "revora"):
        results[strategy] = run_condition(cases, strategy, graph=build_graph(), seed=seed)
    report = {"seed": seed, "count": count, "metrics": compare_conditions(results), "results": results}
    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the Revora evaluation batch")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="evaluation/results.json")
    args = parser.parse_args()
    report = run_batch(args.count, seed=args.seed, output_path=args.output)
    print(json.dumps(report["metrics"], indent=2))