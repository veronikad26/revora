"""Metrics for offline RecoverAI and baseline comparison."""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Iterable
from app.config import CONFIDENCE_THRESHOLD


def _amount(record: dict[str, Any]) -> float:
    return float(record.get("case", {}).get("amount", 0) or 0)


def _action(record: dict[str, Any]) -> str:
    return str(record.get("action") or record.get("state", {}).get("authorized_action") or record.get("state", {}).get("proposed_action") or "do_nothing")


def _false_intervention_reason(record: dict[str, Any]) -> str | None:
    if record.get("strategy") != "naive":
        return None
    case = record.get("case", {})
    action = _action(record)
    category = case.get("expected_category")
    consent = bool(case.get("consent_flag", False))
    confidence = case.get("confidence")
    if category == "risk_fraud_block" and action != "risk_ops_flag":
        return "risk_fraud_block_violation"
    if action in {"notify", "nudge", "negotiate"} and not consent:
        return "consent_violation"
    if action == "retry" and confidence is not None and float(confidence) < CONFIDENCE_THRESHOLD:
        return "confidence_threshold_violation"
    if case.get("expected_safe_action") in {"escalate", "do_nothing", "risk_ops_flag"} and action not in {"escalate", "do_nothing", "risk_ops_flag"}:
        return "expected_safe_action_violation"
    return None


def summarize_results(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    at_risk = sum(_amount(row) for row in rows)
    recovered = sum(float(row.get("recovered_amount", 0) or 0) for row in rows)
    recovered_cases = sum(1 for row in rows if float(row.get("recovered_amount", 0) or 0) > 0)
    escalated = sum(1 for row in rows if _action(row) == "escalate" or row.get("outcome") == "escalated")
    do_nothing = sum(1 for row in rows if _action(row) == "do_nothing")
    false_reasons = Counter(reason for row in rows if (reason := _false_intervention_reason(row)))
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

    return {"cases": len(rows), "at_risk_amount": at_risk, "recovered_amount": recovered, "recovery_rate": recovered / at_risk if at_risk else 0.0, "recovered_cases": recovered_cases, "escalation_count": escalated, "escalation_rate": escalated / len(rows) if rows else 0.0, "correctly_withheld_count": do_nothing, "false_intervention_count": sum(false_reasons.values()), "false_intervention_rate": sum(false_reasons.values()) / len(rows) if rows else 0.0, "false_intervention_reasons": dict(false_reasons), "escalation_triggers": dict(escalation_triggers), "by_category": finalize(by_category), "by_entry_point": finalize(by_entry)}


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