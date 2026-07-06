import os
import json
from langchain.tools import tool
from typing import List
from pydantic.v1 import BaseModel, Field


ROOT_DIR = os.environ.get("DAA_ROOT_DIR", "/app")

def get_full_path(file_path: str) -> str:
    """Returns the full path of a file."""
    if file_path.startswith("/tmp") or file_path.startswith("/home"):
        return file_path
    if os.path.isabs(file_path):
        if file_path.startswith(ROOT_DIR):
            return file_path
        return os.path.join(ROOT_DIR, file_path[1:])
    return os.path.join(ROOT_DIR, file_path)


@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file.

    Args:
        file_path: The path of the file to read.
    
    Returns:
        The content of the file.
    """
    try:
        full_path = get_full_path(file_path)
        with open(full_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {file_path}"


class WriteFileInput(BaseModel):
    data: str = Field(description="A JSON string containing 'file_path' and 'content'. Example: {\"file_path\": \"/app/main.py\", \"content\": \"print('hello')\"}")


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
    full_path = get_full_path(path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Directory not found: {full_path}")
    return os.listdir(full_path)

