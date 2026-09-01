"""Assembly of the guarded RecoverAI LangGraph StateGraph."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from langgraph.graph import END, START, StateGraph
from app.db.checkpointer import create_checkpointer
from app.graph.edges.routing import after_communication, after_consent, after_firewall, after_router, entry_route
from app.graph.nodes.closed_loop_update import closed_loop_update_node
from app.graph.nodes.communication import communication_node
from app.graph.nodes.consent_gate import consent_gate_node
from app.graph.nodes.diagnosis import diagnosis_node
from app.graph.nodes.execution import execution_node
from app.graph.nodes.observation import observation_node
from app.graph.nodes.policy_engine import policy_engine_node
from app.graph.nodes.recovery_router import recovery_router_node
from app.graph.nodes.trust_firewall import trust_firewall_node
from app.graph.state import RecoveryState


def inbound_communication_node(state: RecoveryState) -> dict[str, Any]:
    """Parse a queued customer reply, then clear the one-shot event marker."""
    update = communication_node(state, mode="inbound")
    return {**update, "pending_event": None, "draft_message": None, "authorized_action": None}


def build_graph(*, checkpointer: Any | None = None, checkpoint_path: str | Path | None = None):
    graph = StateGraph(RecoveryState)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("recovery_router", recovery_router_node)
    graph.add_node("consent_gate", consent_gate_node)
    graph.add_node("communication", communication_node)
    graph.add_node("communication_inbound", inbound_communication_node)
    graph.add_node("trust_firewall", trust_firewall_node)
    graph.add_node("policy_engine", policy_engine_node)
    graph.add_node("execution", execution_node)
    graph.add_node("observation", observation_node)
    graph.add_node("closed_loop_update", closed_loop_update_node)
    graph.add_conditional_edges(START, entry_route, {"diagnosis": "diagnosis", "communication_inbound": "communication_inbound", "recovery_router": "recovery_router"})
    graph.add_edge("communication_inbound", "recovery_router")
    graph.add_edge("diagnosis", "recovery_router")
    graph.add_conditional_edges("recovery_router", after_router, {"consent_gate": "consent_gate", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("consent_gate", after_consent, {"communication": "communication", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("communication", after_communication, {"trust_firewall": "trust_firewall", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("trust_firewall", after_firewall, {"policy_engine": "policy_engine", "communication": "communication", "end": END})
    graph.add_edge("policy_engine", "execution")
    graph.add_edge("execution", "observation")
    graph.add_edge("observation", "closed_loop_update")
    graph.add_edge("closed_loop_update", END)
    saver = checkpointer if checkpointer is not None else create_checkpointer(checkpoint_path)
    return graph.compile(checkpointer=saver)


create_graph = build_graph