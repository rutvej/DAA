import os
from langchain.tools import tool
from typing import List
from pydantic.v1 import BaseModel, Field


ROOT_DIR = "/app"

def get_full_path(file_path: str) -> str:
    """Returns the full path of a file."""
    if file_path.startswith("/tmp"):
        return file_path
    if os.path.isabs(file_path):
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
    file_path: str = Field(description="The path of the file to write to.")
    content: str = Field(description="The content to write to the file.")


@tool(args_schema=WriteFileInput)
def write_file(file_path: str, content: str) -> None:
    """Writes content to a file.
    
    Args:
        file_path: The path of the file to write to.
        content: The content to write to the file.
    """
    try:
        full_path = get_full_path(file_path.strip())
        with open(full_path, "w") as f:
            f.write(content.strip())
    except ValueError:
        return "Invalid input format. Please provide the file path and content separated by a comma."


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

