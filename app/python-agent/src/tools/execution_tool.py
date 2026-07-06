import subprocess
import os
import json
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


@tool(args_schema=RunTestsInput)
def run_tests(data: str) -> str:
    """Runs a test or validation command inside the cloned repository to verify code correctness before opening a PR.
    Use this after applying a fix to confirm it passes. If it fails twice, trigger create_incident_ticket instead.
    """
    try:
        input_data = json.loads(data)
        repo_path = input_data.get("repo_path", "").strip()
        test_command = input_data.get("test_command", "pytest").strip()

        if not repo_path:
            return "Error: 'repo_path' is required."

        if not os.path.exists(repo_path):
            return f"Error: Repository path '{repo_path}' does not exist."

        result = subprocess.run(
            test_command,
            shell=True,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )

        return (
            f"Test execution completed with return code {result.returncode}.\n"
            f"Command: {test_command}\n"
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
