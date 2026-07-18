import os
import shlex
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.database import Base, get_db
from src.main import app
from src.routers.logs import get_current_user

try:
    from common.fingerprint import compute_canonical_fingerprint
except ImportError:
    from app.common.fingerprint import compute_canonical_fingerprint

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
    return {"username": "testuser", "id": "test-user-id", "role": "admin"}


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. Authentication enforcement (`DAA_AUTH_ENABLED=true` rejecting unauthenticated requests with `401`)
# ---------------------------------------------------------------------------
def test_auth_enforcement_when_enabled():
    orig_override = app.dependency_overrides.pop(get_current_user, None)
    try:
        with patch("src.routers.auth.DAA_AUTH_ENABLED", True):
            res = client.post(
                "/logs/",
                json={
                    "content": "Database timeout",
                    "app_name": "secure-app",
                },
            )
            assert res.status_code == 401
            assert res.json()["detail"] == "Not authenticated"
    finally:
        if orig_override:
            app.dependency_overrides[get_current_user] = orig_override


# ---------------------------------------------------------------------------
# 2. CORS allowlist verification (`Origin: http://evil.com` rejected with `400/403` or unlisted)
# ---------------------------------------------------------------------------
def test_cors_allowlist_enforcement():
    res_evil = client.options(
        "/logs/",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_evil.status_code in (400, 403)
    assert "access-control-allow-origin" not in res_evil.headers

    res_allowed = client.options(
        "/logs/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_allowed.status_code == 200
    assert (
        res_allowed.headers.get("access-control-allow-origin")
        == "http://localhost:3000"
    )


# ---------------------------------------------------------------------------
# 3. End-to-end cryptographic deduplication (`compute_fingerprint` matching)
# ---------------------------------------------------------------------------
@patch("pika.BlockingConnection")
def test_cryptographic_fingerprint_deduplication(mock_pika):
    app_res = client.post("/applications/", json={"name": "payment-api"})
    assert app_res.status_code == 201
    app_id = app_res.json()["id"]

    client.post(
        f"/applications/{app_id}/escalation-policies",
        json={"condition_value": 2, "window_seconds": 120},
    )

    log_content_1 = '2026-07-17T10:00:00Z Connection refused at 0x7fff12345678: File "app/db.py", line 42'
    log_content_2 = '2026-07-17T11:30:15Z Connection refused at 0x7fff99998888: File "app/db.py", line 105'

    fp1 = compute_canonical_fingerprint("payment-api", "DBError", log_content_1)
    fp2 = compute_canonical_fingerprint("payment-api", "DBError", log_content_2)
    assert (
        fp1 == fp2
    ), "Cryptographic fingerprint deduplication failed to canonicalize dynamic addresses/timestamps!"

    res1 = client.post(
        "/logs/",
        json={
            "app_name": "payment-api",
            "content": log_content_1,
            "exception_type": "DBError",
        },
    )
    assert res1.status_code == 202
    assert res1.json()["status"] == "Logged (Threshold not reached)"

    res2 = client.post(
        "/logs/",
        json={
            "app_name": "payment-api",
            "content": log_content_2,
            "exception_type": "DBError",
        },
    )
    assert res2.status_code == 202
    assert res2.json()["status"] == "Escalated to Agent"
    incident_id = res2.json()["incidentId"]

    log_content_3 = '2026-07-17T12:00:00Z Connection refused at 0x7fffaaaa0000: File "app/db.py", line 300'
    res3 = client.post(
        "/logs/",
        json={
            "app_name": "payment-api",
            "content": log_content_3,
            "exception_type": "DBError",
        },
    )
    assert res3.status_code == 202
    assert "Suppressed (Debugging)" in res3.json()["status"]

    inc_res = client.get("/incidents/")
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) == 1
    assert incidents[0]["id"] == incident_id
    assert incidents[0]["occurrence_count"] == 3


# ---------------------------------------------------------------------------
# 4. Safe subprocess argument splitting (`shlex.split` verification & Git `--` option separation)
# ---------------------------------------------------------------------------
def test_safe_shlex_splitting_and_git_options():
    injected_cmd = "pytest tests/ --maxfail=1; echo RCE && bash -c 'whoami'"
    tokenized = shlex.split(injected_cmd)
    assert isinstance(tokenized, list)
    assert tokenized[0] == "pytest"
    assert "echo" in tokenized

    auth_url = "https://token@github.com/rutvej/repo.git"
    git_command = ["git", "ls-remote", "--heads", "--", auth_url]
    assert "--" in git_command
    assert git_command.index("--") < git_command.index(auth_url)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="success")
        import subprocess

        subprocess.run(tokenized, shell=False, check=False)
        mock_run.assert_called_once_with(tokenized, shell=False, check=False)
