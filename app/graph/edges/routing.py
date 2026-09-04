"""Conditional edge functions for the assembled RecoverAI graph."""
from __future__ import annotations

from typing import Literal

from app.graph.state import RecoveryState


MESSAGE_ACTIONS = {"notify", "nudge", "negotiate"}


def entry_route(
    state: RecoveryState,
) -> Literal[
    "diagnosis",
    "communication_inbound",
    "recovery_router",
]:
    event = state.get("pending_event")

    if event == "inbound_reply":
        return "communication_inbound"

    if event == "consent_granted":
        return "recovery_router"

    return "diagnosis"


def after_router(
    state: RecoveryState,
) -> Literal["consent_gate", "policy_engine"]:
    """Route message actions through consent; all other actions go to policy."""

    if state.get("proposed_action") in MESSAGE_ACTIONS:
        return "consent_gate"

    return "policy_engine"


def after_consent(
    state: RecoveryState,
) -> Literal["communication", "policy_engine"]:
    """Only consented customers enter the outbound communication path."""

    if (
        state.get("contact_allowed")
        and not state.get("opt_out")
    ):
        return "communication"

    return "policy_engine"


def after_communication(
    state: RecoveryState,
) -> Literal["trust_firewall", "policy_engine"]:
    """Every generated outbound message is checked by the firewall."""

    if state.get("draft_message"):
        return "trust_firewall"

    return "policy_engine"


def after_firewall(
    state: RecoveryState,
) -> Literal["policy_engine"]:
    """Never loop back from the firewall.

    A generated message gets exactly one deterministic safety review.
    If it passes, Policy Engine may authorize execution.
    If it is blocked, Policy Engine receives the blocked state and can
    escalate the case.

    This intentionally removes the communication -> firewall ->
    communication cycle that was capable of exhausting LangGraph's
    recursion limit.
    """

    return "policy_engine"


def after_policy(
    state: RecoveryState,
) -> Literal["execution"]:
    return "execution"


def after_execution(
    state: RecoveryState,
) -> Literal["observation"]:
    return "observation"


def after_observation(
    state: RecoveryState,
) -> Literal["closed_loop_update"]:
    return "closed_loop_update"


def after_closed_loop(
    state: RecoveryState,
) -> Literal["end"]:
    return "end"


route_after_router = after_router
route_after_consent = after_consent
route_after_communication = after_communication
route_after_firewall = after_firewall