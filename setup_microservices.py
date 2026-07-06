#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"

def load_env() -> dict:
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values

def run_cmd(cmd: str, cwd: Path):
    print(f"$ {cmd} (in {cwd})")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Stdout: {res.stdout}")
        print(f"Stderr: {res.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")
    return res.stdout.strip()

def main():
    env = load_env()
    token = env.get("GITLAB_PRIVATE_TOKEN")
    root_password = env.get("GITLAB_ROOT_PASSWORD", "StrongPassword123")
    daa_token = env.get("DAA_TOKEN")

    if not token:
        print("Error: GITLAB_PRIVATE_TOKEN not found in .env. Run demo setup first.")
        sys.exit(1)
    if not daa_token:
        print("Error: DAA_TOKEN not found in .env. Run demo setup first.")
        sys.exit(1)

    headers = {"PRIVATE-TOKEN": token}
    backend_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {daa_token}"
    }

    # 1. Create projects in GitLab and push code
    for app_name in ["checkout-service", "payment-service"]:
        print(f"\n--- Setting up {app_name} ---")
        
        # Check if project exists on GitLab
        proj_url = f"http://localhost:8082/api/v4/projects/root%2F{app_name}"
        res = requests.get(proj_url, headers=headers)
        if not res.ok:
            print(f"Creating GitLab project {app_name}...")
            res_create = requests.post(
                "http://localhost:8082/api/v4/projects",
                headers=headers,
                data={"name": app_name, "visibility": "public"},
                timeout=15
            )
            res_create.raise_for_status()
            print(f"Created project {app_name} on GitLab.")
        else:
            print(f"Project {app_name} already exists on GitLab.")

        # Git init and push
        app_dir = ROOT_DIR / "examples" / app_name
        run_cmd("git init", app_dir)
        
        # Configure Git remote
        remote_url = f"http://root:{root_password}@localhost:8082/root/{app_name}.git"
        try:
            run_cmd("git remote remove origin", app_dir)
        except Exception:
            pass
        run_cmd(f"git remote add origin {remote_url}", app_dir)

        # Commit and push
        run_cmd('git config user.email "sre@example.com"', app_dir)
        run_cmd('git config user.name "SRE Agent"', app_dir)
        run_cmd("git add .", app_dir)
        try:
            run_cmd('git commit -m "Initial commit"', app_dir)
        except Exception:
            print("No changes to commit.")
        
        # Push
        print(f"Pushing {app_name} to GitLab...")
        run_cmd("git push -u origin master --force", app_dir)
        print(f"Pushed {app_name} successfully!")

        # 2. Register Application in DAA
        print(f"Registering {app_name} in DAA backend...")
        app_res = requests.post(
            "http://localhost:8000/applications/",
            headers=backend_headers,
            json={
                "name": app_name,
                "description": f"Mock microservice {app_name}",
                "language": "python",
                "repository_url": f"http://gitlab:80/root/{app_name}.git"
            }
        )
        if app_res.status_code == 400 and "already exists" in app_res.text:
            print(f"Application {app_name} already registered.")
            # Get the app to retrieve ID
            get_res = requests.get("http://localhost:8000/applications/", headers=backend_headers)
            app_id = next(a["id"] for a in get_res.json() if a["name"] == app_name)
        else:
            app_res.raise_for_status()
            app_id = app_res.json()["id"]
            print(f"Registered application {app_name} (ID: {app_id})")

        # 3. Create Escalation Policy (Threshold = 2 errors in 60s)
        # Check first
        policy_res = requests.get(f"http://localhost:8000/applications/{app_id}/escalation-policies", headers=backend_headers)
        if not policy_res.json():
            print(f"Creating escalation policy for {app_name}...")
            requests.post(
                f"http://localhost:8000/applications/{app_id}/escalation-policies",
                headers=backend_headers,
                json={
                    "rule_type": "error_rate_threshold",
                    "condition_value": 2,
                    "window_seconds": 60,
                    "cooldown_minutes": 30,
                    "severity_keywords": ["FATAL", "OOMKill", "RedisTimeoutError", "PaymentGatewayError"]
                }
            ).raise_for_status()
            print("Created escalation policy.")
        else:
            print(f"Escalation policy for {app_name} already exists.")

        # 4. Register Project Connection (Jira and Git) in DAA
        print(f"Registering project connection for {app_name} in DAA backend...")
        requests.post(
            "http://localhost:8000/projects/",
            headers=backend_headers,
            json={
                "app_name": app_name,
                "repo_provider": "gitlab",
                "repo_url": f"http://gitlab:80/root/{app_name}.git",
                "repo_token": token,
                "jira_url": "http://backend-api:80/mock-jira",
                "jira_token": "mock-token",
                "jira_project_key": "MOCK"
            }
        ).raise_for_status()
        print("Project connection registered successfully!")

if __name__ == "__main__":
    main()
