from app.graph.nodes.execution import execution_node
from app.graph.nodes.observation import observation_node
from app.graph.nodes.closed_loop_update import closed_loop_update_node
from app.graph.state import new_case_state

def test_execution_is_dry_run_and_increments_retry():
    state=new_case_state(case_id="c1",entry_point="failure",customer_id="u1",payment_id="pay-1")
    state.update({"authorized_action":"retry"})
    result=execution_node(state)
    assert result["already_attempted_flag"] is True
    assert result["retry_count"]==1

def test_observation_and_learning_return_appendable_updates():
    state=new_case_state(case_id="c2",entry_point="failure",customer_id="u1")
    state.update({"authorized_action":"do_nothing","outcome":"do_nothing"})
    observed=observation_node(state)
    state.update(observed)
    learned=closed_loop_update_node(state)
    assert len(observed["audit_trail"])==1
    assert learned["learning_updates"]["observations_seen"]==1
