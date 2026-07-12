#!/usr/bin/env python3
"""
DAA v2.0 Autonomous SRE Platform - Outage Simulation & E2E Showcase
-------------------------------------------------------------------
This script simulates a cascading production outage across microservices,
demonstrating DAA's SHA256 error deduplication, sliding-window threshold
escalation, and 4-Dimension surgical SRE investigation.

Usage:
  python3 scripts/simulate_outage.py
"""

import os
import sys
import time
import uuid

# Try importing TestClient to allow standalone in-memory simulation if server is offline
try:
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    db_file = "./demo_showcase.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/backend-api"))
    )
    from sqlalchemy.orm import sessionmaker
    from src.database import Base, engine, get_db
    from src.main import app as backend_app

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    backend_app.dependency_overrides[get_db] = override_get_db
    from src.routers.logs import get_current_user

    backend_app.dependency_overrides[get_current_user] = lambda: {
        "username": "demo-sre",
        "id": "demo-user-id",
    }
    Base.metadata.create_all(bind=engine)
    client = TestClient(backend_app)

    # Mock pika so standalone mode doesn't require a live RabbitMQ broker!
    mock_pika_patch = patch("src.routers.logs.pika.BlockingConnection")
    mock_pika = mock_pika_patch.start()

    STANDALONE_MODE = True
except Exception as e:
    print(
        f"[Note] Could not initialize standalone mode ({e}). Switching to Live Server mode..."
    )
    import requests

    STANDALONE_MODE = False
    BASE_URL = os.environ.get("DAA_BASE_URL", "http://localhost:8000")


def print_header(title):
    print("\n" + "=" * 70)
    print(f" 🚀 {title}")
    print("=" * 70)


def print_step(step_num, text):
    print(f"\n[Step {step_num}] {text}")


def api_post(url, payload):
    if STANDALONE_MODE:
        res = client.post(url, json=payload)
        return res.status_code, res.json()
    else:
        res = requests.post(f"{BASE_URL}{url}", json=payload)
        return res.status_code, res.json()


def api_get(url):
    if STANDALONE_MODE:
        res = client.get(url)
        return res.status_code, res.json()
    else:
        res = requests.get(f"{BASE_URL}{url}")
        return res.status_code, res.json()


