"""Tests for the FastAPI HTTP surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_root_returns_service_metadata() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"]
    assert body["plan"] == "POST /plan"


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_plan_endpoint_returns_itinerary() -> None:
    resp = client.post(
        "/plan",
        json={"origin": "San Francisco", "destination": "Los Angeles", "days": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_name"].startswith("San Francisco")
    assert body["costs"]["total_usd"] > 0
    assert body["stops"]


def test_plan_endpoint_rejects_empty_request() -> None:
    # No idea/destination/direction/anchor -> validation error (422).
    resp = client.post("/plan", json={"days": 3})
    assert resp.status_code == 422
