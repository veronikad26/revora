"""Transparent deterministic customer-response simulator for evaluation."""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Any


@dataclass(frozen=True)
class SimulatedReply:
    text: str
    outcome: str
    probability: float
    intent: dict[str, Any]


def simulate_customer(case: Any, action: str, *, seed: int | None = None) -> SimulatedReply:
    """Sample one visible reply; hidden labels are read only by the evaluator."""
    profile = getattr(case, "hidden_profile", None) or case.get("hidden_profile", "unrecoverable")
    rng = random.Random(seed if seed is not None else hash((getattr(case, "case_id", ""), action)) & 0xFFFFFFFF)
    if profile.startswith("recoverable") and action in {"retry", "notify", "nudge", "negotiate"}:
        probability = 0.85 if action in {"retry", "nudge"} else 0.70
        if rng.random() < probability:
            if action == "retry":
                return SimulatedReply("Payment retry completed successfully.", "recovered", probability, {"amount_acknowledged": True})
            return SimulatedReply("I will take care of the invoice today.", "promise", probability, {"amount_acknowledged": True, "promise_date": "today"})
    if action in {"notify", "nudge", "negotiate"} and rng.random() < 0.10:
        return SimulatedReply("STOP", "opted_out", 0.10, {"opt_out": True})
    if profile == "unrecoverable":
        return SimulatedReply("I cannot complete this payment.", "refusal", 1.0, {"refusal": True})
    return SimulatedReply("No response received.", "no_response", 1.0 - (0.85 if action in {"retry", "nudge"} else 0.70), {})


simulate_response = simulate_customer