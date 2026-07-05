import os
import json
import subprocess
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from .file_system_tool import get_full_path

class CheckRecentChangesInput(BaseModel):
    data: str = Field(description="A JSON string containing optional 'repo_path' (default '.') and optional 'hours' (default 24). Example: {\"repo_path\": \"/app\", \"hours\": 24}")

@tool(args_schema=CheckRecentChangesInput)
def check_recent_changes(data: str) -> str:
    """Queries git logs from the last N hours to identify recent commits, author changes, and modified files that may have caused the incident."""
    try:
        input_data = json.loads(data)
        repo_path = input_data.get("repo_path", ".")
        hours = int(input_data.get("hours", 24))
        
        full_dir = get_full_path(repo_path.strip())
        if not os.path.exists(full_dir):
            return f"Error: Repository directory not found: {repo_path}"

        cmd = [
            "git", "log", 
            f"--since={hours} hours ago", 
            "--stat", 
            "--max-count=15",
            "--pretty=format:%h - %an, %ar : %s"
        ]
        
        result = subprocess.run(cmd, cwd=full_dir, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return f"No git repository found or error querying git log in {repo_path}: {result.stderr.strip()}"
            
        output = result.stdout.strip()
        if not output:
            return f"No recent git changes found in {repo_path} over the last {hours} hours."
            
        return f"=== Recent Git Changes (Last {hours} Hours) ===\n{output}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error checking recent changes: {e}"
