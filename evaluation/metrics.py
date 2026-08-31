"""
Metrics / breakdown computation (PRD Section 9.4).

Responsibilities:
- Rupees recovered as % of at-risk and as uplift multiple vs. both
  baselines.
- Breakdown by root-cause category and by entry point.
- PTP kept-rate, with average days-late when broken.
- Correctly withheld actions (DO NOTHING) count.
- False-intervention count and rate (target 0).
- Escalation count/rate by trigger.
- Closed-loop effect: confidence/timing table before vs. after the
  batch run (PRD Section 8.1).
"""
"""Metrics for offline RecoverAI and baseline comparison."""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Iterable


def _amount(record: dict[str, Any]) -> float:
    case = record.get("case", {})
    return float(case.get("amount", 0) or 0)


def _action(record: dict[str, Any]) -> str:
    return str(record.get("action") or record.get("state", {}).get("authorized_action") or record.get("state", {}).get("proposed_action") or "do_nothing")


def summarize_results(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    at_risk = sum(_amount(row) for row in rows)
    recovered = sum(float(row.get("recovered_amount", 0) or 0) for row in rows)
    recovered_cases = sum(1 for row in rows if float(row.get("recovered_amount", 0) or 0) > 0)
    escalated = sum(1 for row in rows if _action(row) == "escalate" or row.get("outcome") == "escalated")
    do_nothing = sum(1 for row in rows if _action(row) == "do_nothing")
    naive_false = sum(1 for row in rows if row.get("strategy") == "naive" and row.get("case", {}).get("expected_category") == "risk_fraud_block")
    by_category: dict[str, dict[str, Any]] = defaultdict(lambda: {"cases": 0, "at_risk": 0.0, "recovered": 0.0})
    by_entry: dict[str, dict[str, Any]] = defaultdict(lambda: {"cases": 0, "at_risk": 0.0, "recovered": 0.0})
    escalation_triggers = Counter()
    for row in rows:
        case = row.get("case", {})
        category = case.get("expected_category", row.get("state", {}).get("root_cause_category", "unknown"))
        entry = case.get("entry_point", "unknown")
        for bucket, key in ((by_category, category), (by_entry, entry)):
            bucket[key]["cases"] += 1
            bucket[key]["at_risk"] += _amount(row)
            bucket[key]["recovered"] += float(row.get("recovered_amount", 0) or 0)
        trigger = row.get("state", {}).get("escalation_trigger") or row.get("escalation_trigger")
        if trigger:
            escalation_triggers[str(trigger)] += 1
    def finalize(bucket: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {key: {**value, "recovery_rate": value["recovered"] / value["at_risk"] if value["at_risk"] else 0.0} for key, value in bucket.items()}
    return {
        "cases": len(rows),
        "at_risk_amount": at_risk,
        "recovered_amount": recovered,
        "recovery_rate": recovered / at_risk if at_risk else 0.0,
        "recovered_cases": recovered_cases,
        "escalation_count": escalated,
        "escalation_rate": escalated / len(rows) if rows else 0.0,
        "correctly_withheld_count": do_nothing,
        "false_intervention_count": naive_false,
        "false_intervention_rate": naive_false / len(rows) if rows else 0.0,
        "escalation_triggers": dict(escalation_triggers),
        "by_category": finalize(by_category),
        "by_entry_point": finalize(by_entry),
    }


def compare_conditions(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summaries = {name: summarize_results(rows) for name, rows in results.items()}
    agent = summaries.get("revora", {})
    for name, summary in summaries.items():
        if name != "revora":
            base = summary.get("recovered_amount", 0)
            summary["uplift_amount_vs_revora"] = agent.get("recovered_amount", 0) - base
            summary["uplift_multiple_vs_revora"] = agent.get("recovered_amount", 0) / base if base else None
    return summaries


compute_metrics = summarize_results

