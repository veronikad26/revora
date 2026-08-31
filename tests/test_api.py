"""Phase 8 API tests using the local dry-run graph and SQLite database."""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.graph.build_graph import build_graph
from app.api.webhooks import normalize_razorpay_failure


def client():
    return TestClient(create_app(graph=build_graph(), initialize_db=True))


def test_health_reports_initialized_graph():
    with client() as http:
        response = http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "graph_ready": True}


def test_create_failure_runs_graph_and_is_idempotent():
    payment_id = f"pay-api-{uuid4().hex}"
    body = {"customer_id": "customer-api", "payment_id": payment_id, "amount": "500.00", "method": "card", "gateway_reason": "insufficient_funds"}
    with client() as http:
        response = http.post("/cases/failure", json=body)
        duplicate = http.post("/cases/failure", json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "processed"
    assert data["state"]["root_cause_category"] == "insufficient_balance"
    assert duplicate.status_code == 201
    assert duplicate.json()["status"] == "duplicate"


def test_case_lookup_returns_checkpointed_state():
    payment_id = f"pay-lookup-{uuid4().hex}"
    with client() as http:
        created = http.post("/cases/failure", json={"customer_id": "customer-lookup", "payment_id": payment_id, "amount": 100, "method": "card", "gateway_reason": "server_error"}).json()
        fetched = http.get(f"/cases/{created['case_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["state"]["case_id"] == created["case_id"]


def test_normalize_razorpay_payload_converts_paise_to_rupees():
    normalized = normalize_razorpay_failure({"id": "evt_1", "event": "payment.failed", "payload": {"payment": {"entity": {"id": "pay_1", "amount": 12500, "currency": "INR", "method": "card", "error_reason": "insufficient_funds", "email": "c@example.com"}}}})
    assert normalized["payment_id"] == "pay_1"
    assert normalized["amount"] == 125
    assert normalized["gateway_reason"] == "insufficient_funds"


def test_invalid_failure_payload_is_rejected():
    with client() as http:
        response = http.post("/cases/failure", json={"customer_id": "customer-api", "payment_id": "", "amount": 100})
    assert response.status_code == 422
