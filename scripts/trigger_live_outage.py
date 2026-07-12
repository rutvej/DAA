#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.environ.get("DAA_BACKEND_API_URL", "http://localhost:8000")


def trigger_outage():
    # 1. Login to get fresh token
    print("Logging in to DAA backend...")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/auth/login",
            data=json.dumps(
                {"username": "testuser", "password": "testpassword"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            token = res_data["token"]
            print("Successfully obtained DAA token!")
    except Exception:
        print("Login failed. Trying to register user first...")
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/auth/register",
                data=json.dumps(
                    {"username": "testuser", "password": "testpassword"}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as res:
                print("Registration response:", res.read().decode("utf-8"))

            # Try login again
            req = urllib.request.Request(
                f"{BASE_URL}/auth/login",
                data=json.dumps(
                    {"username": "testuser", "password": "testpassword"}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                token = res_data["token"]
                print("Successfully obtained DAA token after registration!")
        except Exception as reg_err:
            print("Failed to authenticate or register:", reg_err)
            return

    # 2. Submit logs with unique content to trigger a new incident
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    unique_id = uuid.uuid4().hex[:8]
    err_content = f"FATAL: DatabaseDeadlock: transaction deadlock detected while updating table microservices. Run ID: {unique_id}"

    print(f"\nSubmitting unique log errors for test-app (Trace ID: {trace_id})...")
    for i in range(1, 5):
        payload = {
            "app_name": "test-app",
            "content": err_content,
            "exception_type": "DatabaseDeadlock",
            "trace_id": trace_id,
            "correlation_id": str(uuid.uuid4()),
        }

        req = urllib.request.Request(
            f"{BASE_URL}/logs/",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                print(
                    f"Log {i}/4 submitted -> Status: {res_data.get('status')} (Incident: {res_data.get('incidentId')})"
                )
        except urllib.error.HTTPError as e:
            print(f"Log submission failed: {e.code} - {e.read().decode('utf-8')}")
        time.sleep(0.5)

    print("\nLive outage simulation triggered successfully!")


if __name__ == "__main__":
    trigger_outage()
