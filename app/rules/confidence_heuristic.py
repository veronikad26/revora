"""
Deterministic confidence heuristic (PRD Section 5.1).

Responsibilities:
- Given a diagnosed case, compute a confidence score without a
  trained ML model:
    - exact known decline-code match -> high confidence
    - partial/ambiguous match or first-seen pattern -> lower confidence
- Below CONFIDENCE_THRESHOLD (app/config.py), the Recovery Router
  routes the case to human review instead of guessing.
- Weights/table here are the target of the closed-loop update node
  (app/graph/nodes/closed_loop_update.py), which adjusts them based
  on observed outcomes.

No implementation yet — skeleton only.
"""
"""Deterministic confidence scoring for root-cause diagnosis.

The PRD intentionally avoids a trained classifier. This module therefore uses
small, explicit scores that can be inspected, tested, and adjusted by the
closed-loop updater in a later phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.config import CONFIDENCE_THRESHOLD

EXACT_MATCH_SCORE = 0.95
PARTIAL_MATCH_SCORE = 0.75
AMBIGUOUS_MATCH_SCORE = 0.60
FIRST_SEEN_SCORE = 0.35
MISSING_SIGNAL_SCORE = 0.20


@dataclass(frozen=True)
class ConfidenceResult:
    """Explainable confidence output consumed by the Diagnosis node."""

    score: float
    match_type: str
    reason: str

    @property
    def is_above_threshold(self) -> bool:
        return self.score >= CONFIDENCE_THRESHOLD

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "match_type": self.match_type,
            "reason": self.reason,
            "is_above_threshold": self.is_above_threshold,
        }


def clamp_score(score: float) -> float:
    """Keep externally supplied or learned weights within the valid range."""

    return round(max(0.0, min(1.0, float(score))), 4)


def calculate_confidence(
    *,
    exact_match: bool = False,
    partial_match: bool = False,
    ambiguous_match: bool = False,
    first_seen: bool = False,
    signal_present: bool = True,
) -> ConfidenceResult:
    """Calculate a deterministic score from match quality."""

    if exact_match:
        return ConfidenceResult(EXACT_MATCH_SCORE, "exact", "exact known pattern match")
    if partial_match:
        return ConfidenceResult(PARTIAL_MATCH_SCORE, "partial", "partial known pattern match")
    if ambiguous_match:
        return ConfidenceResult(AMBIGUOUS_MATCH_SCORE, "ambiguous", "ambiguous pattern match")
    if first_seen:
        return ConfidenceResult(FIRST_SEEN_SCORE, "first_seen", "first-seen or unrecognized pattern")
    if not signal_present:
        return ConfidenceResult(MISSING_SIGNAL_SCORE, "missing", "required diagnostic signal is missing")
    return ConfidenceResult(FIRST_SEEN_SCORE, "unclassified", "no recognized pattern match")


def score_known_reason(
    reason: str | None,
    known_reasons: Iterable[str],
    *,
    allow_partial: bool = True,
) -> ConfidenceResult:
    """Score a gateway reason against the configured known-reason table."""

    normalized = (reason or "").strip().lower()
    known = {str(item).strip().lower() for item in known_reasons if str(item).strip()}
    if not normalized:
        return calculate_confidence(signal_present=False)
    if normalized in known:
        return calculate_confidence(exact_match=True)
    if allow_partial and any(normalized in item or item in normalized for item in known):
        return calculate_confidence(partial_match=True)
    return calculate_confidence(first_seen=True)


def is_actionable_confidence(score: float, threshold: float = CONFIDENCE_THRESHOLD) -> bool:
    """Return whether a score meets the configured action threshold."""

    return clamp_score(score) >= threshold


compute_confidence = calculate_confidence
confidence_for_reason = score_known_reason