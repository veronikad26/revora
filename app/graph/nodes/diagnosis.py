"""Deterministic Diagnosis node for all three RecoverAI entry points."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.graph.state import RecoveryState
from app.models.root_cause_classification import RootCauseClassification
from app.rules.abandonment_scorer import score_checkout
from app.rules.confidence_heuristic import ConfidenceResult, calculate_confidence, score_known_reason


RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "root_cause_rules.yaml"


@lru_cache(maxsize=1)
def load_root_cause_rules() -> dict[str, Any]:
    """Load the checked-in rule table once per process."""

    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _failure_classification(state: RecoveryState) -> tuple[str, ConfidenceResult, str]:
    """Classify a payment failure by granular gateway reason."""

    table = load_root_cause_rules()
    rules = table.get("rules", [])
    gateway_reason = _normalise(state.get("gateway_reason"))
    method = _normalise(state.get("method"))
    known_reasons = [rule.get("reason", "") for rule in rules]
    confidence = score_known_reason(gateway_reason, known_reasons)

    matching_rule = next(
        (rule for rule in rules if _normalise(rule.get("reason")) == gateway_reason),
        None,
    )
    if matching_rule:
        category = matching_rule.get("category", table.get("default_category", "technical_unclassified"))
        allowed_sources = {_normalise(item) for item in str(matching_rule.get("source", "")).split(",")}
        if method and allowed_sources and method not in allowed_sources and "common" not in allowed_sources:
            confidence = calculate_confidence(ambiguous_match=True)
            return category, confidence, f"known reason {gateway_reason!r} but method {method!r} is outside configured source"
        return category, confidence, f"matched gateway reason {gateway_reason!r}: {matching_rule.get('description', '')}".strip()

    category = table.get("default_category", "technical_unclassified")
    return category, confidence, f"unrecognized gateway reason {gateway_reason!r}; defaulted to {category}"


def _abandonment_classification(state: RecoveryState) -> tuple[str, ConfidenceResult, str]:
    """Classify checkout abandonment using behavioral signals, not decline codes."""

    payload = dict(state)
    last_activity = payload.get("last_activity_at")
    if isinstance(last_activity, str) and last_activity:
        payload["last_activity_at"] = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
    if not payload.get("last_activity_at"):
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            payload["created_at"] = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    checkpoint_time = payload.get("updated_at") or payload.get("created_at")
    if isinstance(checkpoint_time, str):
        checkpoint_time = datetime.fromisoformat(checkpoint_time.replace("Z", "+00:00"))
    result = score_checkout(payload, now=checkpoint_time) if checkpoint_time else score_checkout(payload)
    confidence = calculate_confidence(
        exact_match=result.score >= 0.50,
        ambiguous_match=0 < result.score < 0.50,
        signal_present=result.score > 0,
    )
    return "abandoned_checkout", confidence, f"behavioral abandonment score={result.score:.4f}; " + "; ".join(result.signals)


def _classify(state: RecoveryState) -> tuple[str, ConfidenceResult, str]:
    entry_point = state.get("entry_point")
    if entry_point == "abandonment":
        return _abandonment_classification(state)
    if entry_point == "receivable":
        return "overdue_invoice", calculate_confidence(exact_match=True), "entry point is an overdue receivable"
    if entry_point == "failure":
        return _failure_classification(state)
    return "technical_unclassified", calculate_confidence(signal_present=False), "missing or unsupported entry point"


def diagnosis_node(state: RecoveryState, session: Any | None = None) -> dict[str, Any]:
    """Return a partial state update and optionally persist its classification."""

    category, confidence, reason = _classify(state)
    event_id = state.get("event_id") or state["case_id"]
    learned = dict(state.get("learning_updates") or {}).get("confidence_adjustments", {})
    adjusted_score = max(0.0, min(1.0, confidence.score + float(learned.get(category, 0.0))))
    if learned.get(category):
        reason += f"; learned confidence adjustment={float(learned[category]):+.4f}"
    update: dict[str, Any] = {
        "root_cause_category": category,
        "confidence": round(adjusted_score, 4),
        "diagnosis_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if session is not None:
        session.add(
            RootCauseClassification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                event_type=state.get("event_type") or state.get("entry_point", "unknown"),
                category=category,
                confidence=adjusted_score,
                reason=reason,
            )
        )
    return update


diagnose = diagnosis_node
run_diagnosis = diagnosis_node