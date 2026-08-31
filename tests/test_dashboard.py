"""Phase 10 dashboard helper tests without launching a Streamlit server."""
import json

from dashboard.streamlit_app import flatten_breakdown, load_report


def test_load_report_returns_safe_empty_shape_for_missing_file(tmp_path):
    report = load_report(tmp_path / "missing.json")
    assert report["metrics"] == {}
    assert report["results"] == {}


def test_load_report_and_flatten_breakdown(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"metrics": {}, "results": {}, "seed": 42}), encoding="utf-8")
    report = load_report(path)
    assert report["seed"] == 42
    rows = flatten_breakdown({"by_category": {"technical_unclassified": {"cases": 2, "recovered": 100}}}, "by_category")
    assert rows == [{"name": "technical_unclassified", "cases": 2, "recovered": 100}]
