import subprocess
import os
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

class RunTestsInput(BaseModel):
    repo_path: str = Field(description="The absolute path of the cloned repository.")
    test_command: str = Field(default="pytest", description="The command to run tests (e.g. 'pytest', 'python -m unittest', 'npm test').")

@tool(args_schema=RunTestsInput)
def run_tests(repo_path: str, test_command: str = "pytest") -> str:
    """Runs a testing or validation command inside the cloned repository to verify code correctness.
    
    Args:
        repo_path: The absolute path of the cloned repository.
        test_command: The shell command to run (e.g., 'pytest', 'npm test').
        
    Returns:
        The output (stdout + stderr) or error details of the test run.
    """
    repo_path = repo_path.strip()
    if not os.path.exists(repo_path):
        return f"Error: Repository path '{repo_path}' does not exist."
    
    try:
        # Run the test command in the repository directory
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        return (
            f"Test execution completed with return code {result.returncode}.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
    except subprocess.TimeoutExpired:
        return "Error: The test command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
