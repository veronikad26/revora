"""Conditional edge functions for the assembled RecoverAI graph."""
from __future__ import annotations
from typing import Literal
from app.graph.state import RecoveryState

MESSAGE_ACTIONS = {"notify", "nudge", "negotiate"}


def after_router(state: RecoveryState) -> Literal["consent_gate", "policy_engine"]:
    """Route all outreach through Consent Gate; non-outreach to Policy Engine."""
    return "consent_gate" if state.get("proposed_action") in MESSAGE_ACTIONS else "policy_engine"


def after_consent(state: RecoveryState) -> Literal["communication", "policy_engine"]:
    """Even denied consent reaches Policy Engine, never directly Execution."""
    return "communication" if state.get("contact_allowed") and not state.get("opt_out") else "policy_engine"


def after_communication(state: RecoveryState) -> Literal["trust_firewall", "policy_engine"]:
    """Only a generated draft enters the explicit firewall stage."""
    return "trust_firewall" if state.get("draft_message") else "policy_engine"


def after_firewall(state: RecoveryState) -> Literal["policy_engine", "communication", "end"]:
    result = state.get("trust_firewall_result")
    if result == "pass":
        return "policy_engine"
    if state.get("trust_firewall_regenerations", 0) <= 1 and state.get("proposed_action") != "escalate":
        return "communication"
    return "policy_engine"


def after_policy(state: RecoveryState) -> Literal["execution"]:
    """All cases pass through execution after policy, which safely no-ops unauthorized actions."""
    return "execution"


def after_execution(state: RecoveryState) -> Literal["observation"]:
    return "observation"


def after_observation(state: RecoveryState) -> Literal["closed_loop_update"]:
    return "closed_loop_update"


def after_closed_loop(state: RecoveryState) -> Literal["end"]:
    return "end"


# Friendly aliases for graph assembly and tests.
route_after_router = after_router
route_after_consent = after_consent
route_after_communication = after_communication
route_after_firewall = after_firewall
route_after_policy = after_policy
