from unittest.mock import patch
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import get_db
from src.main import app
from src.routers.logs import get_current_user

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def override_get_current_user():
    return {"username": "testuser", "id": "test-user-id"}


@pytest.fixture(autouse=True)
def apply_v2_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield

client = TestClient(app)


def setup():
    from src.database import Base

    Base.metadata.create_all(bind=engine)


def teardown():
    from src.database import Base

    Base.metadata.drop_all(bind=engine)


def test_v2_applications_and_policies():
    setup()
    # Create Application
    app_res = client.post(
        "/applications/",
        json={
            "name": "payment-service",
            "description": "Handles Stripe checkouts",
            "language": "python",
            "repository_url": "https://github.com/rutvej/payment-service",
        },
    )
    assert app_res.status_code == 201
    app_id = app_res.json()["id"]
    assert app_res.json()["name"] == "payment-service"

    # Create Escalation Policy (Threshold = 2 errors)
    policy_res = client.post(
        f"/applications/{app_id}/escalation-policies",
        json={
            "rule_type": "error_rate_threshold",
            "condition_value": 2,
            "window_seconds": 60,
            "severity_keywords": ["FATAL", "OOMKill"],
            "cooldown_minutes": 30,
        },
    )
    assert policy_res.status_code == 201
    assert policy_res.json()["condition_value"] == 2
    teardown()


@patch("pika.BlockingConnection")
def test_v2_deduplication_and_escalation(mock_pika):
    setup()
    # 1. Create App and Policy (threshold = 2)
    app_res = client.post("/applications/", json={"name": "checkout-api"})
    app_id = app_res.json()["id"]
    client.post(
        f"/applications/{app_id}/escalation-policies",
        json={"condition_value": 2, "window_seconds": 120},
    )

    # 2. Submit 1st log -> Should be Logged (1/2 in 120s)
    log1 = client.post(
        "/logs/",
        json={
            "app_name": "checkout-api",
            "content": "Timeout connecting to Redis slave",
            "exception_type": "RedisTimeoutError",
        },
    )
    assert log1.status_code == 202
    assert log1.json()["status"] == "Logged (Threshold not reached)"
    assert log1.json()["error_count"] == 1

    # 3. Submit 2nd log -> Breaches threshold (2/2) -> Should Escalate to Agent!
    log2 = client.post(
        "/logs/",
        json={
            "app_name": "checkout-api",
            "content": "Timeout connecting to Redis slave",
            "exception_type": "RedisTimeoutError",
        },
    )
    assert log2.status_code == 202
    assert log2.json()["status"] == "Escalated to Agent"
    assert "incidentId" in log2.json()
    incident_id = log2.json()["incidentId"]

    # 4. Submit 3rd log with SAME exception/content -> Should be Suppressed (Debugging)!
    log3 = client.post(
        "/logs/",
        json={
            "app_name": "checkout-api",
            "content": "Timeout connecting to Redis slave",
            "exception_type": "RedisTimeoutError",
        },
    )
    assert log3.status_code == 202
    assert "Suppressed (Debugging)" in log3.json()["status"]

    # 5. Check Incidents endpoint
    inc_res = client.get("/incidents/")
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) == 1
    assert incidents[0]["id"] == incident_id
    assert incidents[0]["occurrence_count"] == 3  # 2 logged + 1 Debugging!
    assert incidents[0]["status"] == "investigating"

    teardown()
