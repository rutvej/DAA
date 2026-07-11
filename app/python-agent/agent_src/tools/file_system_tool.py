import os
import json
from typing import List

try:
    from langchain.tools import tool
except Exception:

    class _LocalToolWrapper:
        def __init__(self, func):
            self.func = func

        def run(self, *args, **kwargs):
            return self.func(*args, **kwargs)

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    def tool(*dargs, **dkwargs):
        if dargs and callable(dargs[0]) and not dkwargs:
            return _LocalToolWrapper(dargs[0])

        def decorator(func):
            return _LocalToolWrapper(func)

        return decorator


try:
    from pydantic.v1 import BaseModel, Field
except Exception:

    class BaseModel:
        pass

    def Field(default=None, **kwargs):
        return default


ROOT_DIR = os.environ.get("DAA_ROOT_DIR", "/app")


def get_full_path(file_path: str) -> str:
    """Returns the full path of a file."""
    file_path = file_path.strip().strip("'\"")
    if file_path.startswith("/tmp") or file_path.startswith("/home"):
        return file_path
    if os.path.isabs(file_path):
        if file_path.startswith(ROOT_DIR):
            return file_path
        return os.path.join(ROOT_DIR, file_path[1:])
    return os.path.join(ROOT_DIR, file_path)


def parse_api_path(file_path: str) -> tuple[str, str]:
    """Extracts app_name and relative path from a file path."""
    file_path = file_path.strip().strip("'\"")
    if file_path.startswith("/tmp/"):
        parts = [p for p in file_path.split("/") if p]
        if len(parts) >= 3:
            app_name = parts[1]
            relative_path = "/".join(parts[2:])
            return app_name, relative_path

    target_app = os.environ.get("DAA_TARGET_APP")
    if target_app:
        return target_app, file_path.lstrip("/")

    parts = [p for p in file_path.split("/") if p]
    if len(parts) > 1:
        return parts[0], "/".join(parts[1:])
    return os.environ.get("DAA_TARGET_APP", "unknown"), file_path.lstrip("/")


@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file.

    Args:
        file_path: The path of the file to read.

    Returns:
        The content of the file.
    """
    if os.environ.get("DAA_GIT_MODE") == "api":
        app_name, relative_path = parse_api_path(file_path)
        from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

        client = CloneFreeGitClient(app_name)
        ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
        content = client.get_file_content(relative_path, ref=ref)
        if content is not None:
            return content
        return f"File not found via API: {relative_path}"

    try:
        full_path = get_full_path(file_path)
        with open(full_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {file_path}"


class WriteFileInput(BaseModel):
    data: str = Field(
        description='A JSON string containing \'file_path\' and \'content\'. Example: {"file_path": "/app/main.py", "content": "print(\'hello\')"}'
    )


@tool(args_schema=WriteFileInput)
def write_file(data: str) -> str:
    """Writes content to a file.

    Args:
        data: A JSON string containing 'file_path' and 'content'.
    """
    try:
        input_data = json.loads(data)
        file_path = input_data.get("file_path")
        content = input_data.get("content")

        if not file_path or content is None:
            return "Error: 'file_path' and 'content' are required in the JSON string."

        if os.environ.get("DAA_GIT_MODE") == "api":
            app_name, relative_path = parse_api_path(file_path)
            from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

            client = CloneFreeGitClient(app_name)
            ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
            success = client.write_file_content(
                relative_path,
                content,
                branch_name=ref,
                commit_message=f"Update {relative_path}",
            )
            if success:
                return "File written and committed successfully via API."
            return f"Error writing file via API: {relative_path}"

        full_path = get_full_path(file_path.strip())
        with open(full_path, "w") as f:
            f.write(content.strip())
        return "File written successfully."
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_files(path: str) -> List[str]:
    """Lists all files in a directory.

    Args:
        path: The path of the directory to list files from.

    Returns:
        A list of files in the directory.
    """
    if os.environ.get("DAA_GIT_MODE") == "api":
        app_name, relative_path = parse_api_path(path)
        from .clonefree_client import CloneFreeGitClient, ACTIVE_BRANCHES

        client = CloneFreeGitClient(app_name)
        ref = ACTIVE_BRANCHES.get(app_name) or client.default_branch or "main"
        return client.list_files(relative_path, ref=ref)

    full_path = get_full_path(path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Directory not found: {full_path}")
    return os.listdir(full_path)
