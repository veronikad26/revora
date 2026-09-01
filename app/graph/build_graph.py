"""Assembly of the guarded RecoverAI LangGraph StateGraph."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from langgraph.graph import END, START, StateGraph
from app.db.checkpointer import create_checkpointer
from app.graph.edges.routing import after_closed_loop, after_communication, after_consent, after_execution, after_firewall, after_observation, after_policy, after_router
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


def build_graph(*, checkpointer: Any | None = None, checkpoint_path: str | Path | None = None):
    """Build the compiled graph.

    Node wrappers intentionally use the safe default clients. Provider clients
    are injected in direct node tests or can be supplied later through the
    application dependency container.
    """
    graph = StateGraph(RecoveryState)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("recovery_router", recovery_router_node)
    graph.add_node("consent_gate", consent_gate_node)
    graph.add_node("communication", communication_node)
    graph.add_node("trust_firewall", trust_firewall_node)
    graph.add_node("policy_engine", policy_engine_node)
    graph.add_node("execution", execution_node)
    graph.add_node("observation", observation_node)
    graph.add_node("closed_loop_update", closed_loop_update_node)

    graph.add_edge(START, "diagnosis")
    graph.add_edge("diagnosis", "recovery_router")
    graph.add_conditional_edges("recovery_router", after_router, {"consent_gate": "consent_gate", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("consent_gate", after_consent, {"communication": "communication", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("communication", after_communication, {"trust_firewall": "trust_firewall", "policy_engine": "policy_engine"})
    graph.add_conditional_edges("trust_firewall", after_firewall, {"policy_engine": "policy_engine", "communication": "communication", "end": END})
    graph.add_conditional_edges("policy_engine", after_policy, {"execution": "execution"})
    graph.add_conditional_edges("execution", after_execution, {"observation": "observation"})
    graph.add_conditional_edges("observation", after_observation, {"closed_loop_update": "closed_loop_update"})
    graph.add_conditional_edges("closed_loop_update", after_closed_loop, {"end": END})

    saver = checkpointer if checkpointer is not None else create_checkpointer(checkpoint_path)
    return graph.compile(checkpointer=saver)


create_graph = build_graph
