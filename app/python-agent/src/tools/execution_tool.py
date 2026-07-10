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

        # 2. Match container for Full-Stack Outsourced Testing
        container_name = None
        try:
            docker_ps = subprocess.run(
                "docker ps --format '{{.Names}}'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            names = [n.strip() for n in docker_ps.stdout.split("\n") if n.strip()]
            repo_dir_name = os.path.basename(repo_path.rstrip("/"))
            for name in names:
                if repo_dir_name in name:
                    container_name = name
                    break
        except Exception:
            pass

        if container_name:
            # Run the test inside the running container sandbox
            cmd = f"docker exec -w /app {container_name} {test_command}"
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            command_run = cmd
        else:
            # Fallback to local subprocess execution
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            command_run = test_command

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