def run_showcase():
    print_header("DAA v2.0 AUTONOMOUS SRE PLATFORM - OUTAGE SIMULATION")
    print(
        f"Mode: {'Standalone In-Memory Showcase' if STANDALONE_MODE else f'Live Server ({BASE_URL})'}"
    )

    # --- STEP 1: Register Applications & Policies ---
    print_step(1, "Registering Microservices & SLA Escalation Policies...")

    status, app_res = api_post(
        "/applications/",
        {
            "name": "checkout-service",
            "description": "Handles e-commerce carts and Stripe payment gateways",
            "language": "python",
            "repository_url": "https://github.com/rutvej/checkout-service",
        },
    )
    app_id = app_res.get("id", str(uuid.uuid4()))
    print(f"  ✔ Registered Application: checkout-service (ID: {app_id[:8]}...)")

    status, policy_res = api_post(
        f"/applications/{app_id}/escalation-policies",
        {
            "rule_type": "error_rate_threshold",
            "condition_value": 3,
            "window_seconds": 60,
            "severity_keywords": ["FATAL", "OOMKill", "DatabaseDeadlock"],
            "cooldown_minutes": 30,
        },
    )
    print("  ✔ Created Escalation Policy: Escalate after 3 errors in 60 seconds")

    # --- STEP 2: Simulate Production Outage & Error Flood ---
    print_step(2, "Simulating Cascading Outage (Redis Connection Timeout Flood)...")

    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    err_content = "RedisTimeoutError: Connection timed out connecting to redis-master:6379 after 5000ms. Pool exhausted."

    for i in range(1, 6):
        time.sleep(0.4)
        status, log_res = api_post(
            "/logs/",
            {
                "app_name": "checkout-service",
                "content": err_content,
                "exception_type": "RedisTimeoutError",
                "trace_id": trace_id,
                "correlation_id": str(uuid.uuid4()),
            },
        )

        log_status = log_res.get("status", "Unknown")
        if "Logged (Threshold not reached)" in log_status:
            print(
                f"  ⚡ [Log {i}/5] Received Error -> Status: Logged ({log_res.get('error_count')}/3 in 60s window)"
            )
        elif "Escalated to Agent" in log_status:
            inc_id = log_res.get("incidentId", "N/A")
            print(
                f"  🚨 [Log {i}/5] THRESHOLD BREACHED (3/3)! -> Status: Escalated to Agent!"
            )
            print(f"     ➔ Created Active Incident ID: {inc_id}")
            print("     ➔ Published Fix Job to RabbitMQ Queue 'fix_jobs'")
        elif "Suppressed (Debugging)" in log_status:
            print(
                f"  🛡️  [Log {i}/5] IDENTICAL ERROR DETECTED -> Status: Suppressed (Debugging)!"
            )
            print(
                "     ➔ SHA256 Fingerprint matched active incident. 0% Redundant LLM Token Waste!"
            )

    # --- STEP 3: Verify Incident State in Database ---
    print_step(3, "Verifying Active Incident Database State...")
    status, inc_list = api_get("/incidents/")
    if inc_list and len(inc_list) > 0:
        inc = inc_list[0]
        print(f"  ✔ Incident ID       : {inc.get('id')}")
        print(f"  ✔ Application       : {inc.get('app_name')}")
        print(f"  ✔ SHA256 Fingerprint: {inc.get('fingerprint')[:16]}...")
        print(
            f"  ✔ Occurrence Count  : {inc.get('occurrence_count')} errors aggregated"
        )
        print(f"  ✔ Current Status    : {inc.get('status').upper()}")
    else:
        print("  ✖ No active incidents found.")

    # --- STEP 4: Demonstrate 4-Dimension Agent Diagnostics ---
    print_step(4, "Simulating Python Agent 4-Dimension SRE Investigation...")
    print("  [Agent] Waking up to process job from RabbitMQ...")
    time.sleep(0.5)
    print("  [Dimension 1: Change Horizon] Executing `check_recent_changes`...")
    print(
        "    ➔ Found commit a8f92b: 'Update redis pool max_connections from 500 to 10'"
    )
    time.sleep(0.5)
    print("  [Dimension 2: Infra Status] Executing `check_alerts`...")
    print("    ➔ Alert Active: Redis connection pool 100% saturated on redis-master")
    time.sleep(0.5)
    print(
        "  [Dimension 3: Correlated Traces] Executing `query_correlated_logs(trace_id)`..."
    )
    print(
        "    ➔ Correlated 3 failed requests across payment-service and checkout-service"
    )
    time.sleep(0.5)
    print(
        "  [Dimension 4: Surgical Code Nav] Executing `read_repomap` & `view_file_slice`..."
    )
    print(
        "    ➔ Read repomap (120 lines total). Located symbol `redis_pool_init` in config.py"
    )
    print(
        "    ➔ Viewed slice config.py:L15-L25 (10 lines read. NOT reading entire 5000-line repo!)"
    )

    # --- STEP 5: Generate Postmortem Report ---
    print_step(5, "Generating Automated SRE Postmortem Report...")

    postmortem = f"""
======================================================================
📄 DAA v2.0 AUTONOMOUS POSTMORTEM REPORT
======================================================================
Incident ID : INC-2026-884
Service     : checkout-service
Severity    : HIGH (Threshold Breached: 5 occurrences in 60s)
Root Cause  : Redis connection pool exhaustion caused by commit a8f92b 
              which reduced max_connections to 10 under high cart load.

--- 4-Dimension Investigation Summary ---
1. Recent Changes : Commit a8f92b modified redis pool settings 2 hours ago.
2. Infra Status   : Redis server health is OK, but connection limit reached.
3. Traces         : Trace {trace_id} shows cascading 504 Gateway Timeouts.
4. Code Diagnosis : Surgically analyzed `config.py` via AST repomap without
                    token flooding.

--- Remediation Action ---
✔ Generated Pull Request: https://github.com/rutvej/checkout-service/pull/142
  (Reverts max_connections back to 500 and adds exponential backoff retry)
✔ Verification Tests    : 14/14 passed in isolated container sandbox.
======================================================================
"""
    print(postmortem)
    print_header("SHOWCASE COMPLETE - DAA v2.0 IS READY FOR PRODUCTION!")
    print("\n")


if __name__ == "__main__":
    run_showcase()
