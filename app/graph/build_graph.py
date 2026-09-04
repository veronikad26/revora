"""Assembly of the guarded RecoverAI LangGraph StateGraph."""
from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.db.checkpointer import create_checkpointer
from app.graph.edges.routing import (
    after_communication,
    after_consent,
    after_firewall,
    after_router,
    entry_route,
)
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


def inbound_communication_node(
    state: RecoveryState,
    session: Any | None = None,
) -> dict[str, Any]:
    """Parse a queued customer reply and clear the one-shot event marker."""

    update = communication_node(
        state,
        mode="inbound",
        session=session,
    )

    return {
        **update,
        "pending_event": None,
        "draft_message": None,
        "authorized_action": None,
    }


def _with_session(
    node_fn: Callable[..., dict[str, Any]],
    session_factory: Callable[[], Any],
) -> Callable[[RecoveryState], dict[str, Any]]:
    """Wrap a graph node in a short-lived committed DB session."""

    @wraps(node_fn)
    def wrapped(
        state: RecoveryState,
    ) -> dict[str, Any]:
        session = session_factory()

        try:
            result = node_fn(
                state,
                session=session,
            )
            session.commit()
            return result

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()

    return wrapped


def build_graph(
    *,
    checkpointer: Any | None = None,
    checkpoint_path: str | Path | None = None,
    session_factory: Callable[[], Any] | None = None,
):
    graph = StateGraph(RecoveryState)

    if session_factory is not None:
        diagnosis = _with_session(
            diagnosis_node,
            session_factory,
        )

        consent_gate = _with_session(
            consent_gate_node,
            session_factory,
        )

        communication = _with_session(
            communication_node,
            session_factory,
        )

        communication_inbound = _with_session(
            inbound_communication_node,
            session_factory,
        )

        trust_firewall = _with_session(
            trust_firewall_node,
            session_factory,
        )

        policy_engine = _with_session(
            policy_engine_node,
            session_factory,
        )

        execution = _with_session(
            execution_node,
            session_factory,
        )

        observation = _with_session(
            observation_node,
            session_factory,
        )

        closed_loop_update = _with_session(
            closed_loop_update_node,
            session_factory,
        )

    else:
        diagnosis = diagnosis_node
        consent_gate = consent_gate_node
        communication = communication_node
        communication_inbound = inbound_communication_node
        trust_firewall = trust_firewall_node
        policy_engine = policy_engine_node
        execution = execution_node
        observation = observation_node
        closed_loop_update = closed_loop_update_node

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    graph.add_node("diagnosis", diagnosis)
    graph.add_node("recovery_router", recovery_router_node)
    graph.add_node("consent_gate", consent_gate)
    graph.add_node("communication", communication)
    graph.add_node(
        "communication_inbound",
        communication_inbound,
    )
    graph.add_node("trust_firewall", trust_firewall)
    graph.add_node("policy_engine", policy_engine)
    graph.add_node("execution", execution)
    graph.add_node("observation", observation)
    graph.add_node(
        "closed_loop_update",
        closed_loop_update,
    )

    # ------------------------------------------------------------------
    # Entry routing
    # ------------------------------------------------------------------

    graph.add_conditional_edges(
        START,
        entry_route,
        {
            "diagnosis": "diagnosis",
            "communication_inbound": "communication_inbound",
            "recovery_router": "recovery_router",
        },
    )

    # Inbound customer reply.
    graph.add_edge(
        "communication_inbound",
        "recovery_router",
    )

    # Normal case diagnosis.
    graph.add_edge(
        "diagnosis",
        "recovery_router",
    )

    # ------------------------------------------------------------------
    # Recovery routing
    # ------------------------------------------------------------------

    graph.add_conditional_edges(
        "recovery_router",
        after_router,
        {
            "consent_gate": "consent_gate",
            "policy_engine": "policy_engine",
        },
    )

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    graph.add_conditional_edges(
        "consent_gate",
        after_consent,
        {
            "communication": "communication",
            "policy_engine": "policy_engine",
        },
    )

    # ------------------------------------------------------------------
    # Communication and Trust Firewall
    #
    # IMPORTANT:
    # There is deliberately NO edge from trust_firewall back to
    # communication. This makes the outbound path acyclic.
    # ------------------------------------------------------------------

    graph.add_conditional_edges(
        "communication",
        after_communication,
        {
            "trust_firewall": "trust_firewall",
            "policy_engine": "policy_engine",
        },
    )

    graph.add_conditional_edges(
        "trust_firewall",
        after_firewall,
        {
            "policy_engine": "policy_engine",
        },
    )

    # ------------------------------------------------------------------
    # Authorization → execution → observation → learning
    # ------------------------------------------------------------------

    graph.add_edge(
        "policy_engine",
        "execution",
    )

    graph.add_edge(
        "execution",
        "observation",
    )

    graph.add_edge(
        "observation",
        "closed_loop_update",
    )

    graph.add_edge(
        "closed_loop_update",
        END,
    )

    saver = (
        checkpointer
        if checkpointer is not None
        else create_checkpointer(checkpoint_path)
    )

    return graph.compile(checkpointer=saver)


create_graph = build_graph