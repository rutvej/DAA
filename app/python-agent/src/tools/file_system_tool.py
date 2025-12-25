import os
from langchain.tools import tool
from typing import List

@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file."""
    with open(file_path, "r") as f:
        return f.read()

@tool
def write_file(file_path: str, content: str) -> None:
    """Writes content to a file."""
    with open(file_path, "w") as f:
        f.write(content)

@tool
def list_files(path: str) -> List[str]:
    """Lists all files in a directory."""
    return os.listdir(path)
