import subprocess
import os
import json
import requests
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field


class RunTestsInput(BaseModel):
    data: str = Field(
        description=(
            "A JSON string containing 'repo_path' (absolute path to the cloned repo) "
            "and optional 'test_command' (default 'pytest'). "
            'Example: {"repo_path": "/tmp/checkout-service", "test_command": "pytest -v"}'
        )
    )

def _get_app_language(app_name: str) -> str:
    if not app_name:
        return "python"
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    try:
        resp = requests.get(f"{backend_url}/apps/{app_name}", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("language", "python").lower()
    except Exception:
        pass
    return "python"


@tool(args_schema=RunTestsInput)
def run_tests(data: str) -> str:
    """Runs a test or validation command inside the cloned repository to verify code correctness before opening a PR.
    Use this after applying a fix to confirm it passes. If it fails twice, trigger create_incident_ticket instead.
    """
    try:
        input_data = json.loads(data)
        repo_path = input_data.get("repo_path", "").strip()
        test_command = input_data.get("test_command", "pytest").strip()

        # 1. Stateless / Serverless Mode Check
        git_mode = os.getenv("DAA_GIT_MODE", "local")
        db_provider = os.getenv("DAA_DB_PROVIDER", "sqlite")

        if git_mode == "api" or db_provider == "none":
            return (
                "Test execution bypassed: DAA SRE is running in Serverless (Stateless) mode.\n"
                "Reason: Repository code is managed directly via Git REST APIs without local cloning.\n"
                "Result: Verification tests will be executed automatically by the repository's CI/CD pipelines (e.g., GitHub Actions, GitLab CI) once the Pull Request is created.\n"
                "✅ BYPASSED (Safe to proceed with creating Pull Request)"
            )

        if not repo_path:
            return "Error: 'repo_path' is required."

        if not os.path.exists(repo_path):
            return f"Error: Repository path '{repo_path}' does not exist."

        # 2. Deterministic Image Selection based on Application.language
        lang = _get_app_language(os.environ.get("DAA_TARGET_APP", ""))
        image_map = {
            "python": "python:3.10-slim",
            "node": "node:18-slim",
            "javascript": "node:18-slim",
            "typescript": "node:18-slim",
            "go": "golang:1.20",
            "golang": "golang:1.20",
            "java": "maven:3.8-openjdk-17-slim",
            "ruby": "ruby:3.1-slim"
        }
        runner_image = image_map.get(lang, "python:3.10-slim")

        # 3. Execute via docker run
        cmd = f"docker run --rm -v {repo_path}:/workspace -w /workspace {runner_image} {test_command}"
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        command_run = cmd

        return (
            f"Test execution completed with return code {result.returncode}.\n"
            f"Command: {command_run}\n"
            f"--- stdout ---\n{result.stdout or '(empty)'}\n"
            f"--- stderr ---\n{result.stderr or '(empty)'}\n"
            f"{'✅ PASSED' if result.returncode == 0 else '❌ FAILED'}"
        )
    except subprocess.TimeoutExpired:
        return "Error: The test command timed out after 120 seconds."
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error executing command: {str(e)}"
