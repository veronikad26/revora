"""Offline Phase 9 evaluation harness tests."""
from evaluation.batch_generator import generate_cases
from evaluation.baselines import do_nothing, naive_baseline
from evaluation.customer_simulator import simulate_customer
from evaluation.metrics import compare_conditions, summarize_results
from evaluation.run_batch import run_batch


def test_batch_is_reproducible_and_public_input_hides_profile():
    first = generate_cases(12, seed=7)
    second = generate_cases(12, seed=7)
    assert first == second
    assert "hidden_profile" not in first[0].as_dict()
    assert "expected_category" not in first[0].as_dict()


def test_simulator_is_reproducible_for_same_case_and_action():
    case = generate_cases(1, seed=42)[0]
    assert simulate_customer(case, "retry", seed=99) == simulate_customer(case, "retry", seed=99)


def test_baselines_have_expected_distinct_behavior():
    case = generate_cases(3, seed=3)[0]
    assert do_nothing(case)["action"] == "do_nothing"
    assert naive_baseline(case)["authorized"] is True


def test_metrics_calculate_recovery_and_breakdowns():
    records = [{"case": {"amount": 100, "entry_point": "failure", "expected_category": "technical_unclassified"}, "action": "retry", "outcome": "recovered", "recovered_amount": 100}]
    metrics = summarize_results(records)
    assert metrics["recovery_rate"] == 1.0
    assert metrics["by_entry_point"]["failure"]["recovered"] == 100


def test_compare_conditions_reports_uplift():
    rows = [{"case": {"amount": 100, "entry_point": "failure"}, "action": "retry", "recovered_amount": 100}]
    report = compare_conditions({"do_nothing": [{"case": {"amount": 100}, "recovered_amount": 0}], "revora": rows})
    assert report["do_nothing"]["uplift_amount_vs_revora"] == 100
    assert report["do_nothing"]["uplift_multiple_vs_revora"] is None


def test_batch_runner_returns_three_conditions():
    report = run_batch(6, seed=11)
    assert report["count"] == 6
    assert set(report["metrics"]) == {"do_nothing", "naive", "revora"}
    assert len(report["results"]["revora"]) == 6
